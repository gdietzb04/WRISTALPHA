"""Manual CSV adapter for user-recorded dealer and marketplace observations."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from wristalpha.adapters.base import (
    AdapterDataError,
    MarketplaceAdapter,
    MarketplaceQuery,
    RawListing,
)

REQUIRED_COLUMNS = frozenset(
    {"source", "external_id", "fetched_at", "title", "price", "currency", "url"}
)
OPTIONAL_COLUMNS = frozenset(
    {
        "brand",
        "reference_hint",
        "production_year",
        "condition",
        "box",
        "papers",
        "seller_type",
        "seller_country",
        "vat_included",
        "warranty_remaining_months",
        "service_history",
        "description",
    }
)
SUPPORTED_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS
BOOLEAN_COLUMNS = frozenset({"box", "papers", "vat_included"})
INTEGER_COLUMNS = frozenset({"production_year", "warranty_remaining_months"})


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _parse_bool(value: str | None, *, column: str, row_number: int) -> bool | None:
    normalized = _optional_text(value)
    if normalized is None:
        return None
    choices = {
        "true": True,
        "yes": True,
        "1": True,
        "false": False,
        "no": False,
        "0": False,
    }
    parsed = choices.get(normalized.lower())
    if parsed is None:
        raise AdapterDataError(
            f"row {row_number}: {column} must be true/false, yes/no, 1/0, or empty"
        )
    return parsed


def _parse_int(value: str | None, *, column: str, row_number: int) -> int | None:
    normalized = _optional_text(value)
    if normalized is None:
        return None
    try:
        return int(normalized)
    except ValueError as exc:
        raise AdapterDataError(f"row {row_number}: {column} must be an integer") from exc


class CsvMarketplaceAdapter(MarketplaceAdapter):
    """Read immutable raw observations from a user-controlled CSV file."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def fetch_listings(
        self,
        query: MarketplaceQuery,
        since: datetime | None,
    ) -> list[RawListing]:
        if since is not None and (since.tzinfo is None or since.utcoffset() is None):
            raise AdapterDataError("since must include a UTC offset")
        if not self._path.is_file():
            raise AdapterDataError(f"CSV source does not exist: {self._path}")

        with self._path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            self._validate_header(reader.fieldnames)
            listings = [
                listing
                for row_number, row in enumerate(reader, start=2)
                if (listing := self._parse_row(row, row_number)) is not None
                and self._matches(listing, query, since)
            ]
        return listings

    @staticmethod
    def _validate_header(fieldnames: Sequence[str] | None) -> None:
        if fieldnames is None:
            raise AdapterDataError("CSV source has no header")
        normalized = {name.strip() for name in fieldnames}
        missing = REQUIRED_COLUMNS - normalized
        unknown = normalized - SUPPORTED_COLUMNS
        if missing:
            raise AdapterDataError(f"CSV source is missing required columns: {sorted(missing)}")
        if unknown:
            raise AdapterDataError(f"CSV source has unsupported columns: {sorted(unknown)}")

    @staticmethod
    def _parse_row(row: dict[str, str | None], row_number: int) -> RawListing | None:
        if all(_optional_text(value) is None for value in row.values()):
            return None

        raw_payload = {key.strip(): value for key, value in row.items()}
        parsed: dict[str, Any] = {key: _optional_text(value) for key, value in raw_payload.items()}
        for column in BOOLEAN_COLUMNS:
            parsed[column] = _parse_bool(
                raw_payload.get(column),
                column=column,
                row_number=row_number,
            )
        for column in INTEGER_COLUMNS:
            parsed[column] = _parse_int(
                raw_payload.get(column),
                column=column,
                row_number=row_number,
            )
        try:
            parsed["price"] = Decimal(parsed["price"])
        except (InvalidOperation, TypeError) as exc:
            raise AdapterDataError(f"row {row_number}: price must be a decimal") from exc

        parsed["raw_payload"] = raw_payload
        try:
            return RawListing.model_validate(parsed)
        except ValidationError as exc:
            raise AdapterDataError(f"row {row_number}: {exc}") from exc

    @staticmethod
    def _matches(
        listing: RawListing,
        query: MarketplaceQuery,
        since: datetime | None,
    ) -> bool:
        if since is not None and listing.fetched_at < since:
            return False
        normalized_brands = {brand.casefold() for brand in query.brands}
        if normalized_brands and (
            listing.brand is None or listing.brand.casefold() not in normalized_brands
        ):
            return False
        normalized_references = {reference.casefold() for reference in query.references}
        if normalized_references and (
            listing.reference_hint is None
            or listing.reference_hint.casefold() not in normalized_references
        ):
            return False
        if query.maximum_price is not None:
            if query.currency is None or listing.currency != query.currency:
                return False
            if listing.price > query.maximum_price:
                return False
        return True
