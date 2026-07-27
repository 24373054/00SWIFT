"""Attach atomic limit reservation reference to payment orders."""

import sqlalchemy as sa

from alembic import op

revision = "0018_payment_limit_reservation"
down_revision = "0017_limit_counters_exposure"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "prod_payment_orders" not in sa.inspect(bind).get_table_names():
        return
    if "limit_reservation_id" not in {item["name"] for item in sa.inspect(bind).get_columns("prod_payment_orders")}:
        with op.batch_alter_table("prod_payment_orders", recreate="always") as batch:
            batch.add_column(sa.Column("limit_reservation_id", sa.String(100), nullable=True))


def downgrade() -> None:
    if "prod_payment_orders" in sa.inspect(op.get_bind()).get_table_names():
        with op.batch_alter_table("prod_payment_orders", recreate="always") as batch:
            batch.drop_column("limit_reservation_id")
