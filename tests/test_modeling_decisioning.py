from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import numpy as np

from wristalpha.decisioning.alerts import AlertCandidate, AlertEngine, undervalued_listing_alert
from wristalpha.decisioning.recommendations import Candidate, rank_recommendations
from wristalpha.modeling.backtest import (
    BacktestObservation,
    ValidationVerdict,
    walk_forward_backtest,
)
from wristalpha.modeling.forecasting import ForecastEstimate, ensemble_forecasts


class LinearRegressor:
    def __init__(self) -> None:
        self.weights = np.zeros(1)

    def fit(self, features: np.ndarray, targets: np.ndarray) -> None:
        self.weights = np.linalg.pinv(features) @ targets

    def predict(self, features: np.ndarray) -> np.ndarray:
        return features @ self.weights


def test_walk_forward_report_and_ensemble_are_explicit() -> None:
    observations = [
        BacktestObservation(
            as_of=date(2025, month, 1),
            reference_id=f"ref-{index}",
            features=(float(index), 1.0),
            forward_return=index * 0.01 + month * 0.001,
        )
        for month in range(1, 13)
        for index in range(5)
    ]
    report = walk_forward_backtest(observations, LinearRegressor, minimum_train_dates=5)
    assert report.observations > 0
    assert report.rank_ic > 0
    combined = ensemble_forecasts(
        [
            ForecastEstimate(0.1, -0.1, 0.1, 0.3, "a", {}),
            ForecastEstimate(0.2, 0.0, 0.2, 0.4, "b", {}),
        ]
    )
    assert np.isclose(combined.point, 0.15)


def _candidate(reference_id: str, expected: float) -> Candidate:
    return Candidate(
        reference_id=reference_id,
        brand="Example",
        family="Family",
        price=10_000,
        expected_gross_return=expected + 0.02,
        expected_net_return=expected,
        p10_net_return=expected - 0.1,
        p90_net_return=expected + 0.1,
        liquidity_score=0.8,
        time_to_exit_days=30,
        drivers=("momentum",),
        bear_case="Liquidity evaporates.",
    )


def test_recommendations_require_validation_and_known_costs() -> None:
    blocked = rank_recommendations(
        [_candidate("a", 0.1)],
        budget=20_000,
        minimum_liquidity=0.5,
        current_brand_counts={},
        maximum_brand_count=2,
        verdict=ValidationVerdict(False, "IC not significant"),
    )
    assert blocked.actionable is False
    result = rank_recommendations(
        [_candidate("a", 0.1), _candidate("b", 0.2)],
        budget=20_000,
        minimum_liquidity=0.5,
        current_brand_counts={},
        maximum_brand_count=2,
        verdict=ValidationVerdict(True, "validated"),
    )
    assert result.winner is not None
    assert result.winner.candidate.reference_id == "b"


def test_alerts_are_deduplicated_and_rate_limited() -> None:
    observed = datetime(2026, 1, 1, tzinfo=UTC)
    alert = undervalued_listing_alert(
        reference_id="ref",
        listing_id="listing",
        listing_price=80,
        fair_value=100,
        fair_value_standard_error=10,
        observed_at=observed,
    )
    assert alert is not None
    engine = AlertEngine(minimum_interval=timedelta(hours=1))
    assert engine.accept(alert)
    assert not engine.accept(alert)
    second = AlertCandidate("price_cut", "ref", observed, "cut", "warning")
    assert not engine.accept(second)
