"""Read-only dashboard projection over point-in-time database records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, desc, select
from sqlalchemy.orm import Session

from wristalpha.models import DataQualityCheck, Forecast, Holding, ModelRun


@dataclass(frozen=True)
class DashboardSnapshot:
    portfolio: list[dict[str, Any]]
    forecasts: list[dict[str, Any]]
    model_health: dict[str, Any]
    data_quality: list[dict[str, Any]]


class SqlDashboardService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def snapshot(self) -> DashboardSnapshot:
        with Session(self._engine) as session:
            holdings = session.scalars(select(Holding).order_by(desc(Holding.as_of))).all()
            forecasts = session.scalars(
                select(Forecast).order_by(desc(Forecast.as_of)).limit(100)
            ).all()
            latest_run = session.scalar(
                select(ModelRun).order_by(desc(ModelRun.started_at)).limit(1)
            )
            checks = session.scalars(
                select(DataQualityCheck).order_by(desc(DataQualityCheck.as_of)).limit(20)
            ).all()
        return DashboardSnapshot(
            portfolio=[
                {
                    "reference": item.reference_text,
                    "model": item.model_name,
                    "purchase_price": float(item.purchase_price),
                    "currency": item.purchase_currency,
                    "mark": (
                        float(item.illiquidity_adjusted_mark)
                        if item.illiquidity_adjusted_mark is not None
                        else None
                    ),
                    "as_of": item.as_of.isoformat(),
                }
                for item in holdings
            ],
            forecasts=[
                {
                    "reference_id": str(item.reference_id),
                    "horizon": item.horizon,
                    "basis": item.return_basis,
                    "point": float(item.point),
                    "p10": float(item.p10),
                    "p50": float(item.p50),
                    "p90": float(item.p90),
                    "model_version": item.model_version,
                    "as_of": item.as_of.isoformat(),
                }
                for item in forecasts
            ],
            model_health=(
                {
                    "status": latest_run.status,
                    "model_name": latest_run.model_name,
                    "model_version": latest_run.model_version,
                    "metrics": latest_run.metrics,
                    "started_at": latest_run.started_at.isoformat(),
                }
                if latest_run is not None
                else {
                    "status": "not_run",
                    "model_name": None,
                    "model_version": None,
                    "metrics": None,
                    "started_at": None,
                }
            ),
            data_quality=[
                {
                    "name": item.check_name,
                    "passed": item.passed,
                    "severity": item.severity,
                    "details": item.details,
                    "as_of": item.as_of.isoformat(),
                }
                for item in checks
            ],
        )
