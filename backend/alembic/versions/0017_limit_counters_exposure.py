"""Create atomic limit counters and exposure positions."""

import sqlalchemy as sa

from alembic import op

revision = "0017_limit_counters_exposure"
down_revision = "0016_entitlement_amount_bands"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prod_limit_counters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("counter_id", sa.String(100), nullable=False),
        sa.Column("tenant_id", sa.String(80), nullable=False),
        sa.Column("participant_id", sa.String(80), nullable=False),
        sa.Column("service", sa.String(80), nullable=False),
        sa.Column("corridor", sa.String(40), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("business_date", sa.String(10), nullable=False),
        sa.Column("reserved_amount_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("consumed_amount_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("tenant_id", "participant_id", "service", "corridor", "currency", "business_date", name="uq_prod_limit_counter_scope"),
        sa.CheckConstraint("reserved_amount_minor >= 0 AND consumed_amount_minor >= 0", name="ck_prod_limit_counter_nonnegative"),
    )
    op.create_table(
        "prod_exposure_positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("position_id", sa.String(100), nullable=False, unique=True),
        sa.Column("tenant_id", sa.String(80), nullable=False),
        sa.Column("participant_id", sa.String(80), nullable=False),
        sa.Column("corridor", sa.String(40), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("exposure_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("tenant_id", "participant_id", "corridor", "currency", name="uq_prod_exposure_scope"),
        sa.CheckConstraint("exposure_minor >= 0", name="ck_prod_exposure_nonnegative"),
    )


def downgrade() -> None:
    op.drop_table("prod_exposure_positions")
    op.drop_table("prod_limit_counters")
