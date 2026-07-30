"""FastAPI read surface for statistically honest WRISTALPHA research."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from wristalpha import __version__
from wristalpha.config import RuntimeSettings
from wristalpha.dashboard import DashboardSnapshot, SqlDashboardService
from wristalpha.db import build_engine


class HealthResponse(TypedDict):
    status: Literal["ok"]
    version: str


settings = RuntimeSettings()
service = SqlDashboardService(build_engine(settings))
app = FastAPI(
    title="WRISTALPHA",
    version=__version__,
    description="Local-first luxury-watch research; estimates are not investment advice.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> HealthResponse:
    return {"status": "ok", "version": __version__}


def _snapshot() -> DashboardSnapshot:
    try:
        return service.snapshot()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable or not migrated; see the local runbook.",
        ) from exc


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    snapshot = _snapshot()
    metrics = snapshot.model_health.get("metrics")
    actionable = bool(
        isinstance(metrics, dict)
        and metrics.get("rank_ic_t_stat") is not None
        and float(metrics["rank_ic_t_stat"]) >= 1.96
        and float(metrics.get("rank_ic", 0)) > 0
    )
    return {
        "portfolio": snapshot.portfolio,
        "forecasts": snapshot.forecasts,
        "model_health": snapshot.model_health,
        "data_quality": snapshot.data_quality,
        "recommendations": {
            "actionable": actionable,
            "message": (
                "Validated rankings are available."
                if actionable
                else "Rankings are disabled until out-of-sample IC is statistically significant."
            ),
            "items": [],
        },
        "disclaimer": (
            "Statistical estimates derived from biased marketplace asks; not investment advice."
        ),
    }
