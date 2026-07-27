"""Add dual-control DLQ replay requests."""

import sqlalchemy as sa

from alembic import op

revision = "0024_dlq_replay_requests"
down_revision = "0023_outbox_null_lease_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prod_replay_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("replay_id", sa.String(100), nullable=False),
        sa.Column("event_id", sa.String(80), sa.ForeignKey("prod_outbox_events.event_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("original_hash", sa.String(64), nullable=False),
        sa.Column("maker", sa.String(200), nullable=False),
        sa.Column("checker", sa.String(200), nullable=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("replay_id", name="uq_prod_replay_id"),
        sa.UniqueConstraint("event_id", name="uq_prod_replay_event"),
    )
    op.create_index("ix_prod_replay_requests_event_id", "prod_replay_requests", ["event_id"])
    op.create_index("ix_prod_replay_requests_tenant_id", "prod_replay_requests", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_prod_replay_requests_tenant_id", table_name="prod_replay_requests")
    op.drop_index("ix_prod_replay_requests_event_id", table_name="prod_replay_requests")
    op.drop_table("prod_replay_requests")
