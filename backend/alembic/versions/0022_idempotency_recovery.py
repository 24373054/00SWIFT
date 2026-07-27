"""Add idempotency recovery and trace fields."""

import sqlalchemy as sa

from alembic import op

revision = "0022_idempotency_recovery"
down_revision = "0021_outbox_event_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {item["name"] for item in inspector.get_columns("prod_idempotency_keys")}
    for column in (
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(120), nullable=True),
    ):
        if column.name not in existing:
            op.add_column("prod_idempotency_keys", column)
    op.create_index("ix_prod_idempotency_keys_trace_id", "prod_idempotency_keys", ["trace_id"])


def downgrade() -> None:
    op.drop_index("ix_prod_idempotency_keys_trace_id", table_name="prod_idempotency_keys")
    for name in ("trace_id", "last_error", "attempt"):
        op.drop_column("prod_idempotency_keys", name)
