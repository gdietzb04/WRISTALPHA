"""Conservative, logged normalization of raw listing observations."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from wristalpha.adapters.base import RawListing

SPACE = re.compile(r"\s+")
REFERENCE_NOISE = re.compile(r"[^A-Z0-9]")


@dataclass(frozen=True)
class CleanListing:
    source: str
    external_id: str
    fetched_at: datetime
    title: str
    price: Decimal
    currency: str
    brand: str | None
    reference_hint: str | None
    production_year: int | None
    condition: str | None
    box: bool | None
    papers: bool | None
    seller_type: str | None
    seller_country: str | None
    vat_included: bool | None
    first_seen: datetime
    last_seen: datetime
    days_on_market: int
    price_cut_fraction: float | None = None
    outlier_reason: str | None = None


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = SPACE.sub(" ", value).strip()
    return normalized or None


def normalize_reference(value: str | None) -> str | None:
    text = normalize_text(value)
    if text is None:
        return None
    result = REFERENCE_NOISE.sub("", text.upper())
    return result or None


def clean_listing(raw: RawListing) -> CleanListing:
    return CleanListing(
        source=raw.source,
        external_id=raw.external_id,
        fetched_at=raw.fetched_at,
        title=normalize_text(raw.title) or raw.title,
        price=raw.price,
        currency=raw.currency,
        brand=normalize_text(raw.brand),
        reference_hint=normalize_reference(raw.reference_hint),
        production_year=raw.production_year,
        condition=normalize_text(raw.condition),
        box=raw.box,
        papers=raw.papers,
        seller_type=normalize_text(raw.seller_type),
        seller_country=raw.seller_country,
        vat_included=raw.vat_included,
        first_seen=raw.fetched_at,
        last_seen=raw.fetched_at,
        days_on_market=0,
    )


def mark_price_outliers(
    listings: list[CleanListing],
    *,
    lower_quantile: float = 0.01,
    upper_quantile: float = 0.99,
) -> list[CleanListing]:
    if not listings:
        return []
    prices = sorted(float(item.price) for item in listings)
    lower = prices[min(int((len(prices) - 1) * lower_quantile), len(prices) - 1)]
    upper = prices[min(int((len(prices) - 1) * upper_quantile), len(prices) - 1)]
    return [
        replace(
            item,
            outlier_reason=(
                "price_below_winsor_bound"
                if float(item.price) < lower
                else "price_above_winsor_bound"
                if float(item.price) > upper
                else None
            ),
        )
        for item in listings
    ]
