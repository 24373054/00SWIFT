"""Enable PostgreSQL tenant/participant RLS for tenant-owned production tables."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0014_production_rls"
down_revision = "0013_production_financial_invariants"
branch_labels = None
depends_on = None

POLICIES = {
    "prod_tenants": "tenant_id = current_setting('app.tenant_id', true)",
    "prod_participants": "tenant_id = current_setting('app.tenant_id', true)",
    "prod_payment_orders": "tenant_id = current_setting('app.tenant_id', true) AND initiator_participant = current_setting('app.participant_id', true)",
    "prod_accounts": "tenant_id = current_setting('app.tenant_id', true) AND participant_id = current_setting('app.participant_id', true)",
    "prod_entitlements": "participant_id = current_setting('app.participant_id', true)",
    "prod_service_identities": "participant_id = current_setting('app.participant_id', true)",
    "prod_certificates": "participant_id = current_setting('app.participant_id', true)",
    "prod_account_ownerships": "participant_id = current_setting('app.participant_id', true)",
    "prod_limit_profiles": "participant_id = current_setting('app.participant_id', true)",
    "prod_rulebook_acceptances": "participant_id = current_setting('app.participant_id', true)",
    "prod_mandates": "participant_id = current_setting('app.participant_id', true)",
    "prod_fx_quotes": "participant_id = current_setting('app.participant_id', true)",
}


def _is_postgres(bind) -> bool:
    return bind.dialect.name == "postgresql"


def upgrade() -> None:
    bind = op.get_bind()
    if not _is_postgres(bind):
        return
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    for table, predicate in POLICIES.items():
        if table not in tables:
            continue
        policy_name = f"p_{table}_tenant_context"
        columns = {column["name"] for column in inspector.get_columns(table)}
        if "tenant_id" not in columns and "participant_id" not in columns:
            continue
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name} ON {table}"))
        op.execute(sa.text(f"CREATE POLICY {policy_name} ON {table} USING ({predicate}) WITH CHECK ({predicate})"))


def downgrade() -> None:
    bind = op.get_bind()
    if not _is_postgres(bind):
        return
    for table in POLICIES:
        policy_name = f"p_{table}_tenant_context"
        op.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name} ON {table}"))
        op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
