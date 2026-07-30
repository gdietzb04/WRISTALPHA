"""Create the P1 point-in-time core schema.

Revision ID: 0001_p1
Revises:
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_p1"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id_column() -> sa.Column[object]:
    return sa.Column(
        "id",
        sa.Uuid(),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def _point_in_time_columns() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def _point_in_time_indexes(table_name: str) -> None:
    op.create_index(f"ix_{table_name}_as_of", table_name, ["as_of"])
    op.create_index(f"ix_{table_name}_ingested_at", table_name, ["ingested_at"])


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    op.create_table(
        "brand",
        _id_column(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        *_point_in_time_columns(),
        sa.UniqueConstraint("name", "as_of", name="uq_brand_name_as_of"),
        sa.UniqueConstraint("slug", "as_of", name="uq_brand_slug_as_of"),
    )
    _point_in_time_indexes("brand")

    op.create_table(
        "watch_reference",
        _id_column(),
        sa.Column("brand_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_reference", sa.String(120), nullable=False),
        sa.Column("family", sa.String(160), nullable=False),
        sa.Column("material", sa.String(120)),
        sa.Column("complication", sa.String(240)),
        sa.Column("case_size_mm", sa.Numeric(6, 2)),
        sa.Column("movement", sa.String(160)),
        sa.Column("retail_price_history", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("production_start_year", sa.SmallInteger()),
        sa.Column("production_end_year", sa.SmallInteger()),
        sa.Column("discontinued", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_point_in_time_columns(),
        sa.ForeignKeyConstraint(
            ["brand_id"],
            ["brand.id"],
            name="fk_watch_reference_brand_id_brand",
        ),
        sa.UniqueConstraint(
            "brand_id",
            "canonical_reference",
            "as_of",
            name="uq_watch_reference_brand_ref_as_of",
        ),
        sa.CheckConstraint(
            "production_end_year IS NULL OR production_start_year IS NULL "
            "OR production_end_year >= production_start_year",
            name=op.f("ck_watch_reference_production_year_order"),
        ),
    )
    _point_in_time_indexes("watch_reference")

    op.create_table(
        "listing",
        _id_column(),
        sa.Column("reference_id", sa.Uuid()),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("external_id", sa.String(240), nullable=False),
        sa.Column("adapter_type", sa.String(40), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delisted_at", sa.DateTime(timezone=True)),
        sa.Column("delisting_probability", sa.Numeric(8, 7)),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("raw_payload_sha256", sa.String(64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("raw_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("raw_currency", sa.String(3), nullable=False),
        sa.Column("cleaned_price", sa.Numeric(18, 2)),
        sa.Column("cleaned_currency", sa.String(3)),
        sa.Column("production_year", sa.SmallInteger()),
        sa.Column("condition", sa.String(120)),
        sa.Column("box", sa.Boolean()),
        sa.Column("papers", sa.Boolean()),
        sa.Column("seller_type", sa.String(80)),
        sa.Column("seller_country", sa.String(2)),
        sa.Column("vat_included", sa.Boolean()),
        sa.Column("warranty_remaining_months", sa.SmallInteger()),
        sa.Column("service_history", sa.Text()),
        sa.Column("resolution_confidence", sa.Numeric(8, 7)),
        sa.Column("price_history", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("outlier_reason", sa.Text()),
        *_point_in_time_columns(),
        sa.ForeignKeyConstraint(
            ["reference_id"],
            ["watch_reference.id"],
            name="fk_listing_reference_id_watch_reference",
        ),
        sa.UniqueConstraint(
            "source",
            "external_id",
            "as_of",
            name="uq_listing_source_id_as_of",
        ),
        sa.CheckConstraint("raw_price > 0", name=op.f("ck_listing_raw_price_positive")),
        sa.CheckConstraint(
            "cleaned_price IS NULL OR cleaned_price > 0",
            name=op.f("ck_listing_cleaned_price_positive"),
        ),
        sa.CheckConstraint(
            "delisting_probability IS NULL OR "
            "(delisting_probability >= 0 AND delisting_probability <= 1)",
            name=op.f("ck_listing_delisting_probability_range"),
        ),
        sa.CheckConstraint(
            "resolution_confidence IS NULL OR "
            "(resolution_confidence >= 0 AND resolution_confidence <= 1)",
            name=op.f("ck_listing_resolution_confidence_range"),
        ),
        sa.CheckConstraint(
            "last_seen >= first_seen",
            name=op.f("ck_listing_seen_timestamp_order"),
        ),
    )
    _point_in_time_indexes("listing")
    op.create_index("ix_listing_reference_as_of", "listing", ["reference_id", "as_of"])

    op.create_table(
        "transaction",
        _id_column(),
        sa.Column("reference_id", sa.Uuid()),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("external_id", sa.String(240), nullable=False),
        sa.Column("auction_house", sa.String(160)),
        sa.Column("sale_name", sa.String(240)),
        sa.Column("lot_number", sa.String(80)),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hammer_price", sa.Numeric(18, 2)),
        sa.Column("buyer_premium", sa.Numeric(18, 2)),
        sa.Column("realized_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_url", sa.Text()),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("raw_payload_sha256", sa.String(64), nullable=False),
        *_point_in_time_columns(),
        sa.ForeignKeyConstraint(
            ["reference_id"],
            ["watch_reference.id"],
            name="fk_transaction_reference_id_watch_reference",
        ),
        sa.UniqueConstraint(
            "source",
            "external_id",
            "as_of",
            name="uq_transaction_source_id_as_of",
        ),
        sa.CheckConstraint(
            "realized_price > 0",
            name=op.f("ck_transaction_realized_price_positive"),
        ),
        sa.CheckConstraint(
            "hammer_price IS NULL OR hammer_price > 0",
            name=op.f("ck_transaction_hammer_price_positive"),
        ),
    )
    _point_in_time_indexes("transaction")

    op.create_table(
        "price_index",
        _id_column(),
        sa.Column("reference_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("hedonic_index", sa.Numeric(20, 8), nullable=False),
        sa.Column("standard_error", sa.Numeric(20, 8)),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("listing_count", sa.Integer(), nullable=False),
        sa.Column("median_days_on_market", sa.Numeric(12, 3)),
        sa.Column("confidence", sa.Numeric(8, 7), nullable=False),
        sa.Column("model_version", sa.String(120), nullable=False),
        *_point_in_time_columns(),
        sa.ForeignKeyConstraint(
            ["reference_id"],
            ["watch_reference.id"],
            name="fk_price_index_reference_id_watch_reference",
        ),
        sa.UniqueConstraint(
            "reference_id",
            "date",
            "model_version",
            "as_of",
            name="uq_price_index_ref_date_model_as_of",
        ),
        sa.CheckConstraint(
            "hedonic_index > 0",
            name=op.f("ck_price_index_hedonic_index_positive"),
        ),
        sa.CheckConstraint("volume >= 0", name=op.f("ck_price_index_volume_nonnegative")),
        sa.CheckConstraint(
            "listing_count >= 0",
            name=op.f("ck_price_index_listing_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_price_index_confidence_range"),
        ),
    )
    _point_in_time_indexes("price_index")

    op.create_table(
        "feature_snapshot",
        _id_column(),
        sa.Column("reference_id", sa.Uuid(), nullable=False),
        sa.Column("feature_set_version", sa.String(120), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("maximum_source_ingested_at", sa.DateTime(timezone=True), nullable=False),
        *_point_in_time_columns(),
        sa.ForeignKeyConstraint(
            ["reference_id"],
            ["watch_reference.id"],
            name="fk_feature_snapshot_reference_id_watch_reference",
        ),
        sa.UniqueConstraint(
            "reference_id",
            "feature_set_version",
            "as_of",
            name="uq_feature_snapshot_ref_version_as_of",
        ),
        sa.CheckConstraint(
            "maximum_source_ingested_at <= as_of",
            name=op.f("ck_feature_snapshot_no_lookahead"),
        ),
    )
    _point_in_time_indexes("feature_snapshot")

    op.create_table(
        "forecast",
        _id_column(),
        sa.Column("reference_id", sa.Uuid(), nullable=False),
        sa.Column("horizon", sa.SmallInteger(), nullable=False),
        sa.Column("return_basis", sa.String(12), nullable=False),
        sa.Column("point", sa.Numeric(16, 9), nullable=False),
        sa.Column("p10", sa.Numeric(16, 9), nullable=False),
        sa.Column("p50", sa.Numeric(16, 9), nullable=False),
        sa.Column("p90", sa.Numeric(16, 9), nullable=False),
        sa.Column("model_version", sa.String(120), nullable=False),
        *_point_in_time_columns(),
        sa.ForeignKeyConstraint(
            ["reference_id"],
            ["watch_reference.id"],
            name="fk_forecast_reference_id_watch_reference",
        ),
        sa.UniqueConstraint(
            "reference_id",
            "horizon",
            "return_basis",
            "model_version",
            "as_of",
            name="uq_forecast_ref_horizon_basis_model_as_of",
        ),
        sa.CheckConstraint(
            "horizon IN (3, 6, 12, 36)",
            name=op.f("ck_forecast_supported_horizon"),
        ),
        sa.CheckConstraint(
            "return_basis IN ('gross', 'net')",
            name=op.f("ck_forecast_return_basis"),
        ),
        sa.CheckConstraint(
            "p10 <= p50 AND p50 <= p90",
            name=op.f("ck_forecast_quantile_order"),
        ),
    )
    _point_in_time_indexes("forecast")

    op.create_table(
        "holding",
        _id_column(),
        sa.Column("reference_id", sa.Uuid()),
        sa.Column("model_name", sa.String(240), nullable=False),
        sa.Column("reference_text", sa.String(120), nullable=False),
        sa.Column("production_year", sa.SmallInteger()),
        sa.Column("purchase_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("purchase_currency", sa.String(3), nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("condition", sa.String(120)),
        sa.Column("box", sa.Boolean()),
        sa.Column("papers", sa.Boolean()),
        sa.Column("marked_price", sa.Numeric(18, 2)),
        sa.Column("illiquidity_adjusted_mark", sa.Numeric(18, 2)),
        sa.Column("mark_model_version", sa.String(120)),
        *_point_in_time_columns(),
        sa.ForeignKeyConstraint(
            ["reference_id"],
            ["watch_reference.id"],
            name="fk_holding_reference_id_watch_reference",
        ),
        sa.CheckConstraint(
            "purchase_price > 0",
            name=op.f("ck_holding_purchase_price_positive"),
        ),
        sa.CheckConstraint(
            "marked_price IS NULL OR marked_price > 0",
            name=op.f("ck_holding_marked_price_positive"),
        ),
        sa.CheckConstraint(
            "illiquidity_adjusted_mark IS NULL OR illiquidity_adjusted_mark > 0",
            name=op.f("ck_holding_illiquidity_mark_positive"),
        ),
    )
    _point_in_time_indexes("holding")

    op.create_table(
        "model_run",
        _id_column(),
        sa.Column("model_name", sa.String(160), nullable=False),
        sa.Column("model_version", sa.String(120), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON()),
        sa.Column("artifact_uri", sa.Text()),
        sa.Column("error_message", sa.Text()),
        *_point_in_time_columns(),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'blocked')",
            name=op.f("ck_model_run_model_run_status"),
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name=op.f("ck_model_run_model_run_timestamp_order"),
        ),
    )
    _point_in_time_indexes("model_run")

    op.create_table(
        "alert",
        _id_column(),
        sa.Column("reference_id", sa.Uuid()),
        sa.Column("listing_id", sa.Uuid()),
        sa.Column("alert_type", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("dedupe_key", sa.String(240), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("fired_at", sa.DateTime(timezone=True)),
        *_point_in_time_columns(),
        sa.ForeignKeyConstraint(
            ["reference_id"],
            ["watch_reference.id"],
            name="fk_alert_reference_id_watch_reference",
        ),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"], name="fk_alert_listing_id_listing"),
        sa.UniqueConstraint("dedupe_key", "as_of", name="uq_alert_dedupe_as_of"),
        sa.CheckConstraint(
            "alert_type IN ('undervalued_listing', 'price_cut', 'momentum_breakout', "
            "'momentum_breakdown', 'regime_shift', 'data_quality')",
            name=op.f("ck_alert_alert_type"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'suppressed', 'failed')",
            name=op.f("ck_alert_alert_status"),
        ),
    )
    _point_in_time_indexes("alert")

    op.create_table(
        "data_quality_check",
        _id_column(),
        sa.Column("check_name", sa.String(160), nullable=False),
        sa.Column("scope", sa.String(240), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("severity", sa.String(24), nullable=False),
        sa.Column("observed_value", sa.JSON()),
        sa.Column("expected_value", sa.JSON()),
        sa.Column("details", sa.Text()),
        sa.Column("model_run_id", sa.Uuid()),
        *_point_in_time_columns(),
        sa.ForeignKeyConstraint(
            ["model_run_id"],
            ["model_run.id"],
            name="fk_data_quality_check_model_run_id_model_run",
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'error', 'blocking')",
            name=op.f("ck_data_quality_check_data_quality_severity"),
        ),
    )
    _point_in_time_indexes("data_quality_check")
    op.create_index(
        "ix_data_quality_check_name_as_of",
        "data_quality_check",
        ["check_name", "as_of"],
    )

    op.execute(
        """
        CREATE FUNCTION wristalpha_prevent_raw_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.raw_payload IS DISTINCT FROM NEW.raw_payload
               OR OLD.raw_payload_sha256 IS DISTINCT FROM NEW.raw_payload_sha256 THEN
                RAISE EXCEPTION 'raw payloads are immutable; append a new observation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER listing_raw_payload_immutable
        BEFORE UPDATE ON listing
        FOR EACH ROW EXECUTE FUNCTION wristalpha_prevent_raw_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER transaction_raw_payload_immutable
        BEFORE UPDATE ON transaction
        FOR EACH ROW EXECUTE FUNCTION wristalpha_prevent_raw_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS transaction_raw_payload_immutable ON transaction")
    op.execute("DROP TRIGGER IF EXISTS listing_raw_payload_immutable ON listing")
    op.execute("DROP FUNCTION IF EXISTS wristalpha_prevent_raw_mutation")
    for table_name in (
        "data_quality_check",
        "alert",
        "model_run",
        "holding",
        "forecast",
        "feature_snapshot",
        "price_index",
        "transaction",
        "listing",
        "watch_reference",
        "brand",
    ):
        op.drop_table(table_name)
