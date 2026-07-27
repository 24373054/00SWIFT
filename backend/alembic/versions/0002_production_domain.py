"""Create the contract-first production payment domain.

Revision ID: 0002_production_domain
Revises: 0001_nextgen_core
"""

from __future__ import annotations

import hashlib

from alembic import op
from database import Base
from production import models as production_models  # noqa: F401

revision = "0002_production_domain"
down_revision = "0001_nextgen_core"
branch_labels = None
depends_on = None

EXPECTED_PRODUCTION_SCHEMA_HASH = "0b33b9deef7b3b9a27c0e65fc9a213b4ee917160b96f0fc1e17fde12f2689b73"
PRODUCTION_TABLE_NAMES = (
    "prod_account_ownerships", "prod_accounts", "prod_approvals", "prod_audit_events",
    "prod_authorization_decisions", "prod_beneficiary_credits", "prod_cancellation_requests",
    "prod_certificates", "prod_completion_profiles", "prod_compliance_decisions",
    "prod_delivery_profiles", "prod_entitlements", "prod_evidence_manifests", "prod_field_lineage",
    "prod_finality_profiles", "prod_funding_reservations", "prod_fx_quotes", "prod_fx_trade_intents",
    "prod_fx_trades", "prod_idempotency_keys", "prod_inbox_messages", "prod_investigation_cases",
    "prod_journal_entries", "prod_journals", "prod_ledger_accounts", "prod_liability_profiles",
    "prod_limit_profiles", "prod_mandates", "prod_outbox_events", "prod_participants",
    "prod_payment_facts", "prod_payment_orders", "prod_reconciliation_breaks", "prod_reconciliation_runs",
    "prod_report_batches", "prod_report_receipts", "prod_return_payments", "prod_rulebook_acceptances",
    "prod_service_identities", "prod_settlement_legs", "prod_standard_artifacts", "prod_tenants",
    "prod_transaction_copies",
)


def _production_tables():
    return [Base.metadata.tables[name] for name in PRODUCTION_TABLE_NAMES]


def _production_schema_hash() -> str:
    lines = []
    for table in _production_tables():
        columns = "|".join(f"{column.name}:{column.type}:{int(column.nullable)}" for column in table.columns)
        lines.append(f"{table.name}:{columns}")
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _assert_frozen_schema() -> None:
    actual = _production_schema_hash()
    if actual != EXPECTED_PRODUCTION_SCHEMA_HASH:
        raise RuntimeError(
            "Production ORM schema changed after 0002; create a new explicit Alembic revision instead of mutating history"
        )


def upgrade() -> None:
    _assert_frozen_schema()
    bind = op.get_bind()
    for table in _production_tables():
        table.create(bind, checkfirst=True)


def downgrade() -> None:
    for table_name in reversed(PRODUCTION_TABLE_NAMES):
        op.drop_table(table_name, if_exists=True)
