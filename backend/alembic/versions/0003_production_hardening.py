"""Backfill B0-B10 hardening fields for databases created by the first 0002."""

from __future__ import annotations

import uuid

import sqlalchemy as sa

from alembic import op
from database import Base
from production import models as production_models  # noqa: F401

revision = "0003_production_hardening"
down_revision = "0002_production_domain"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def _add(table: str, column: sa.Column) -> None:
    if column.name not in _columns(table):
        op.add_column(table, column)


def upgrade() -> None:
    _add("prod_participants", sa.Column("tenant_id", sa.String(80), nullable=True))
    _add("prod_fx_quotes", sa.Column("participant_id", sa.String(80), nullable=True))
    _add("prod_fx_quotes", sa.Column("corridor", sa.String(40), nullable=True))
    _add("prod_payment_facts", sa.Column("supersedes_fact_id", sa.String(80), nullable=True))
    _add("prod_idempotency_keys", sa.Column("owner", sa.String(120), nullable=True))
    _add("prod_idempotency_keys", sa.Column("locked_until", sa.DateTime(), nullable=True))
    _add("prod_outbox_events", sa.Column("schema_version", sa.String(40), nullable=True, server_default="1.0"))
    _add("prod_outbox_events", sa.Column("partition_key", sa.String(120), nullable=True))
    _add("prod_outbox_events", sa.Column("lease_owner", sa.String(120), nullable=True))
    _add("prod_outbox_events", sa.Column("lease_until", sa.DateTime(), nullable=True))
    _add("prod_return_payments", sa.Column("return_uetr", sa.String(36), nullable=True))
    bind = op.get_bind()
    if "participant_id" in _columns("prod_fx_quotes"):
        bind.execute(sa.text("UPDATE prod_fx_quotes SET participant_id = COALESCE(participant_id, 'SANDBOX-ORIGIN')"))
        bind.execute(sa.text("UPDATE prod_fx_quotes SET corridor = COALESCE(corridor, 'CN-HK')"))
    if "partition_key" in _columns("prod_outbox_events"):
        bind.execute(sa.text("UPDATE prod_outbox_events SET partition_key = COALESCE(partition_key, aggregate_id)"))
    if "return_uetr" in _columns("prod_return_payments"):
        for row in bind.execute(sa.text("SELECT id FROM prod_return_payments WHERE return_uetr IS NULL")).fetchall():
            bind.execute(sa.text("UPDATE prod_return_payments SET return_uetr = :uetr WHERE id = :id"), {"uetr": str(uuid.uuid4()), "id": row[0]})
    for name, table in Base.metadata.tables.items():
        if name.startswith("prod_") and name not in sa.inspect(bind).get_table_names():
            table.create(bind, checkfirst=True)


def downgrade() -> None:
    # New tables are removed; additive columns are intentionally retained to
    # keep downgrade recoverable for rows created after hardening.
    bind = op.get_bind()
    original = {"prod_standard_artifacts", "prod_transaction_copies", "prod_field_lineage", "prod_reconciliation_breaks", "prod_report_batches", "prod_report_receipts", "prod_tenants", "prod_certificates", "prod_accounts", "prod_account_ownerships", "prod_limit_profiles", "prod_rulebook_acceptances", "prod_mandates", "prod_approvals"}
    for name in sorted(original, reverse=True):
        if name in sa.inspect(bind).get_table_names():
            op.drop_table(name)
