"""Protect all raw acquisition fields from in-place mutation.

Revision ID: 0002_raw_immutable
Revises: 0001_p1
"""

from __future__ import annotations

from alembic import op

revision = "0002_raw_immutable"
down_revision = "0001_p1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS listing_raw_payload_immutable ON listing")
    op.execute("DROP TRIGGER IF EXISTS transaction_raw_payload_immutable ON transaction")
    op.execute("DROP FUNCTION IF EXISTS wristalpha_prevent_raw_mutation")
    op.execute(
        """
        CREATE FUNCTION wristalpha_prevent_listing_raw_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF ROW(OLD.source, OLD.external_id, OLD.adapter_type, OLD.source_url,
                 OLD.fetched_at, OLD.raw_payload, OLD.raw_payload_sha256,
                 OLD.title, OLD.description, OLD.raw_price, OLD.raw_currency)
             IS DISTINCT FROM
             ROW(NEW.source, NEW.external_id, NEW.adapter_type, NEW.source_url,
                 NEW.fetched_at, NEW.raw_payload, NEW.raw_payload_sha256,
                 NEW.title, NEW.description, NEW.raw_price, NEW.raw_currency) THEN
            RAISE EXCEPTION 'raw listing fields are immutable; append an observation';
          END IF;
          RETURN NEW;
        END; $$;
        """
    )
    op.execute(
        """
        CREATE FUNCTION wristalpha_prevent_transaction_raw_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF ROW(OLD.source, OLD.external_id, OLD.auction_house, OLD.sale_name,
                 OLD.lot_number, OLD.sold_at, OLD.hammer_price, OLD.buyer_premium,
                 OLD.realized_price, OLD.currency, OLD.source_url,
                 OLD.raw_payload, OLD.raw_payload_sha256)
             IS DISTINCT FROM
             ROW(NEW.source, NEW.external_id, NEW.auction_house, NEW.sale_name,
                 NEW.lot_number, NEW.sold_at, NEW.hammer_price, NEW.buyer_premium,
                 NEW.realized_price, NEW.currency, NEW.source_url,
                 NEW.raw_payload, NEW.raw_payload_sha256) THEN
            RAISE EXCEPTION 'raw transaction fields are immutable; append an observation';
          END IF;
          RETURN NEW;
        END; $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER listing_raw_payload_immutable
        BEFORE UPDATE ON listing FOR EACH ROW
        EXECUTE FUNCTION wristalpha_prevent_listing_raw_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER transaction_raw_payload_immutable
        BEFORE UPDATE ON transaction FOR EACH ROW
        EXECUTE FUNCTION wristalpha_prevent_transaction_raw_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS transaction_raw_payload_immutable ON transaction")
    op.execute("DROP TRIGGER IF EXISTS listing_raw_payload_immutable ON listing")
    op.execute("DROP FUNCTION IF EXISTS wristalpha_prevent_transaction_raw_mutation")
    op.execute("DROP FUNCTION IF EXISTS wristalpha_prevent_listing_raw_mutation")
    op.execute(
        """
        CREATE FUNCTION wristalpha_prevent_raw_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.raw_payload IS DISTINCT FROM NEW.raw_payload
             OR OLD.raw_payload_sha256 IS DISTINCT FROM NEW.raw_payload_sha256 THEN
            RAISE EXCEPTION 'raw payloads are immutable; append a new observation';
          END IF;
          RETURN NEW;
        END; $$;
        """
    )
    op.execute(
        "CREATE TRIGGER listing_raw_payload_immutable BEFORE UPDATE ON listing "
        "FOR EACH ROW EXECUTE FUNCTION wristalpha_prevent_raw_mutation()"
    )
    op.execute(
        "CREATE TRIGGER transaction_raw_payload_immutable BEFORE UPDATE ON transaction "
        "FOR EACH ROW EXECUTE FUNCTION wristalpha_prevent_raw_mutation()"
    )
