"""Point-in-time feature snapshot persistence boundary."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from wristalpha.analytics.features import FeatureRow
from wristalpha.models import FeatureSnapshot


def persist_feature_row(session: Session, row: FeatureRow) -> FeatureSnapshot:
    if row.maximum_source_ingested_at > row.as_of:
        raise ValueError("look-ahead detected before feature persistence")
    payload = dict(row.values.items())
    snapshot = FeatureSnapshot(
        id=uuid.uuid4(),
        reference_id=uuid.UUID(row.reference_id),
        feature_set_version=row.feature_set_version,
        features=payload,
        maximum_source_ingested_at=row.maximum_source_ingested_at,
        as_of=row.as_of,
    )
    session.add(snapshot)
    return snapshot
