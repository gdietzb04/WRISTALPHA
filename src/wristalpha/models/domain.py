"""Point-in-time relational schema for WRISTALPHA."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wristalpha.models.base import Base, PointInTimeMixin

JsonObject = dict[str, Any]
JsonArray = list[JsonObject]


class Brand(PointInTimeMixin, Base):
    __tablename__ = "brand"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)

    references: Mapped[list[WatchReference]] = relationship(back_populates="brand")

    __table_args__ = (
        UniqueConstraint("name", "as_of", name="uq_brand_name_as_of"),
        UniqueConstraint("slug", "as_of", name="uq_brand_slug_as_of"),
    )


class WatchReference(PointInTimeMixin, Base):
    __tablename__ = "watch_reference"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brand.id"), nullable=False)
    canonical_reference: Mapped[str] = mapped_column(String(120), nullable=False)
    family: Mapped[str] = mapped_column(String(160), nullable=False)
    material: Mapped[str | None] = mapped_column(String(120))
    complication: Mapped[str | None] = mapped_column(String(240))
    case_size_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    movement: Mapped[str | None] = mapped_column(String(160))
    retail_price_history: Mapped[JsonArray] = mapped_column(JSON, default=list, nullable=False)
    production_start_year: Mapped[int | None] = mapped_column(SmallInteger)
    production_end_year: Mapped[int | None] = mapped_column(SmallInteger)
    discontinued: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    brand: Mapped[Brand] = relationship(back_populates="references")
    listings: Mapped[list[Listing]] = relationship(back_populates="reference")
    transactions: Mapped[list[Transaction]] = relationship(back_populates="reference")

    __table_args__ = (
        UniqueConstraint(
            "brand_id",
            "canonical_reference",
            "as_of",
            name="uq_watch_reference_brand_ref_as_of",
        ),
        CheckConstraint(
            "production_end_year IS NULL OR production_start_year IS NULL "
            "OR production_end_year >= production_start_year",
            name="production_year_order",
        ),
    )


class Listing(PointInTimeMixin, Base):
    __tablename__ = "listing"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("watch_reference.id"))
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    external_id: Mapped[str] = mapped_column(String(240), nullable=False)
    adapter_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delisted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delisting_probability: Mapped[Decimal | None] = mapped_column(Numeric(8, 7))
    raw_payload: Mapped[JsonObject] = mapped_column(JSON, nullable=False)
    raw_payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    raw_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    raw_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    cleaned_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    cleaned_currency: Mapped[str | None] = mapped_column(String(3))
    production_year: Mapped[int | None] = mapped_column(SmallInteger)
    condition: Mapped[str | None] = mapped_column(String(120))
    box: Mapped[bool | None] = mapped_column(Boolean)
    papers: Mapped[bool | None] = mapped_column(Boolean)
    seller_type: Mapped[str | None] = mapped_column(String(80))
    seller_country: Mapped[str | None] = mapped_column(String(2))
    vat_included: Mapped[bool | None] = mapped_column(Boolean)
    warranty_remaining_months: Mapped[int | None] = mapped_column(SmallInteger)
    service_history: Mapped[str | None] = mapped_column(Text)
    resolution_confidence: Mapped[Decimal | None] = mapped_column(Numeric(8, 7))
    price_history: Mapped[JsonArray] = mapped_column(JSON, default=list, nullable=False)
    outlier_reason: Mapped[str | None] = mapped_column(Text)

    reference: Mapped[WatchReference | None] = relationship(back_populates="listings")

    __table_args__ = (
        UniqueConstraint("source", "external_id", "as_of", name="uq_listing_source_id_as_of"),
        CheckConstraint("raw_price > 0", name="raw_price_positive"),
        CheckConstraint(
            "cleaned_price IS NULL OR cleaned_price > 0",
            name="cleaned_price_positive",
        ),
        CheckConstraint(
            "delisting_probability IS NULL OR "
            "(delisting_probability >= 0 AND delisting_probability <= 1)",
            name="delisting_probability_range",
        ),
        CheckConstraint(
            "resolution_confidence IS NULL OR "
            "(resolution_confidence >= 0 AND resolution_confidence <= 1)",
            name="resolution_confidence_range",
        ),
        CheckConstraint("last_seen >= first_seen", name="seen_timestamp_order"),
        Index("ix_listing_reference_as_of", "reference_id", "as_of"),
    )


class Transaction(PointInTimeMixin, Base):
    __tablename__ = "transaction"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("watch_reference.id"))
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    external_id: Mapped[str] = mapped_column(String(240), nullable=False)
    auction_house: Mapped[str | None] = mapped_column(String(160))
    sale_name: Mapped[str | None] = mapped_column(String(240))
    lot_number: Mapped[str | None] = mapped_column(String(80))
    sold_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hammer_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    buyer_premium: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    realized_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[JsonObject] = mapped_column(JSON, nullable=False)
    raw_payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    reference: Mapped[WatchReference | None] = relationship(back_populates="transactions")

    __table_args__ = (
        UniqueConstraint("source", "external_id", "as_of", name="uq_transaction_source_id_as_of"),
        CheckConstraint("realized_price > 0", name="realized_price_positive"),
        CheckConstraint(
            "hammer_price IS NULL OR hammer_price > 0",
            name="hammer_price_positive",
        ),
    )


class PriceIndex(PointInTimeMixin, Base):
    __tablename__ = "price_index"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reference_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("watch_reference.id"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    hedonic_index: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    standard_error: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    listing_count: Mapped[int] = mapped_column(Integer, nullable=False)
    median_days_on_market: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    confidence: Mapped[Decimal] = mapped_column(Numeric(8, 7), nullable=False)
    model_version: Mapped[str] = mapped_column(String(120), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "reference_id",
            "date",
            "model_version",
            "as_of",
            name="uq_price_index_ref_date_model_as_of",
        ),
        CheckConstraint("hedonic_index > 0", name="hedonic_index_positive"),
        CheckConstraint("volume >= 0", name="volume_nonnegative"),
        CheckConstraint("listing_count >= 0", name="listing_count_nonnegative"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
    )


class FeatureSnapshot(PointInTimeMixin, Base):
    __tablename__ = "feature_snapshot"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reference_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("watch_reference.id"), nullable=False
    )
    feature_set_version: Mapped[str] = mapped_column(String(120), nullable=False)
    features: Mapped[JsonObject] = mapped_column(JSON, nullable=False)
    maximum_source_ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "reference_id",
            "feature_set_version",
            "as_of",
            name="uq_feature_snapshot_ref_version_as_of",
        ),
        CheckConstraint(
            "maximum_source_ingested_at <= as_of",
            name="no_lookahead",
        ),
    )


class Forecast(PointInTimeMixin, Base):
    __tablename__ = "forecast"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reference_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("watch_reference.id"), nullable=False
    )
    horizon: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    return_basis: Mapped[str] = mapped_column(String(12), nullable=False)
    point: Mapped[Decimal] = mapped_column(Numeric(16, 9), nullable=False)
    p10: Mapped[Decimal] = mapped_column(Numeric(16, 9), nullable=False)
    p50: Mapped[Decimal] = mapped_column(Numeric(16, 9), nullable=False)
    p90: Mapped[Decimal] = mapped_column(Numeric(16, 9), nullable=False)
    model_version: Mapped[str] = mapped_column(String(120), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "reference_id",
            "horizon",
            "return_basis",
            "model_version",
            "as_of",
            name="uq_forecast_ref_horizon_basis_model_as_of",
        ),
        CheckConstraint("horizon IN (3, 6, 12, 36)", name="supported_horizon"),
        CheckConstraint("return_basis IN ('gross', 'net')", name="return_basis"),
        CheckConstraint("p10 <= p50 AND p50 <= p90", name="quantile_order"),
    )


class Holding(PointInTimeMixin, Base):
    __tablename__ = "holding"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("watch_reference.id"))
    model_name: Mapped[str] = mapped_column(String(240), nullable=False)
    reference_text: Mapped[str] = mapped_column(String(120), nullable=False)
    production_year: Mapped[int | None] = mapped_column(SmallInteger)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    purchase_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    condition: Mapped[str | None] = mapped_column(String(120))
    box: Mapped[bool | None] = mapped_column(Boolean)
    papers: Mapped[bool | None] = mapped_column(Boolean)
    marked_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    illiquidity_adjusted_mark: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    mark_model_version: Mapped[str | None] = mapped_column(String(120))

    __table_args__ = (
        CheckConstraint("purchase_price > 0", name="purchase_price_positive"),
        CheckConstraint("marked_price IS NULL OR marked_price > 0", name="marked_price_positive"),
        CheckConstraint(
            "illiquidity_adjusted_mark IS NULL OR illiquidity_adjusted_mark > 0",
            name="illiquidity_mark_positive",
        ),
    )


class Alert(PointInTimeMixin, Base):
    __tablename__ = "alert"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("watch_reference.id"))
    listing_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("listing.id"))
    alert_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(240), nullable=False)
    payload: Mapped[JsonObject] = mapped_column(JSON, nullable=False)
    fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("dedupe_key", "as_of", name="uq_alert_dedupe_as_of"),
        CheckConstraint(
            "alert_type IN ('undervalued_listing', 'price_cut', 'momentum_breakout', "
            "'momentum_breakdown', 'regime_shift', 'data_quality')",
            name="alert_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'sent', 'suppressed', 'failed')",
            name="alert_status",
        ),
    )


class ModelRun(PointInTimeMixin, Base):
    __tablename__ = "model_run"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)
    model_version: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parameters: Mapped[JsonObject] = mapped_column(JSON, nullable=False)
    metrics: Mapped[JsonObject | None] = mapped_column(JSON)
    artifact_uri: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'blocked')",
            name="model_run_status",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="model_run_timestamp_order",
        ),
    )


class DataQualityCheck(PointInTimeMixin, Base):
    __tablename__ = "data_quality_check"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    check_name: Mapped[str] = mapped_column(String(160), nullable=False)
    scope: Mapped[str] = mapped_column(String(240), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    severity: Mapped[str] = mapped_column(String(24), nullable=False)
    observed_value: Mapped[JsonObject | None] = mapped_column(JSON)
    expected_value: Mapped[JsonObject | None] = mapped_column(JSON)
    details: Mapped[str | None] = mapped_column(Text)
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("model_run.id"))

    __table_args__ = (
        CheckConstraint(
            "severity IN ('info', 'warning', 'error', 'blocking')",
            name="data_quality_severity",
        ),
        Index("ix_data_quality_check_name_as_of", "check_name", "as_of"),
    )
