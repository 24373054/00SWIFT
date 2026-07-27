"""Make payment facts append-only by business reference and sequence."""

import sqlalchemy as sa

from alembic import op

revision = "0026_append_only_fact_metadata"
down_revision = "0025_payment_state_dimensions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {item["name"] for item in inspector.get_columns("prod_payment_facts")}
    for name, typ, default in (("fact_sequence", sa.Integer(), "1"), ("input_hash", sa.String(64), ""), ("output_hash", sa.String(64), ""), ("rule_version", sa.String(80), "unspecified"), ("actor", sa.String(160), "system")):
        if name not in existing:
            op.add_column("prod_payment_facts", sa.Column(name, typ, nullable=False, server_default=default))
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, order_id, fact_type, reference FROM prod_payment_facts ORDER BY id")).mappings().all()
    counters = {}
    for row in rows:
        key = (row["order_id"], row["fact_type"], row["reference"])
        counters[key] = counters.get(key, 0) + 1
        bind.execute(sa.text("UPDATE prod_payment_facts SET fact_sequence=:sequence WHERE id=:id"), {"sequence": counters[key], "id": row["id"]})
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("prod_payment_facts") as batch:
            batch.drop_constraint("uq_prod_fact_ref", type_="unique")
            batch.create_unique_constraint("uq_prod_fact_sequence", ["order_id", "fact_type", "reference", "fact_sequence"])
    else:
        op.drop_constraint("uq_prod_fact_ref", "prod_payment_facts", type_="unique")
        op.create_unique_constraint("uq_prod_fact_sequence", "prod_payment_facts", ["order_id", "fact_type", "reference", "fact_sequence"])


def downgrade() -> None:
    op.drop_constraint("uq_prod_fact_sequence", "prod_payment_facts", type_="unique")
    op.create_unique_constraint("uq_prod_fact_ref", "prod_payment_facts", ["order_id", "fact_type", "reference"])
    for name in ("actor", "rule_version", "output_hash", "input_hash", "fact_sequence"):
        op.drop_column("prod_payment_facts", name)
