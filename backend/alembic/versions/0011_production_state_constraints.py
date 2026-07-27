"""Constrain every production state/status column to the versioned vocabulary."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0011_production_state_constraints"
down_revision = "0010_production_utc_timestamps"
branch_labels = None
depends_on = None

CONSTRAINTS = {
    "prod_tenants": ("status", ("PENDING", "ACTIVE", "SUSPENDED", "REVOKED")),
    "prod_participants": ("status", ("PENDING", "ACTIVE", "SUSPENDED", "REVOKED")),
    "prod_entitlements": ("status", ("PENDING", "ACTIVE", "SUSPENDED", "EXPIRED", "REVOKED")),
    "prod_service_identities": ("status", ("PENDING", "ACTIVE", "SUSPENDED", "REVOKED")),
    "prod_certificates": ("status", ("PENDING", "ACTIVE", "EXPIRED", "REVOKED")),
    "prod_accounts": ("status", ("PENDING", "ACTIVE", "SUSPENDED", "CLOSED")),
    "prod_account_ownerships": ("status", ("PENDING", "ACTIVE", "EXPIRED", "REVOKED")),
    "prod_limit_profiles": ("status", ("PENDING", "ACTIVE", "SUSPENDED", "EXPIRED", "REVOKED")),
    "prod_rulebook_acceptances": ("status", ("PENDING", "ACCEPTED", "REJECTED", "EXPIRED")),
    "prod_mandates": ("status", ("PENDING", "ACTIVE", "EXPIRED", "REVOKED")),
    "prod_approvals": ("state", ("PENDING", "APPROVED", "REJECTED", "EXPIRED")),
    "prod_payment_orders": ("orchestration_state", ("RECEIVED", "CONTROL_CHECKS", "RESERVATION_PENDING", "FX_ACCEPTANCE_PENDING", "FX_ACCEPTED", "MESSAGE_DELIVERED", "VALUE_SETTLEMENT", "CUSTOMER_COMPLETED", "COMPLIANCE_REJECTED", "EXECUTION_CANCELLED", "SUSPENDED", "OPERATIONALLY_CLOSED", "OPERATIONALLY_CLOSED_UNSUCCESSFUL")),
    "prod_payment_facts": ("state", ("RECEIVED", "VALIDATED", "APPLIED", "PENDING", "PASSED", "AUTHORIZED", "APPROVED", "ACCEPTANCE_PENDING", "READY_TO_ACCEPT", "TRADE_ACCEPTED", "ACCEPTED", "REJECTED", "REQUESTED", "VALIDATING", "SENT", "RESERVED", "RELEASED", "CONSUMED", "FINAL", "DELIVERED", "NETWORK_ACKED", "CREDITED", "MATCHED", "UNMATCHED", "NOT_APPLICABLE", "FAILED", "EXPIRED", "CANCELLED", "CLOSED", "UNKNOWN")),
    "prod_funding_reservations": ("state", ("PENDING", "RESERVED", "RELEASED", "CONSUMED", "FAILED", "EXPIRED", "UNKNOWN")),
    "prod_fx_quotes": ("status", ("QUOTED", "ACCEPTED", "EXPIRED", "REJECTED", "CANCELLED", "UNKNOWN")),
    "prod_fx_trade_intents": ("state", ("PREPARING", "READY_TO_ACCEPT", "REQUESTED", "TRADE_ACCEPTED", "ACCEPTED", "REJECTED", "CANCELLED", "COMPLETED", "FAILED", "UNKNOWN")),
    "prod_fx_trades": ("contract_state", ("PREPARING", "EXECUTING", "TRADE_ACCEPTED", "ACCEPTED", "EXECUTED", "REJECTED", "FAILED", "CANCELLED", "UNKNOWN")),
    "prod_settlement_legs": ("state", ("PENDING", "SUBMITTED", "FINAL", "FAILED", "CANCELLED", "UNKNOWN")),
    "prod_beneficiary_credits": ("state", ("UNKNOWN", "PENDING", "CREDITED", "FAILED", "REVERSED")),
    "prod_reconciliation_runs": ("state", ("UNMATCHED", "MATCHED", "BREAK", "FAILED")),
    "prod_cancellation_requests": ("state", ("REQUESTED", "VALIDATING", "SENT", "ACCEPTED", "REJECTED", "UNKNOWN", "CLOSED")),
    "prod_investigation_cases": ("state", ("OPEN", "IN_PROGRESS", "CLOSED")),
    "prod_return_payments": ("state", ("REQUESTED", "SENT", "ACCEPTED", "FINAL", "REJECTED", "UNKNOWN", "CLOSED")),
    "prod_journals": ("state", ("DRAFT", "VALIDATED", "POSTED", "VOIDED")),
    "prod_idempotency_keys": ("status", ("STARTED", "COMPLETED", "EXPIRED", "FAILED_RETRYABLE", "FAILED_FINAL")),
    "prod_key_operation_audits": ("status", ("STARTED", "COMPLETED", "FAILED")),
    "prod_corridor_admissions": ("status", ("PENDING", "ACTIVE", "EXPIRED", "REVOKED")),
    "prod_control_attestations": ("status", ("PENDING", "ACTIVE", "EXPIRED", "REVOKED")),
    "prod_outbox_events": ("status", ("PENDING", "PROCESSING", "PUBLISHED", "DEAD_LETTER")),
    "prod_standard_artifacts": ("status", ("PENDING", "ACTIVE", "EXPIRED", "REVOKED")),
    "prod_reconciliation_breaks": ("state", ("OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED")),
    "prod_report_batches": ("state", ("CREATED", "GENERATED", "SUBMITTED", "ACCEPTED", "FAILED")),
    "prod_report_receipts": ("state", ("PENDING", "RECEIVED", "ACCEPTED", "REJECTED")),
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    for table, (column, values) in CONSTRAINTS.items():
        if table not in tables or column not in {col["name"] for col in inspector.get_columns(table)}:
            continue
        quoted = ",".join(repr(value) for value in values)
        invalid = bind.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE {column} NOT IN ({quoted})")).scalar_one()
        if invalid:
            raise RuntimeError(f"Cannot constrain {table}.{column}: {invalid} invalid states")
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.create_check_constraint(f"ck_{table}_{column}_state_v1", f"{column} IN ({quoted})")


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    for table, (column, _values) in reversed(tuple(CONSTRAINTS.items())):
        if table not in tables:
            continue
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.drop_constraint(f"ck_{table}_{column}_state_v1", type_="check")
