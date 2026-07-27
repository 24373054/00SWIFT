"""Normalize production timestamps to timezone-aware UTC columns."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0010_production_utc_timestamps"
down_revision = "0009_production_bigint_amounts"
branch_labels = None
depends_on = None

DATE_COLUMNS = {
    "prod_tenants": ("created_at", "updated_at"), "prod_participants": ("created_at", "updated_at"),
    "prod_service_identities": ("created_at",), "prod_qualification_artifacts": ("valid_from", "valid_to", "verified_at"),
    "prod_qualification_decisions": ("decided_at",), "prod_payment_orders": ("created_at", "updated_at"),
    "prod_payment_facts": ("occurred_at",), "prod_authorization_decisions": ("evaluated_at", "valid_from", "valid_to"),
    "prod_compliance_decisions": ("evaluated_at", "valid_to"), "prod_funding_reservations": ("created_at", "updated_at"),
    "prod_fx_quotes": ("expires_at", "created_at"), "prod_fx_trade_intents": ("created_at", "updated_at"),
    "prod_fx_trades": ("created_at",), "prod_settlement_legs": ("created_at", "updated_at"),
    "prod_beneficiary_credits": ("created_at", "updated_at"), "prod_reconciliation_runs": ("created_at", "updated_at"),
    "prod_cancellation_requests": ("created_at",), "prod_investigation_cases": ("created_at", "updated_at"),
    "prod_return_payments": ("created_at",), "prod_ledger_accounts": (), "prod_journals": ("created_at",),
    "prod_journal_entries": ("created_at",), "prod_idempotency_keys": ("locked_until", "expires_at", "created_at"),
    "prod_request_nonces": ("expires_at", "first_used_at"), "prod_key_operation_audits": ("created_at", "completed_at"),
    "prod_corridor_admissions": ("valid_from", "valid_to", "created_at"), "prod_control_attestations": ("valid_from", "valid_to", "created_at"),
    "prod_outbox_events": ("available_at", "lease_until", "created_at"), "prod_inbox_messages": ("created_at",),
    "prod_evidence_manifests": ("created_at",), "prod_audit_events": ("created_at",),
    "prod_transaction_copies": ("created_at",), "prod_field_lineage": ("created_at",),
    "prod_reconciliation_breaks": ("created_at",), "prod_report_batches": ("created_at",),
    "prod_report_receipts": ("created_at",),
}


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    for table, columns in DATE_COLUMNS.items():
        if table not in tables:
            continue
        with op.batch_alter_table(table, recreate="always") as batch:
            for column in columns:
                batch.alter_column(column, type_=sa.DateTime(timezone=True))


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    for table, columns in DATE_COLUMNS.items():
        if table not in tables:
            continue
        with op.batch_alter_table(table, recreate="always") as batch:
            for column in columns:
                batch.alter_column(column, type_=sa.DateTime(timezone=False))
