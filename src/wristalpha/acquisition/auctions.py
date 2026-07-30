"""First-class manual auction result acquisition."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from wristalpha.adapters.base import AdapterDataError, FrozenDict

SUPPORTED_AUCTION_HOUSES = frozenset({"Phillips", "Christie's", "Sotheby's", "Antiquorum"})
REQUIRED_COLUMNS = frozenset(
    {
        "auction_house",
        "external_id",
        "sold_at",
        "realized_price",
        "currency",
        "source_url",
        "title",
    }
)


class RawTransaction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    auction_house: str
    external_id: str
    sold_at: datetime
    realized_price: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    source_url: HttpUrl
    title: str
    hammer_price: Decimal | None = Field(default=None, gt=0)
    buyer_premium: Decimal | None = Field(default=None, ge=0)
    lot_number: str | None = None
    sale_name: str | None = None
    brand: str | None = None
    reference_hint: str | None = None
    raw_payload: FrozenDict

    @field_validator("sold_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("sold_at must include a UTC offset")
        return value

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("auction_house")
    @classmethod
    def known_house(cls, value: str) -> str:
        if value not in SUPPORTED_AUCTION_HOUSES:
            raise ValueError("auction house is not a configured first-class source")
        return value

    @field_validator("raw_payload", mode="before")
    @classmethod
    def freeze_payload(cls, value: Any) -> FrozenDict:
        if not isinstance(value, dict):
            raise ValueError("raw_payload must be a mapping")
        return FrozenDict(value)

    @property
    def raw_payload_sha256(self) -> str:
        canonical = json.dumps(
            self.raw_payload.to_plain(),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


class AuctionCsvAdapter:
    def __init__(self, path: Path) -> None:
        self._path = path

    def fetch_transactions(self, since: datetime | None = None) -> list[RawTransaction]:
        if since is not None and (since.tzinfo is None or since.utcoffset() is None):
            raise AdapterDataError("since must include a UTC offset")
        if not self._path.is_file():
            raise AdapterDataError(f"auction CSV does not exist: {self._path}")
        with self._path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or ())
            missing = REQUIRED_COLUMNS - fields
            if missing:
                raise AdapterDataError(f"auction CSV missing columns: {sorted(missing)}")
            transactions = [
                transaction
                for row_number, row in enumerate(reader, start=2)
                if (transaction := self._parse(row, row_number)) is not None
            ]
        return [
            transaction
            for transaction in transactions
            if since is None or transaction.sold_at >= since
        ]

    @staticmethod
    def _parse(row: dict[str, str | None], row_number: int) -> RawTransaction | None:
        raw = {key.strip(): value for key, value in row.items()}
        if not any((value or "").strip() for value in raw.values()):
            return None
        values: dict[str, Any] = {
            key: value.strip() if value and value.strip() else None for key, value in raw.items()
        }
        try:
            for key in ("realized_price", "hammer_price", "buyer_premium"):
                if values.get(key) is not None:
                    values[key] = Decimal(values[key])
            values["raw_payload"] = raw
            return RawTransaction.model_validate(values)
        except (InvalidOperation, ValueError) as exc:
            raise AdapterDataError(f"auction row {row_number}: {exc}") from exc
