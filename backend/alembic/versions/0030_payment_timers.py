"""Add payment timeout timers."""

import sqlalchemy as sa

from alembic import op

revision = "0030_payment_timers"
down_revision = "0029_payment_graph_report_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prod_payment_timers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timer_id", sa.String(100), nullable=False, unique=True),
        sa.Column("order_id", sa.String(80), sa.ForeignKey("prod_payment_orders.order_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("timer_type", sa.String(40), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="SCHEDULED"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("order_id", "timer_type", name="uq_prod_timer_type"),
    )
    op.create_index("ix_prod_payment_timers_due_at", "prod_payment_timers", ["due_at"])
    op.create_index("ix_prod_payment_timers_order_id", "prod_payment_timers", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_prod_payment_timers_order_id", table_name="prod_payment_timers")
    op.drop_index("ix_prod_payment_timers_due_at", table_name="prod_payment_timers")
    op.drop_table("prod_payment_timers")
