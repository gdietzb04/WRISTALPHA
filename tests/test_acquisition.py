from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from wristalpha.acquisition.auctions import AuctionCsvAdapter
from wristalpha.acquisition.cache import RawResponseCache
from wristalpha.acquisition.html import (
    CompliantHtmlAdapter,
    FetchResult,
    HtmlSourceDefinition,
    SelectorSet,
    SourceBlockedError,
)
from wristalpha.adapters.base import MarketplaceQuery, RawListing


class StubFetcher:
    def __init__(self, result: FetchResult) -> None:
        self.result = result
        self.calls = 0

    def fetch(self, definition: HtmlSourceDefinition) -> FetchResult:
        del definition
        self.calls += 1
        return self.result


def _definition() -> HtmlSourceDefinition:
    return HtmlSourceDefinition(
        source="verified-fixture",
        search_url="https://example.com/watches",
        user_agent="WRISTALPHA/0.1 research@example.invalid",
        selectors=SelectorSet(
            item="[data-listing]",
            external_id_attribute="data-listing",
            title=".title",
            price=".price",
            currency=".currency",
            url="a",
        ),
        minimum_interval_seconds=1,
        jitter_seconds=0,
    )


def test_raw_listing_payload_is_deeply_immutable() -> None:
    listing = RawListing(
        source="fixture",
        external_id="1",
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        title="Example",
        price="100",
        currency="usd",
        url="https://example.com/1",
        raw_payload={"price": "100", "nested": {"values": [1, 2]}},
    )
    with pytest.raises(TypeError):
        listing.raw_payload["price"] = "999"  # type: ignore[index]
    assert listing.raw_payload["nested"]["values"] == (1, 2)


def test_html_adapter_caches_and_maps_verified_selector_output(tmp_path: Path) -> None:
    record: dict[str, Any] = {
        "external_id": "abc",
        "title": "Watch",
        "price": "12,500",
        "currency": "USD",
        "url": "/watch/abc",
        "brand": "Example",
        "reference_hint": "REF-1",
    }
    fetcher = StubFetcher(
        FetchResult(
            status=200,
            content_type="text/html",
            body=b"<html>fixture</html>",
            records=(record,),
            fetched_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )
    adapter = CompliantHtmlAdapter(
        _definition(),
        RawResponseCache(tmp_path),
        fetcher=fetcher,
        robots_allowed=lambda url, user_agent: bool(url and user_agent),
        sleep=lambda seconds: None,
        random_uniform=lambda start, end: 0,
    )
    listings = adapter.fetch_listings(
        MarketplaceQuery(brands=("Example",), references=("REF-1",)),
        None,
    )
    assert listings[0].price == 12_500
    assert str(listings[0].url) == "https://example.com/watch/abc"
    assert len(list(tmp_path.rglob("*.body"))) == 1


def test_html_adapter_fails_closed_on_robots_or_http_block(tmp_path: Path) -> None:
    result = FetchResult(429, None, b"", (), datetime(2026, 1, 1, tzinfo=UTC))
    with pytest.raises(SourceBlockedError, match=r"robots\.txt"):
        CompliantHtmlAdapter(
            _definition(),
            RawResponseCache(tmp_path),
            fetcher=StubFetcher(result),
            robots_allowed=lambda url, user_agent: False,
        ).fetch_listings(MarketplaceQuery(), None)
    with pytest.raises(SourceBlockedError, match="HTTP 429"):
        CompliantHtmlAdapter(
            _definition(),
            RawResponseCache(tmp_path),
            fetcher=StubFetcher(result),
            robots_allowed=lambda url, user_agent: True,
            sleep=lambda seconds: None,
        ).fetch_listings(MarketplaceQuery(), None)


def test_auction_csv_adapter_preserves_verified_results(tmp_path: Path) -> None:
    path = tmp_path / "auction.csv"
    path.write_text(
        "auction_house,external_id,sold_at,realized_price,currency,source_url,title,"
        "hammer_price,buyer_premium,lot_number,sale_name,brand,reference_hint\n"
        "Phillips,p-1,2026-01-01T10:00:00+00:00,11000,usd,"
        "https://example.com/p-1,Example,10000,1000,12,Sale,Example,REF-1\n",
        encoding="utf-8",
    )
    result = AuctionCsvAdapter(path).fetch_transactions()
    assert result[0].auction_house == "Phillips"
    assert result[0].currency == "USD"
    assert len(result[0].raw_payload_sha256) == 64
