from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from wristalpha.analytics.cleaning import CleanListing, mark_price_outliers
from wristalpha.analytics.features import MacroObservation, build_feature_row
from wristalpha.analytics.indexing import IndexedListing, build_hedonic_index
from wristalpha.analytics.quality import run_quality_checks
from wristalpha.analytics.resolution import CanonicalReference, resolve_reference


def _listing(
    external_id: str,
    *,
    price: float = 10_000,
    month: int = 1,
    reference: str = "REF-1",
) -> CleanListing:
    observed = datetime(2026, month, 1, tzinfo=UTC)
    return CleanListing(
        source="fixture",
        external_id=external_id,
        fetched_at=observed,
        title="Example Watch",
        price=Decimal(str(price)),
        currency="USD",
        brand="Example",
        reference_hint=reference,
        production_year=2020,
        condition="good",
        box=True,
        papers=True,
        seller_type="dealer",
        seller_country="US",
        vat_included=False,
        first_seen=observed,
        last_seen=observed,
        days_on_market=10,
    )


def test_resolution_is_exact_and_ambiguous_inputs_fail_closed() -> None:
    catalog = [
        CanonicalReference("11111111-1111-1111-1111-111111111111", "Example", "REF-1", "Family")
    ]
    assert resolve_reference(_listing("1"), catalog).confidence == 1
    unresolved = resolve_reference(_listing("2", reference="OTHER"), catalog)
    assert unresolved.reference_id is None


def test_hedonic_index_and_point_in_time_features() -> None:
    rows = [
        IndexedListing(
            _listing(str(index), price=10_000 + index * 50, month=1 if index < 6 else 2),
            "11111111-1111-1111-1111-111111111111",
            "Family",
        )
        for index in range(12)
    ]
    points = build_hedonic_index(rows)
    assert len(points) == 2
    as_of = datetime(2026, 3, 1, tzinfo=UTC)
    feature = build_feature_row(
        reference_id=rows[0].reference_id,
        as_of=as_of,
        maximum_source_ingested_at=datetime(2026, 2, 2, tzinfo=UTC),
        index_history=points,
        listings=[row.listing for row in rows],
        retail_price=100,
        brand_factor_return=0.02,
        macro=[
            MacroObservation(
                "gold",
                0.01,
                datetime(2026, 2, 1, tzinfo=UTC),
                datetime(2026, 2, 2, tzinfo=UTC),
                "configured-fixture",
            )
        ],
    )
    assert feature.values["momentum_1m"] is not None
    assert feature.values["macro_gold"] == 0.01
    with pytest.raises(ValueError, match="look-ahead"):
        build_feature_row(
            reference_id=rows[0].reference_id,
            as_of=as_of,
            maximum_source_ingested_at=as_of + timedelta(days=1),
            index_history=points,
            listings=[],
            retail_price=None,
            brand_factor_return=None,
            macro=[],
        )


def test_outliers_are_logged_and_quality_can_block() -> None:
    listings = [_listing(str(index), price=10_000 + index) for index in range(99)]
    listings.append(_listing("extreme", price=1_000_000))
    marked = mark_price_outliers(listings)
    assert marked[-1].outlier_reason == "price_above_winsor_bound"
    as_of = datetime(2026, 1, 1, tzinfo=UTC)
    checks = run_quality_checks(
        marked,
        as_of=as_of,
        maximum_source_ingested_at=as_of + timedelta(seconds=1),
    )
    assert next(item for item in checks if item.name == "no_lookahead").passed is False
