"""Purged expanding-window validation and statistical honesty verdict."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Protocol

import numpy as np


class Regressor(Protocol):
    def fit(self, features: np.ndarray, targets: np.ndarray) -> None: ...

    def predict(self, features: np.ndarray) -> np.ndarray: ...


@dataclass(frozen=True)
class BacktestObservation:
    as_of: date
    reference_id: str
    features: tuple[float, ...]
    forward_return: float


@dataclass(frozen=True)
class ValidationVerdict:
    actionable: bool
    message: str


@dataclass(frozen=True)
class BacktestReport:
    rank_ic: float
    ic_t_stat: float
    top_bottom_spread: float
    hit_rate: float
    mae: float
    rmse: float
    turnover: float
    observations: int
    verdict: ValidationVerdict


def _rank(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="stable")
    ranks = np.empty(len(values), dtype=float)
    ranks[order] = np.arange(len(values), dtype=float)
    return ranks


def _spearman(left: np.ndarray, right: np.ndarray) -> float:
    if len(left) < 2:
        return 0.0
    correlation = np.corrcoef(_rank(left), _rank(right))[0, 1]
    return float(correlation) if np.isfinite(correlation) else 0.0


def walk_forward_backtest(
    observations: list[BacktestObservation],
    model_factory: Callable[[], Regressor],
    *,
    minimum_train_dates: int = 12,
    purge_dates: int = 1,
    embargo_dates: int = 1,
) -> BacktestReport:
    dates = sorted({item.as_of for item in observations})
    predictions: list[float] = []
    outcomes: list[float] = []
    fold_ics: list[float] = []
    spreads: list[float] = []
    turnovers: list[float] = []
    previous_top: set[str] = set()
    for test_index in range(minimum_train_dates, len(dates) - embargo_dates):
        test_date = dates[test_index]
        train_cutoff = test_index - purge_dates
        train_dates = set(dates[:train_cutoff])
        train = [item for item in observations if item.as_of in train_dates]
        test = [item for item in observations if item.as_of == test_date]
        if len(train) < 20 or len(test) < 3:
            continue
        model = model_factory()
        x_train = np.asarray([item.features for item in train], dtype=float)
        y_train = np.asarray([item.forward_return for item in train], dtype=float)
        x_test = np.asarray([item.features for item in test], dtype=float)
        y_test = np.asarray([item.forward_return for item in test], dtype=float)
        model.fit(x_train, y_train)
        predicted = np.asarray(model.predict(x_test), dtype=float)
        predictions.extend(predicted.tolist())
        outcomes.extend(y_test.tolist())
        fold_ics.append(_spearman(predicted, y_test))
        group = max(1, len(test) // 10)
        order = np.argsort(predicted)
        spreads.append(float(np.mean(y_test[order[-group:]]) - np.mean(y_test[order[:group]])))
        current_top = {test[index].reference_id for index in order[-group:]}
        if previous_top:
            turnovers.append(1 - len(current_top & previous_top) / max(len(current_top), 1))
        previous_top = current_top
    predicted_array = np.asarray(predictions)
    outcome_array = np.asarray(outcomes)
    if not len(outcome_array):
        verdict = ValidationVerdict(
            False, "Insufficient walk-forward observations; rankings disabled."
        )
        return BacktestReport(0, 0, 0, 0, 0, 0, 0, 0, verdict)
    errors = predicted_array - outcome_array
    ic = float(np.mean(fold_ics)) if fold_ics else 0.0
    ic_standard_error = (
        float(np.std(fold_ics, ddof=1) / math.sqrt(len(fold_ics)))
        if len(fold_ics) > 1
        else math.inf
    )
    t_stat = ic / ic_standard_error if math.isfinite(ic_standard_error) and ic_standard_error else 0
    actionable = ic > 0 and t_stat >= 1.96
    verdict = ValidationVerdict(
        actionable,
        (
            "Out-of-sample rank IC is positive and statistically distinguishable from zero."
            if actionable
            else (
                "Out-of-sample rank IC is indistinguishable from zero; rankings are non-actionable."
            )
        ),
    )
    return BacktestReport(
        rank_ic=ic,
        ic_t_stat=t_stat,
        top_bottom_spread=float(np.mean(spreads)) if spreads else 0,
        hit_rate=float(np.mean(np.sign(predicted_array) == np.sign(outcome_array))),
        mae=float(np.mean(np.abs(errors))),
        rmse=float(np.sqrt(np.mean(errors**2))),
        turnover=float(np.mean(turnovers)) if turnovers else 0,
        observations=len(outcome_array),
        verdict=verdict,
    )
