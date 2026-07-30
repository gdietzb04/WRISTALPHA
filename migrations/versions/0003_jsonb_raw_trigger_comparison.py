"""Use JSONB equality semantics in raw-record immutability triggers.

Revision ID: 0003_jsonb_trigger
Revises: 0002_raw_immutable
"""

from __future__ import annotations

from alembic import op

revision = "0003_jsonb_trigger"
down_revision = "0002_raw_immutable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION wristalpha_prevent_listing_raw_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF ROW(OLD.source, OLD.external_id, OLD.adapter_type, OLD.source_url,
                 OLD.fetched_at, OLD.raw_payload::jsonb, OLD.raw_payload_sha256,
                 OLD.title, OLD.description, OLD.raw_price, OLD.raw_currency)
             IS DISTINCT FROM
             ROW(NEW.source, NEW.external_id, NEW.adapter_type, NEW.source_url,
                 NEW.fetched_at, NEW.raw_payload::jsonb, NEW.raw_payload_sha256,
                 NEW.title, NEW.description, NEW.raw_price, NEW.raw_currency) THEN
            RAISE EXCEPTION 'raw listing fields are immutable; append an observation';
          END IF;
          RETURN NEW;
        END; $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION wristalpha_prevent_transaction_raw_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF ROW(OLD.source, OLD.external_id, OLD.auction_house, OLD.sale_name,
                 OLD.lot_number, OLD.sold_at, OLD.hammer_price, OLD.buyer_premium,
                 OLD.realized_price, OLD.currency, OLD.source_url,
                 OLD.raw_payload::jsonb, OLD.raw_payload_sha256)
             IS DISTINCT FROM
             ROW(NEW.source, NEW.external_id, NEW.auction_house, NEW.sale_name,
                 NEW.lot_number, NEW.sold_at, NEW.hammer_price, NEW.buyer_premium,
                 NEW.realized_price, NEW.currency, NEW.source_url,
                 NEW.raw_payload::jsonb, NEW.raw_payload_sha256) THEN
            RAISE EXCEPTION 'raw transaction fields are immutable; append an observation';
          END IF;
          RETURN NEW;
        END; $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION wristalpha_prevent_listing_raw_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.raw_payload::text IS DISTINCT FROM NEW.raw_payload::text
             OR OLD.raw_payload_sha256 IS DISTINCT FROM NEW.raw_payload_sha256 THEN
            RAISE EXCEPTION 'raw listing fields are immutable; append an observation';
          END IF;
          RETURN NEW;
        END; $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION wristalpha_prevent_transaction_raw_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.raw_payload::text IS DISTINCT FROM NEW.raw_payload::text
             OR OLD.raw_payload_sha256 IS DISTINCT FROM NEW.raw_payload_sha256 THEN
            RAISE EXCEPTION 'raw transaction fields are immutable; append an observation';
          END IF;
          RETURN NEW;
        END; $$;
        """
    )
