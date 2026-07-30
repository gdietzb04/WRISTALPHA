"""Three-model forecast stack with explicit uncertainty."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from arch import arch_model
from lightgbm import LGBMRegressor
from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression
from statsmodels.tsa.statespace.sarimax import SARIMAX


class ModelNotReadyError(RuntimeError):
    """Raised when statistical minimums are not satisfied."""


@dataclass(frozen=True)
class ForecastEstimate:
    point: float
    p10: float
    p50: float
    p90: float
    model_version: str
    diagnostics: dict[str, float | str]


class CrossSectionalRanker:
    """LightGBM expected-return ranker."""

    def __init__(self, *, random_state: int = 17) -> None:
        self._model = LGBMRegressor(
            n_estimators=120,
            learning_rate=0.03,
            num_leaves=15,
            min_child_samples=10,
            random_state=random_state,
            verbosity=-1,
        )

    def fit(self, features: np.ndarray, targets: np.ndarray) -> None:
        if len(targets) < 30:
            raise ModelNotReadyError("ranking model requires at least 30 observations")
        self._model.fit(features, targets)

    def predict(self, features: np.ndarray) -> np.ndarray:
        prediction = self._model.predict(features)
        return np.asarray(prediction, dtype=float)


class TimeSeriesForecaster:
    """ARIMA/state-space point forecast with EGARCH conditional volatility."""

    def forecast(self, returns: np.ndarray, *, steps: int) -> ForecastEstimate:
        clean = np.asarray(returns, dtype=float)
        clean = clean[np.isfinite(clean)]
        if len(clean) < 24:
            raise ModelNotReadyError("time-series model requires at least 24 returns")
        arima = SARIMAX(
            clean,
            order=(1, 0, 0),
            trend="c",
            enforce_stationarity=True,
            enforce_invertibility=True,
        ).fit(disp=False)
        point = float(np.sum(arima.forecast(steps=steps)))
        egarch = arch_model(
            clean * 100,
            mean="Zero",
            vol="EGARCH",
            p=1,
            o=1,
            q=1,
            dist="t",
            rescale=False,
        ).fit(disp="off")
        variance = float(np.sum(egarch.forecast(horizon=steps).variance.values[-1])) / 10_000
        sigma = math.sqrt(max(variance, 1e-12))
        return ForecastEstimate(
            point=point,
            p10=point - 1.2816 * sigma,
            p50=point,
            p90=point + 1.2816 * sigma,
            model_version="arima-egarch-v1",
            diagnostics={"conditional_volatility": sigma},
        )


class RegimeForecaster:
    """Three-state hidden Markov regime model on aggregate market returns."""

    def forecast(self, returns: np.ndarray) -> ForecastEstimate:
        clean = np.asarray(returns, dtype=float)
        clean = clean[np.isfinite(clean)]
        if len(clean) < 36:
            raise ModelNotReadyError("regime model requires at least 36 returns")
        result = MarkovRegression(
            clean,
            k_regimes=3,
            trend="c",
            switching_variance=True,
        ).fit(disp=False)
        probabilities = np.asarray(result.smoothed_marginal_probabilities)[-1]
        regime_means = np.asarray(
            [result.params[index] for index in range(3)],
            dtype=float,
        )
        point = float(probabilities @ regime_means)
        sigma = float(np.std(clean, ddof=1))
        regime = int(np.argmax(probabilities))
        return ForecastEstimate(
            point=point,
            p10=point - 1.2816 * sigma,
            p50=point,
            p90=point + 1.2816 * sigma,
            model_version="markov-regime-v1",
            diagnostics={
                "regime": float(regime),
                "regime_probability": float(probabilities[regime]),
            },
        )


def ensemble_forecasts(
    estimates: list[ForecastEstimate],
    *,
    weights: list[float] | None = None,
) -> ForecastEstimate:
    if not estimates:
        raise ModelNotReadyError("ensemble requires at least one validated estimate")
    chosen = np.asarray(weights or [1 / len(estimates)] * len(estimates), dtype=float)
    if len(chosen) != len(estimates) or np.any(chosen < 0) or chosen.sum() <= 0:
        raise ValueError("ensemble weights must be non-negative and match estimates")
    chosen = chosen / chosen.sum()
    return ForecastEstimate(
        point=float(chosen @ np.asarray([item.point for item in estimates])),
        p10=float(chosen @ np.asarray([item.p10 for item in estimates])),
        p50=float(chosen @ np.asarray([item.p50 for item in estimates])),
        p90=float(chosen @ np.asarray([item.p90 for item in estimates])),
        model_version="ensemble-v1",
        diagnostics={"component_count": float(len(estimates))},
    )
