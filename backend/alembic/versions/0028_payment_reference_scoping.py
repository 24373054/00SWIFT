"""Separate payment reference identifiers and scope uniqueness."""

import sqlalchemy as sa

from alembic import op

revision = "0028_payment_reference_scoping"
down_revision = "0027_append_only_triggers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {item["name"] for item in inspector.get_columns("prod_payment_orders")}
    for name in ("end_to_end_id", "transaction_id"):
        if name not in existing:
            op.add_column("prod_payment_orders", sa.Column(name, sa.String(200), nullable=True))
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, order_id FROM prod_payment_orders WHERE end_to_end_id IS NULL OR transaction_id IS NULL")).mappings().all()
    for row in rows:
        bind.execute(sa.text("UPDATE prod_payment_orders SET end_to_end_id=:e2e, transaction_id=:tx WHERE id=:id"), {"e2e": f"LEGACY-E2E-{row['order_id']}", "tx": f"LEGACY-TX-{row['order_id']}", "id": row["id"]})
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("prod_payment_orders") as batch:
            batch.alter_column("end_to_end_id", existing_type=sa.String(200), nullable=False)
            batch.alter_column("transaction_id", existing_type=sa.String(200), nullable=False)
            batch.create_unique_constraint("uq_prod_end_to_end_tenant", ["tenant_id", "end_to_end_id"])
            batch.create_unique_constraint("uq_prod_transaction_tenant", ["tenant_id", "transaction_id"])
    else:
        op.alter_column("prod_payment_orders", "end_to_end_id", existing_type=sa.String(200), nullable=False)
        op.alter_column("prod_payment_orders", "transaction_id", existing_type=sa.String(200), nullable=False)
        op.create_unique_constraint("uq_prod_end_to_end_tenant", "prod_payment_orders", ["tenant_id", "end_to_end_id"])
        op.create_unique_constraint("uq_prod_transaction_tenant", "prod_payment_orders", ["tenant_id", "transaction_id"])


def downgrade() -> None:
    op.drop_constraint("uq_prod_transaction_tenant", "prod_payment_orders", type_="unique")
    op.drop_constraint("uq_prod_end_to_end_tenant", "prod_payment_orders", type_="unique")
    op.drop_column("prod_payment_orders", "transaction_id")
    op.drop_column("prod_payment_orders", "end_to_end_id")
