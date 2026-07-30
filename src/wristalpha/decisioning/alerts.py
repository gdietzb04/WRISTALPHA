"""Alert detection, deduplication, and per-reference rate limiting."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class AlertCandidate:
    alert_type: str
    reference_id: str
    observed_at: datetime
    message: str
    severity: str
    listing_id: str | None = None

    @property
    def dedupe_key(self) -> str:
        raw = f"{self.alert_type}|{self.reference_id}|{self.listing_id or ''}|{self.message}"
        return hashlib.sha256(raw.encode()).hexdigest()


class AlertEngine:
    def __init__(self, *, minimum_interval: timedelta = timedelta(hours=24)) -> None:
        self._minimum_interval = minimum_interval
        self._seen: set[str] = set()
        self._last_by_reference: dict[str, datetime] = {}

    def accept(self, candidate: AlertCandidate) -> bool:
        if candidate.observed_at.tzinfo is None:
            raise ValueError("alert observed_at must be timezone-aware")
        if candidate.dedupe_key in self._seen:
            return False
        last = self._last_by_reference.get(candidate.reference_id)
        if last is not None and candidate.observed_at - last < self._minimum_interval:
            return False
        self._seen.add(candidate.dedupe_key)
        self._last_by_reference[candidate.reference_id] = candidate.observed_at
        return True


def undervalued_listing_alert(
    *,
    reference_id: str,
    listing_id: str,
    listing_price: float,
    fair_value: float,
    fair_value_standard_error: float,
    observed_at: datetime,
    z_threshold: float = -2.0,
) -> AlertCandidate | None:
    if fair_value_standard_error <= 0:
        return None
    z_score = (listing_price - fair_value) / fair_value_standard_error
    if z_score > z_threshold:
        return None
    return AlertCandidate(
        alert_type="undervalued_listing",
        reference_id=reference_id,
        listing_id=listing_id,
        observed_at=observed_at,
        message=f"Listing is {z_score:.2f} standard errors below modeled fair value.",
        severity="warning",
    )
