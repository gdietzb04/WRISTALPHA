"""Robots-aware Playwright HTML acquisition with conservative retry behavior."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from playwright.sync_api import sync_playwright

from wristalpha.acquisition.cache import RawResponseCache
from wristalpha.adapters.base import (
    AdapterConfigurationError,
    AdapterDataError,
    AdapterError,
    MarketplaceAdapter,
    MarketplaceQuery,
    RawListing,
)

LOGGER = logging.getLogger(__name__)


class SourceBlockedError(AdapterError):
    """Raised on explicit source refusal; callers must switch adapters."""


@dataclass(frozen=True)
class SelectorSet:
    """CSS selectors that must be verified against the live source."""

    item: str
    external_id_attribute: str
    title: str
    price: str
    currency: str
    url: str
    brand: str | None = None
    reference: str | None = None


@dataclass(frozen=True)
class HtmlSourceDefinition:
    source: str
    search_url: str
    user_agent: str
    selectors: SelectorSet
    minimum_interval_seconds: float = 4.0
    jitter_seconds: float = 1.0
    max_attempts: int = 3
    request_timeout_ms: int = 30_000

    def __post_init__(self) -> None:
        if not self.user_agent.strip() or "wristalpha" not in self.user_agent.casefold():
            raise AdapterConfigurationError("user_agent must identify WRISTALPHA")
        if self.minimum_interval_seconds < 1:
            raise AdapterConfigurationError("minimum_interval_seconds must be at least one")
        if not 1 <= self.max_attempts <= 4:
            raise AdapterConfigurationError("max_attempts must be between one and four")


@dataclass(frozen=True)
class FetchResult:
    status: int
    content_type: str | None
    body: bytes
    records: tuple[Mapping[str, Any], ...]
    fetched_at: datetime


class HtmlFetcher(Protocol):
    def fetch(self, definition: HtmlSourceDefinition) -> FetchResult: ...


class PlaywrightHtmlFetcher:
    """Acquire and extract one source page through Playwright."""

    def fetch(self, definition: HtmlSourceDefinition) -> FetchResult:
        selectors = definition.selectors
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(user_agent=definition.user_agent)
            try:
                response = page.goto(
                    definition.search_url,
                    wait_until="domcontentloaded",
                    timeout=definition.request_timeout_ms,
                )
                status = response.status if response is not None else 0
                content_type = (
                    response.headers.get("content-type") if response is not None else None
                )
                body = page.content().encode("utf-8")
                records = tuple(
                    page.locator(selectors.item).evaluate_all(
                        """(items, s) => items.map((item) => {
                          const text = (selector) => selector
                            ? item.querySelector(selector)?.textContent?.trim() ?? null
                            : null;
                          const link = item.querySelector(s.url);
                          return {
                            external_id: item.getAttribute(s.external_id_attribute),
                            title: text(s.title),
                            price: text(s.price),
                            currency: text(s.currency),
                            url: link?.href ?? text(s.url),
                            brand: text(s.brand),
                            reference_hint: text(s.reference),
                          };
                        })""",
                        {
                            "external_id_attribute": selectors.external_id_attribute,
                            "title": selectors.title,
                            "price": selectors.price,
                            "currency": selectors.currency,
                            "url": selectors.url,
                            "brand": selectors.brand,
                            "reference": selectors.reference,
                        },
                    )
                )
                return FetchResult(status, content_type, body, records, datetime.now(UTC))
            finally:
                browser.close()


class RobotsTxtPolicy:
    def allowed(self, url: str, user_agent: str) -> bool:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        request = Request(robots_url, headers={"User-Agent": user_agent})
        try:
            with urlopen(request, timeout=15) as response:
                text = response.read().decode("utf-8", errors="replace")
        except OSError:
            LOGGER.warning("robots.txt unavailable; failing closed", extra={"url": robots_url})
            return False
        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(text.splitlines())
        return parser.can_fetch(user_agent, url)


class CompliantHtmlAdapter(MarketplaceAdapter):
    """Configured HTML adapter; selectors must be verified against a live source."""

    def __init__(
        self,
        definition: HtmlSourceDefinition,
        cache: RawResponseCache,
        *,
        fetcher: HtmlFetcher | None = None,
        robots_allowed: Callable[[str, str], bool] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        random_uniform: Callable[[float, float], float] = random.uniform,
    ) -> None:
        self._definition = definition
        self._cache = cache
        self._fetcher = fetcher or PlaywrightHtmlFetcher()
        self._robots_allowed = robots_allowed or RobotsTxtPolicy().allowed
        self._sleep = sleep
        self._random_uniform = random_uniform
        self._last_request_at: float | None = None

    def fetch_listings(
        self,
        query: MarketplaceQuery,
        since: datetime | None,
    ) -> list[RawListing]:
        if since is not None and (since.tzinfo is None or since.utcoffset() is None):
            raise AdapterDataError("since must include a UTC offset")
        definition = self._definition
        if not self._robots_allowed(definition.search_url, definition.user_agent):
            raise SourceBlockedError(
                f"{definition.source}: robots.txt disallows acquisition; use licensed API or CSV"
            )
        result: FetchResult | None = None
        for attempt in range(definition.max_attempts):
            self._respect_rate_limit()
            try:
                result = self._fetcher.fetch(definition)
            except Exception as exc:
                if attempt + 1 == definition.max_attempts:
                    raise AdapterError(f"{definition.source}: acquisition failed") from exc
                self._sleep(2**attempt + self._random_uniform(0, definition.jitter_seconds))
                continue
            if result.status in {403, 429}:
                LOGGER.warning(
                    "source blocked automated access; switch to licensed API or CSV",
                    extra={"source": definition.source, "status": result.status},
                )
                raise SourceBlockedError(
                    f"{definition.source}: HTTP {result.status}; use licensed API or CSV"
                )
            if result.status >= 500 and attempt + 1 < definition.max_attempts:
                self._sleep(2**attempt + self._random_uniform(0, definition.jitter_seconds))
                continue
            break
        if result is None or not 200 <= result.status < 300:
            status = result.status if result is not None else "unknown"
            raise AdapterError(f"{definition.source}: unexpected HTTP status {status}")
        self._cache.store(
            source=definition.source,
            url=definition.search_url,
            fetched_at=result.fetched_at,
            status=result.status,
            content_type=result.content_type,
            body=result.body,
        )
        listings = [self._parse_record(record, result.fetched_at) for record in result.records]
        return [
            listing
            for listing in listings
            if (since is None or listing.fetched_at >= since)
            and self._matches_query(listing, query)
        ]

    def _respect_rate_limit(self) -> None:
        now = time.monotonic()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            delay = (
                self._definition.minimum_interval_seconds
                + self._random_uniform(0, self._definition.jitter_seconds)
                - elapsed
            )
            if delay > 0:
                self._sleep(delay)
        self._last_request_at = time.monotonic()

    def _parse_record(self, record: Mapping[str, Any], fetched_at: datetime) -> RawListing:
        required = ("external_id", "title", "price", "currency", "url")
        if any(not str(record.get(key) or "").strip() for key in required):
            raise AdapterDataError(
                f"{self._definition.source}: selector output missing required data"
            )
        try:
            price = Decimal(str(record["price"]).replace(",", "").strip())
        except InvalidOperation as exc:
            raise AdapterDataError(f"{self._definition.source}: price is not decimal") from exc
        url = urljoin(self._definition.search_url, str(record["url"]))
        return RawListing(
            source=self._definition.source,
            external_id=str(record["external_id"]),
            fetched_at=fetched_at,
            title=str(record["title"]),
            price=price,
            currency=str(record["currency"]),
            url=url,
            brand=str(record["brand"]) if record.get("brand") else None,
            reference_hint=(
                str(record["reference_hint"]) if record.get("reference_hint") else None
            ),
            raw_payload=dict(record),
        )

    @staticmethod
    def _matches_query(listing: RawListing, query: MarketplaceQuery) -> bool:
        if query.brands and (
            listing.brand is None
            or listing.brand.casefold() not in {brand.casefold() for brand in query.brands}
        ):
            return False
        if query.references and (
            listing.reference_hint is None
            or listing.reference_hint.casefold()
            not in {reference.casefold() for reference in query.references}
        ):
            return False
        if query.maximum_price is not None:
            return query.currency == listing.currency and listing.price <= query.maximum_price
        return True
