"""Typed acquisition boundaries shared by marketplace adapters."""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return FrozenDict({str(key): _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, FrozenDict):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


class FrozenDict(Mapping[str, Any]):
    """Small immutable mapping used for acquisition payloads."""

    def __init__(self, values: Mapping[str, Any]) -> None:
        self._values = dict(values)

    def __getitem__(self, key: str) -> Any:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def to_plain(self) -> dict[str, Any]:
        return {key: _thaw_json(value) for key, value in self._values.items()}


class AdapterError(RuntimeError):
    """Base class for expected acquisition failures."""


class AdapterConfigurationError(AdapterError):
    """Raised when an adapter lacks licensed or user-supplied configuration."""


class AdapterDataError(AdapterError):
    """Raised when source data violates the declared adapter contract."""


class MarketplaceQuery(BaseModel):
    """Conservative, source-independent listing filters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    brands: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    maximum_price: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class RawListing(BaseModel):
    """Immutable listing observation exactly as represented at acquisition time."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    source: str = Field(min_length=1, max_length=120)
    external_id: str = Field(min_length=1, max_length=240)
    fetched_at: datetime
    title: str = Field(min_length=1)
    price: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    url: HttpUrl
    brand: str | None = None
    reference_hint: str | None = None
    production_year: int | None = Field(default=None, ge=1800, le=2200)
    condition: str | None = None
    box: bool | None = None
    papers: bool | None = None
    seller_type: str | None = None
    seller_country: str | None = Field(default=None, min_length=2, max_length=2)
    vat_included: bool | None = None
    warranty_remaining_months: int | None = Field(default=None, ge=0)
    service_history: str | None = None
    description: str | None = None
    raw_payload: FrozenDict

    @field_validator("raw_payload", mode="before")
    @classmethod
    def freeze_raw_payload(cls, value: Any) -> FrozenDict:
        if not isinstance(value, Mapping):
            raise ValueError("raw_payload must be a mapping")
        frozen = _freeze_json(value)
        if not isinstance(frozen, FrozenDict):
            raise ValueError("raw_payload must be a mapping")
        return frozen

    @field_validator("fetched_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("fetched_at must include a UTC offset")
        return value

    @field_validator("currency")
    @classmethod
    def uppercase_listing_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("seller_country")
    @classmethod
    def uppercase_country(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None

    @property
    def raw_payload_sha256(self) -> str:
        """Return a stable digest used to prove that raw content did not change."""

        canonical = json.dumps(
            self.raw_payload.to_plain(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class MarketplaceAdapter(ABC):
    """Only supported listing acquisition interface."""

    @abstractmethod
    def fetch_listings(
        self,
        query: MarketplaceQuery,
        since: datetime | None,
    ) -> list[RawListing]:
        """Fetch observations at or after since without cleaning them."""
