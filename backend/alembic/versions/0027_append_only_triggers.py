"""Database-level append-only triggers for facts and decisions."""

import sqlalchemy as sa

from alembic import op

revision = "0027_append_only_triggers"
down_revision = "0026_append_only_fact_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "prod_finality_decisions" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "prod_finality_decisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("decision_id", sa.String(80), nullable=False, unique=True),
            sa.Column("order_id", sa.String(80), nullable=False),
            sa.Column("outcome", sa.String(30), nullable=False),
            sa.Column("input_hash", sa.String(64), nullable=False),
            sa.Column("rule_version", sa.String(80), nullable=False),
            sa.Column("evidence_ref", sa.String(120), nullable=True),
            sa.Column("evaluated_at", sa.DateTime(), nullable=False),
        )
    if bind.dialect.name != "postgresql":
        return
    bind.exec_driver_sql(
        """
        CREATE OR REPLACE FUNCTION production_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'production evidence/decision rows are append-only'; END; $$;
        """
    )
    for table in ("prod_payment_facts", "prod_authorization_decisions", "prod_compliance_decisions", "prod_finality_decisions"):
        bind.exec_driver_sql(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
        bind.exec_driver_sql(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION production_append_only()")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table in ("prod_payment_facts", "prod_authorization_decisions", "prod_compliance_decisions", "prod_finality_decisions"):
        bind.exec_driver_sql(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
    bind.exec_driver_sql("DROP FUNCTION IF EXISTS production_append_only()")
