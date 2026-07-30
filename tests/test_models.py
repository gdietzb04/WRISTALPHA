import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from wristalpha.models import Base, FeatureSnapshot

REQUIRED_TABLES = {
    "brand",
    "watch_reference",
    "listing",
    "transaction",
    "price_index",
    "feature_snapshot",
    "forecast",
    "holding",
    "alert",
    "model_run",
    "data_quality_check",
}


def test_minimum_tables_have_point_in_time_columns() -> None:
    assert set(Base.metadata.tables) >= REQUIRED_TABLES
    for table_name in REQUIRED_TABLES:
        columns = Base.metadata.tables[table_name].columns
        assert "as_of" in columns
        assert "ingested_at" in columns


def test_feature_snapshot_database_constraint_blocks_lookahead() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    feature_time = datetime(2026, 1, 1, tzinfo=UTC)

    with Session(engine) as session:
        session.add(
            FeatureSnapshot(
                reference_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
                feature_set_version="test-v1",
                features={"momentum_1m": 0.1},
                maximum_source_ingested_at=datetime(2026, 1, 2, tzinfo=UTC),
                as_of=feature_time,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
