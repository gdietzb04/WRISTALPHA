"""Constrained next-purchase ranking with explicit blocking conditions."""

from __future__ import annotations

from dataclasses import dataclass

from wristalpha.modeling.backtest import ValidationVerdict


@dataclass(frozen=True)
class Candidate:
    reference_id: str
    brand: str
    family: str
    price: float
    expected_gross_return: float
    expected_net_return: float | None
    p10_net_return: float | None
    p90_net_return: float | None
    liquidity_score: float
    time_to_exit_days: float | None
    drivers: tuple[str, ...]
    bear_case: str


@dataclass(frozen=True)
class Recommendation:
    rank: int
    candidate: Candidate
    expected_return_per_capital: float


@dataclass(frozen=True)
class RecommendationResult:
    actionable: bool
    message: str
    winner: Recommendation | None
    shortlist: tuple[Recommendation, ...]


def rank_recommendations(
    candidates: list[Candidate],
    *,
    budget: float | None,
    minimum_liquidity: float,
    current_brand_counts: dict[str, int],
    maximum_brand_count: int,
    verdict: ValidationVerdict,
) -> RecommendationResult:
    if not verdict.actionable:
        return RecommendationResult(False, verdict.message, None, ())
    if budget is None or budget <= 0:
        return RecommendationResult(False, "Purchase budget is not configured.", None, ())
    if any(item.expected_net_return is None for item in candidates):
        return RecommendationResult(
            False,
            "Net costs are incomplete; recommendations remain disabled.",
            None,
            (),
        )
    eligible = [
        item
        for item in candidates
        if item.price <= budget
        and item.liquidity_score >= minimum_liquidity
        and current_brand_counts.get(item.brand, 0) < maximum_brand_count
    ]
    ordered = sorted(
        eligible,
        key=lambda item: float(item.expected_net_return or 0) / item.price,
        reverse=True,
    )[:10]
    recommendations = tuple(
        Recommendation(
            rank=index,
            candidate=item,
            expected_return_per_capital=float(item.expected_net_return or 0) / item.price,
        )
        for index, item in enumerate(ordered, start=1)
    )
    if not recommendations:
        return RecommendationResult(
            False, "No candidate satisfies portfolio constraints.", None, ()
        )
    return RecommendationResult(
        True, "Validated shortlist available.", recommendations[0], recommendations
    )
