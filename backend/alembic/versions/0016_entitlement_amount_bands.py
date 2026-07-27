"""Add explicit entitlement amount bands and version."""

import sqlalchemy as sa

from alembic import op

revision = "0016_entitlement_amount_bands"
down_revision = "0015_rulebook_acceptance_window"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "prod_entitlements" not in sa.inspect(bind).get_table_names():
        return
    columns = {item["name"] for item in sa.inspect(bind).get_columns("prod_entitlements")}
    with op.batch_alter_table("prod_entitlements", recreate="always") as batch:
        if "min_amount_minor" not in columns:
            batch.add_column(sa.Column("min_amount_minor", sa.BigInteger(), nullable=True))
        if "max_amount_minor" not in columns:
            batch.add_column(sa.Column("max_amount_minor", sa.BigInteger(), nullable=True))
        if "version" not in columns:
            batch.add_column(sa.Column("version", sa.Integer(), nullable=True))
    bind.execute(sa.text("UPDATE prod_entitlements SET min_amount_minor = COALESCE(min_amount_minor, 0), max_amount_minor = COALESCE(max_amount_minor, 9223372036854775807), version = COALESCE(version, 1)"))
    with op.batch_alter_table("prod_entitlements", recreate="always") as batch:
        batch.alter_column("min_amount_minor", existing_type=sa.BigInteger(), nullable=False)
        batch.alter_column("max_amount_minor", existing_type=sa.BigInteger(), nullable=False)
        batch.alter_column("version", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    if "prod_entitlements" in sa.inspect(op.get_bind()).get_table_names():
        with op.batch_alter_table("prod_entitlements", recreate="always") as batch:
            batch.drop_column("version")
            batch.drop_column("max_amount_minor")
            batch.drop_column("min_amount_minor")
