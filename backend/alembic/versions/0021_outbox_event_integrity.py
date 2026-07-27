"""Require tenant-scoped, hashable and observable outbox events."""

import hashlib
import json

import sqlalchemy as sa

from alembic import op

revision = "0021_outbox_event_integrity"
down_revision = "0020_approval_credential_binding"
branch_labels = None
depends_on = None


def _add(table: str, column: sa.Column) -> None:
    inspector = sa.inspect(op.get_bind())
    if column.name not in {item["name"] for item in inspector.get_columns(table)}:
        op.add_column(table, column)


def upgrade() -> None:
    for column in (
        sa.Column("tenant_id", sa.String(120), nullable=True),
        sa.Column("participant_id", sa.String(120), nullable=True),
        sa.Column("payload_hash", sa.String(64), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("lease_heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("broker_offset", sa.String(200), nullable=True),
        sa.Column("broker_metadata", sa.Text(), nullable=True),
    ):
        _add("prod_outbox_events", column)
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT event_id, aggregate_id, payload FROM prod_outbox_events WHERE tenant_id IS NULL OR participant_id IS NULL OR payload_hash IS NULL OR content_hash IS NULL")).mappings().all()
    for row in rows:
        payload = json.loads(row["payload"])
        order_id = payload.get("order_id", row["aggregate_id"])
        order = bind.execute(sa.text("SELECT tenant_id, initiator_participant FROM prod_payment_orders WHERE order_id = :order_id"), {"order_id": order_id}).mappings().first()
        tenant_id = payload.get("tenant_id") or (order["tenant_id"] if order else None)
        participant_id = payload.get("participant_id") or (order["initiator_participant"] if order else None)
        if not tenant_id or not participant_id:
            raise RuntimeError(f"[EXT-BLOCKED] cannot backfill tenant/participant for outbox {row['event_id']}")
        payload_hash = hashlib.sha256(row["payload"].encode("utf-8")).hexdigest()
        bind.execute(sa.text("UPDATE prod_outbox_events SET tenant_id=:tenant_id, participant_id=:participant_id, payload_hash=:payload_hash, content_hash=:content_hash WHERE event_id=:event_id"), {"tenant_id": tenant_id, "participant_id": participant_id, "payload_hash": payload_hash, "content_hash": payload_hash, "event_id": row["event_id"]})
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("prod_outbox_events") as batch:
            batch.alter_column("tenant_id", existing_type=sa.String(120), nullable=False)
            batch.alter_column("participant_id", existing_type=sa.String(120), nullable=False)
            batch.alter_column("payload_hash", existing_type=sa.String(64), nullable=False)
            batch.alter_column("content_hash", existing_type=sa.String(64), nullable=False)
    else:
        for name, typ in (("tenant_id", sa.String(120)), ("participant_id", sa.String(120)), ("payload_hash", sa.String(64)), ("content_hash", sa.String(64))):
            op.alter_column("prod_outbox_events", name, existing_type=typ, nullable=False)
    for name in ("tenant_id", "participant_id"):
        op.create_index(f"ix_prod_outbox_events_{name}", "prod_outbox_events", [name])


def downgrade() -> None:
    for name in ("tenant_id", "participant_id"):
        op.drop_index(f"ix_prod_outbox_events_{name}", table_name="prod_outbox_events")
    for name, _typ in (("content_hash", sa.String(64)), ("payload_hash", sa.String(64)), ("participant_id", sa.String(120)), ("tenant_id", sa.String(120)), ("broker_metadata", sa.Text()), ("broker_offset", sa.String(200)), ("published_at", sa.DateTime()), ("lease_heartbeat_at", sa.DateTime())):
        op.drop_column("prod_outbox_events", name)
