"""Data-quality checks that fail the analytical pipeline closed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from wristalpha.analytics.cleaning import CleanListing


@dataclass(frozen=True)
class QualityResult:
    name: str
    passed: bool
    severity: str
    details: str


def run_quality_checks(
    listings: list[CleanListing],
    *,
    as_of: datetime,
    maximum_source_ingested_at: datetime,
) -> list[QualityResult]:
    if as_of.tzinfo is None or maximum_source_ingested_at.tzinfo is None:
        raise ValueError("quality timestamps must be timezone-aware")
    return [
        QualityResult(
            "no_lookahead",
            maximum_source_ingested_at <= as_of,
            "blocking",
            "No source ingestion timestamp may exceed the feature as-of time.",
        ),
        QualityResult(
            "positive_prices",
            all(item.price > 0 for item in listings),
            "blocking",
            "Every cleaned listing must have a positive price.",
        ),
        QualityResult(
            "currency_present",
            all(len(item.currency) == 3 for item in listings),
            "error",
            "Every listing must carry a three-letter currency.",
        ),
        QualityResult(
            "outlier_rate",
            (
                sum(item.outlier_reason is not None for item in listings) / len(listings) <= 0.1
                if listings
                else True
            ),
            "warning",
            "More than ten percent of rows were marked as outliers.",
        ),
    ]
