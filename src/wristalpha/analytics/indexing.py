"""Hedonic time-dummy index with standard errors and thin-reference shrinkage."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np

from wristalpha.analytics.cleaning import CleanListing


@dataclass(frozen=True)
class IndexedListing:
    listing: CleanListing
    reference_id: str
    family: str


@dataclass(frozen=True)
class HedonicIndexPoint:
    reference_id: str
    month: date
    value: float
    standard_error: float
    listing_count: int
    confidence: float
    model_version: str = "hedonic-v1"


def _month(value: date) -> date:
    return date(value.year, value.month, 1)


def _design(rows: list[IndexedListing], months: list[date]) -> np.ndarray:
    columns: list[list[float]] = []
    for row in rows:
        item = row.listing
        vector = [1.0]
        vector.extend(
            1.0 if _month(item.fetched_at.date()) == month else 0.0 for month in months[1:]
        )
        vector.extend(
            [
                float(item.production_year or 0),
                1.0 if item.box else 0.0,
                1.0 if item.papers else 0.0,
                1.0 if (item.seller_type or "").casefold() == "dealer" else 0.0,
                1.0 if item.vat_included else 0.0,
            ]
        )
        columns.append(vector)
    matrix = np.asarray(columns, dtype=float)
    if matrix.size:
        years = matrix[:, len(months)]
        nonzero = years[years > 0]
        if nonzero.size:
            matrix[:, len(months)] = np.where(years > 0, years - nonzero.mean(), 0)
    return matrix


def build_hedonic_index(
    rows: list[IndexedListing],
    *,
    prior_strength: float = 8.0,
    minimum_observations: int = 6,
) -> list[HedonicIndexPoint]:
    usable = [row for row in rows if row.listing.outlier_reason is None]
    if len(usable) < minimum_observations:
        return []
    months = sorted({_month(row.listing.fetched_at.date()) for row in usable})
    if not months:
        return []
    design = _design(usable, months)
    response = np.log(np.asarray([float(row.listing.price) for row in usable]))
    beta = np.linalg.pinv(design) @ response
    residuals = response - design @ beta
    degrees = max(len(response) - design.shape[1], 1)
    variance = float(residuals @ residuals / degrees)
    covariance = variance * np.linalg.pinv(design.T @ design)
    time_coefficients = np.concatenate(([0.0], beta[1 : len(months)]))
    time_errors = np.concatenate(
        (
            [math.sqrt(max(covariance[0, 0], 0))],
            np.sqrt(np.maximum(np.diag(covariance)[1 : len(months)], 0)),
        )
    )
    family_values = np.exp(time_coefficients) * 100
    results: list[HedonicIndexPoint] = []
    references = sorted({row.reference_id for row in usable})
    for reference_id in references:
        reference_rows = [row for row in usable if row.reference_id == reference_id]
        for index, month in enumerate(months):
            count = sum(_month(row.listing.fetched_at.date()) == month for row in reference_rows)
            weight = count / (count + prior_strength)
            raw_relative = (
                np.mean(
                    [
                        float(row.listing.price)
                        for row in reference_rows
                        if _month(row.listing.fetched_at.date()) == month
                    ]
                )
                if count
                else family_values[index]
            )
            base_prices = [float(row.listing.price) for row in reference_rows]
            reference_relative = 100 * raw_relative / np.mean(base_prices) if base_prices else 100
            value = weight * reference_relative + (1 - weight) * family_values[index]
            results.append(
                HedonicIndexPoint(
                    reference_id=reference_id,
                    month=month,
                    value=float(value),
                    standard_error=float(time_errors[index]),
                    listing_count=count,
                    confidence=float(min(1.0, count / minimum_observations)),
                )
            )
    return results
