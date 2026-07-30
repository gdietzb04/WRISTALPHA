"""Point-in-time feature engineering from validated index/listing histories."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from wristalpha.analytics.cleaning import CleanListing
from wristalpha.analytics.indexing import HedonicIndexPoint


@dataclass(frozen=True)
class MacroObservation:
    name: str
    value: float
    as_of: datetime
    ingested_at: datetime
    source: str


@dataclass(frozen=True)
class FeatureRow:
    reference_id: str
    as_of: datetime
    maximum_source_ingested_at: datetime
    feature_set_version: str
    values: dict[str, float | None]


def _return(values: list[float], periods: int) -> float | None:
    if len(values) <= periods or values[-periods - 1] <= 0:
        return None
    return values[-1] / values[-periods - 1] - 1


def build_feature_row(
    *,
    reference_id: str,
    as_of: datetime,
    maximum_source_ingested_at: datetime,
    index_history: list[HedonicIndexPoint],
    listings: list[CleanListing],
    retail_price: float | None,
    brand_factor_return: float | None,
    macro: list[MacroObservation],
) -> FeatureRow:
    if maximum_source_ingested_at > as_of:
        raise ValueError("look-ahead detected: source ingestion exceeds feature as-of")
    if any(item.ingested_at > as_of or item.as_of > as_of for item in macro):
        raise ValueError("look-ahead detected in macro observations")
    history = sorted(
        (point for point in index_history if point.reference_id == reference_id),
        key=lambda point: point.month,
    )
    values = [point.value for point in history]
    returns = np.diff(np.log(np.asarray(values, dtype=float))) if len(values) > 1 else np.array([])
    active = [item for item in listings if item.fetched_at <= as_of]
    current_index = values[-1] if values else None
    price_cuts = [item.price_cut_fraction for item in active if item.price_cut_fraction is not None]
    features: dict[str, float | None] = {
        "momentum_1m": _return(values, 1),
        "momentum_3m": _return(values, 3),
        "momentum_6m": _return(values, 6),
        "momentum_12m": _return(values, 12),
        "realized_volatility": (
            float(np.std(returns, ddof=1) * math.sqrt(12)) if len(returns) > 1 else None
        ),
        "listing_count": float(len(active)),
        "median_days_on_market": (
            float(np.median([item.days_on_market for item in active])) if active else None
        ),
        "bid_ask_proxy": float(np.mean(price_cuts)) if price_cuts else None,
        "premium_to_retail": (
            current_index / retail_price - 1
            if current_index is not None and retail_price is not None and retail_price > 0
            else None
        ),
        "brand_factor_return": brand_factor_return,
    }
    for item in macro:
        features[f"macro_{item.name}"] = item.value
    return FeatureRow(
        reference_id=reference_id,
        as_of=as_of,
        maximum_source_ingested_at=maximum_source_ingested_at,
        feature_set_version="features-v1",
        values=features,
    )
