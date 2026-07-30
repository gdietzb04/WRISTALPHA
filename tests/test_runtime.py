from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import wristalpha.api as api_module
from wristalpha.analytics.feature_store import persist_feature_row
from wristalpha.analytics.features import FeatureRow
from wristalpha.dashboard import DashboardSnapshot
from wristalpha.db import build_session_factory, session_scope
from wristalpha.models import Base, FeatureSnapshot
from wristalpha.operations.logging import configure_logging


class StubDashboard:
    def __init__(self, snapshot: DashboardSnapshot) -> None:
        self._snapshot = snapshot

    def snapshot(self) -> DashboardSnapshot:
        return self._snapshot


def test_feature_store_and_session_scope_enforce_point_in_time() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    row = FeatureRow(
        reference_id="11111111-1111-1111-1111-111111111111",
        as_of=now,
        maximum_source_ingested_at=now,
        feature_set_version="features-v1",
        values={"momentum_1m": 0.1},
    )
    with session_scope(factory) as session:
        persist_feature_row(session, row)
    with Session(engine) as session:
        stored = session.scalar(select(FeatureSnapshot))
        assert stored is not None
        assert stored.features["momentum_1m"] == 0.1
    invalid = FeatureRow(
        reference_id=str(uuid.uuid4()),
        as_of=now,
        maximum_source_ingested_at=datetime(2026, 1, 2, tzinfo=UTC),
        feature_set_version="features-v1",
        values={},
    )
    with Session(engine) as session, pytest.raises(ValueError, match="look-ahead"):
        persist_feature_row(session, invalid)


def test_structured_logging_and_overview_projection(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_logging("INFO")
    logging.getLogger("test").info("structured")
    assert '"message": "structured"' in capsys.readouterr().err
    snapshot = DashboardSnapshot(
        portfolio=[],
        forecasts=[],
        model_health={
            "status": "succeeded",
            "model_name": "ensemble",
            "model_version": "v1",
            "metrics": {"rank_ic": 0.1, "rank_ic_t_stat": 2.2},
            "started_at": "2026-01-01T00:00:00+00:00",
        },
        data_quality=[],
    )
    monkeypatch.setattr(api_module, "service", StubDashboard(snapshot))
    response = TestClient(api_module.app).get("/api/overview")
    assert response.status_code == 200
    assert response.json()["recommendations"]["actionable"] is True
