from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from wristalpha.adapters import AdapterDataError, CsvMarketplaceAdapter, MarketplaceQuery

HEADER = (
    "source,external_id,fetched_at,title,price,currency,url,brand,reference_hint,"
    "production_year,condition,box,papers,seller_type,seller_country,vat_included,"
    "warranty_remaining_months,service_history,description\n"
)


def _write_csv(path: Path, rows: str) -> Path:
    path.write_text(HEADER + rows, encoding="utf-8")
    return path


def test_csv_adapter_preserves_raw_data_and_filters_query(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path / "listings.csv",
        "dealer-notes,abc-1,2026-07-29T12:00:00+00:00,"
        '"Example Watch",12500,usd,https://example.test/abc-1,Rolex,124060,'
        '2022,excellent,yes,true,dealer,us,true,20,"Serviced 2025","Full set"\n'
        "dealer-notes,abc-2,2026-07-20T12:00:00+00:00,"
        '"Older Watch",9000,USD,https://example.test/abc-2,Omega,310.30.42.50.01.001,'
        "2020,good,no,true,dealer,gb,false,,,Example\n",
    )
    adapter = CsvMarketplaceAdapter(path)

    listings = adapter.fetch_listings(
        MarketplaceQuery(
            brands=("rolex",),
            references=("124060",),
            maximum_price=Decimal("13000"),
            currency="usd",
        ),
        since=datetime(2026, 7, 25, tzinfo=UTC),
    )

    assert len(listings) == 1
    listing = listings[0]
    assert listing.external_id == "abc-1"
    assert listing.currency == "USD"
    assert listing.seller_country == "US"
    assert listing.box is True
    assert listing.raw_payload["price"] == "12500"
    assert len(listing.raw_payload_sha256) == 64


def test_csv_adapter_rejects_unknown_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(
        "source,external_id,fetched_at,title,price,currency,url,invented\n",
        encoding="utf-8",
    )

    with pytest.raises(AdapterDataError, match="unsupported columns"):
        CsvMarketplaceAdapter(path).fetch_listings(MarketplaceQuery(), since=None)


def test_csv_adapter_rejects_naive_since(tmp_path: Path) -> None:
    path = _write_csv(tmp_path / "listings.csv", "")

    with pytest.raises(AdapterDataError, match="UTC offset"):
        CsvMarketplaceAdapter(path).fetch_listings(
            MarketplaceQuery(),
            since=datetime(2026, 7, 29),
        )


def test_csv_adapter_rejects_ambiguous_boolean(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path / "listings.csv",
        "manual,abc-1,2026-07-29T12:00:00+00:00,Watch,1000,USD,"
        "https://example.test/abc-1,Brand,Ref,2022,good,probably,true,dealer,US,true,,,\n",
    )

    with pytest.raises(AdapterDataError, match="box must be"):
        CsvMarketplaceAdapter(path).fetch_listings(MarketplaceQuery(), since=None)


def test_csv_adapter_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(AdapterDataError, match="does not exist"):
        CsvMarketplaceAdapter(tmp_path / "missing.csv").fetch_listings(
            MarketplaceQuery(),
            since=None,
        )
