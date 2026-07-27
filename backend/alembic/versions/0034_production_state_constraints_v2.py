"""Align every production state column with the domain state-v2 vocabulary."""

from __future__ import annotations

from collections import defaultdict

import sqlalchemy as sa

from alembic import op

revision = "0034_production_state_constraints_v2"
down_revision = "0033_journal_templates"
branch_labels = None
depends_on = None

StateColumn = tuple[str, str]

# This is an immutable migration snapshot.  The parity test compares it with
# production.state_constraints so domain and database vocabularies cannot
# silently drift.
V2_CONSTRAINTS: dict[StateColumn, tuple[str, ...]] = {
    ("prod_tenants", "status"): ("PENDING", "ACTIVE", "SUSPENDED", "REVOKED"),
    ("prod_participants", "status"): ("PENDING", "ACTIVE", "SUSPENDED", "REVOKED"),
    ("prod_entitlements", "status"): ("PENDING", "ACTIVE", "SUSPENDED", "EXPIRED", "REVOKED"),
    ("prod_service_identities", "status"): ("PENDING", "ACTIVE", "SUSPENDED", "REVOKED"),
    ("prod_certificates", "status"): ("PENDING", "ACTIVE", "EXPIRED", "REVOKED"),
    ("prod_accounts", "status"): ("PENDING", "ACTIVE", "SUSPENDED", "CLOSED"),
    ("prod_account_ownerships", "status"): ("PENDING", "ACTIVE", "EXPIRED", "REVOKED"),
    ("prod_limit_profiles", "status"): ("PENDING", "ACTIVE", "SUSPENDED", "EXPIRED", "REVOKED"),
    ("prod_rulebook_acceptances", "status"): ("PENDING", "ACCEPTED", "REJECTED", "EXPIRED"),
    ("prod_mandates", "status"): ("PENDING", "ACTIVE", "EXPIRED", "REVOKED"),
    ("prod_approvals", "state"): ("PENDING", "APPROVED", "REJECTED", "EXPIRED"),
    ("prod_qualification_artifacts", "status"): ("VERIFIED", "ACTIVE", "EXPIRED", "REJECTED"),
    ("prod_delivery_profiles", "required_network_state"): (
        "NETWORK_ACKED",
        "DELIVERED",
        "BUSINESS_ACCEPTED",
    ),
    (
        "prod_payment_orders",
        "orchestration_state",
    ): (
        "RECEIVED",
        "CONTROL_CHECKS",
        "RESERVATION_PENDING",
        "FX_ACCEPTANCE_PENDING",
        "FX_ACCEPTED",
        "MESSAGE_DELIVERED",
        "VALUE_SETTLEMENT",
        "CUSTOMER_COMPLETED",
        "COMPLIANCE_REJECTED",
        "EXECUTION_CANCELLED",
        "SUSPENDED",
        "OPERATIONALLY_CLOSED",
        "OPERATIONALLY_CLOSED_UNSUCCESSFUL",
    ),
    (
        "prod_payment_orders",
        "authorization_state",
    ): (
        "PENDING",
        "MANDATE_VERIFIED",
        "SIGNATURES_PENDING",
        "AUTHORIZED",
        "APPROVED",
        "PASSED",
        "DENIED",
        "REJECTED",
        "EXPIRED",
        "UNKNOWN",
    ),
    ("prod_payment_orders", "compliance_state"): (
        "PENDING",
        "PASSED",
        "REJECTED",
        "REVIEW_REQUIRED",
        "UNKNOWN",
    ),
    ("prod_payment_orders", "funding_state"): (
        "PENDING",
        "RESERVED",
        "RELEASED",
        "CONSUMED",
        "FAILED",
        "EXPIRED",
        "UNKNOWN",
    ),
    ("prod_payment_orders", "fx_state"): (
        "NOT_REQUIRED",
        "NOT_APPLICABLE",
        "PENDING",
        "QUOTED",
        "ACCEPTANCE_PENDING",
        "READY_TO_ACCEPT",
        "TRADE_ACCEPTED",
        "ACCEPTED",
        "REJECTED",
        "CANCELLED",
        "FAILED",
        "EXPIRED",
        "UNKNOWN",
    ),
    ("prod_payment_orders", "message_delivery_state"): (
        "PENDING",
        "VALIDATED",
        "NETWORK_ACKED",
        "NAK_RECEIVED",
        "DELIVERED",
        "UNDELIVERED",
        "FAILED",
        "UNKNOWN",
    ),
    ("prod_payment_orders", "value_settlement_state"): (
        "PENDING",
        "SUBMITTED",
        "FINAL",
        "FAILED",
        "CANCELLED",
        "UNKNOWN",
    ),
    ("prod_payment_orders", "beneficiary_state"): (
        "PENDING",
        "CREDITED",
        "FAILED",
        "REVERSED",
        "UNKNOWN",
    ),
    ("prod_payment_orders", "reconciliation_state"): (
        "PENDING",
        "UNMATCHED",
        "MATCHED",
        "BREAK",
        "FAILED",
    ),
    ("prod_payment_facts", "state"): (
        "RECEIVED",
        "VALIDATED",
        "APPLIED",
        "PENDING",
        "PASSED",
        "AUTHORIZED",
        "APPROVED",
        "ACCEPTANCE_PENDING",
        "READY_TO_ACCEPT",
        "TRADE_ACCEPTED",
        "ACCEPTED",
        "REJECTED",
        "REQUESTED",
        "VALIDATING",
        "SENT",
        "RESERVED",
        "RELEASED",
        "CONSUMED",
        "FINAL",
        "DELIVERED",
        "NETWORK_ACKED",
        "CREDITED",
        "MATCHED",
        "UNMATCHED",
        "NOT_APPLICABLE",
        "FAILED",
        "EXPIRED",
        "CANCELLED",
        "CLOSED",
        "UNKNOWN",
    ),
    ("prod_funding_reservations", "state"): (
        "PENDING",
        "RESERVED",
        "RELEASED",
        "CONSUMED",
        "FAILED",
        "EXPIRED",
        "UNKNOWN",
    ),
    ("prod_fx_quotes", "status"): ("QUOTED", "ACCEPTED", "EXPIRED", "REJECTED", "CANCELLED", "UNKNOWN"),
    ("prod_fx_trade_intents", "state"): (
        "PREPARING",
        "READY_TO_ACCEPT",
        "REQUESTED",
        "TRADE_ACCEPTED",
        "ACCEPTED",
        "REJECTED",
        "CANCELLED",
        "COMPLETED",
        "FAILED",
        "UNKNOWN",
    ),
    ("prod_fx_trades", "contract_state"): (
        "PREPARING",
        "EXECUTING",
        "TRADE_ACCEPTED",
        "ACCEPTED",
        "EXECUTED",
        "REJECTED",
        "FAILED",
        "CANCELLED",
        "UNKNOWN",
    ),
    ("prod_settlement_legs", "state"): ("PENDING", "SUBMITTED", "FINAL", "FAILED", "CANCELLED", "UNKNOWN"),
    ("prod_beneficiary_credits", "state"): ("UNKNOWN", "PENDING", "CREDITED", "FAILED", "REVERSED"),
    ("prod_reconciliation_runs", "state"): ("UNMATCHED", "MATCHED", "BREAK", "FAILED"),
    ("prod_cancellation_requests", "state"): (
        "REQUESTED",
        "VALIDATING",
        "SENT",
        "ACCEPTED",
        "REJECTED",
        "UNKNOWN",
        "CLOSED",
    ),
    ("prod_investigation_cases", "state"): ("OPEN", "IN_PROGRESS", "CLOSED"),
    ("prod_return_payments", "state"): ("REQUESTED", "SENT", "ACCEPTED", "FINAL", "REJECTED", "UNKNOWN", "CLOSED"),
    ("prod_journals", "state"): ("DRAFT", "VALIDATED", "POSTED", "VOIDED"),
    ("prod_idempotency_keys", "status"): ("STARTED", "COMPLETED", "EXPIRED", "FAILED_RETRYABLE", "FAILED_FINAL"),
    ("prod_key_operation_audits", "status"): ("STARTED", "COMPLETED", "FAILED"),
    ("prod_corridor_admissions", "status"): ("PENDING", "ACTIVE", "EXPIRED", "REVOKED"),
    ("prod_control_attestations", "status"): ("PENDING", "ACTIVE", "EXPIRED", "REVOKED"),
    ("prod_outbox_events", "status"): ("PENDING", "PROCESSING", "PUBLISHED", "DEAD_LETTER"),
    ("prod_standard_artifacts", "status"): ("PENDING", "ACTIVE", "EXPIRED", "REVOKED"),
    ("prod_reconciliation_breaks", "state"): ("OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"),
    ("prod_report_batches", "state"): ("CREATED", "GENERATED", "SUBMITTED", "ACCEPTED", "FAILED"),
    ("prod_report_receipts", "state"): ("PENDING", "RECEIVED", "ACCEPTED", "REJECTED"),
    ("prod_replay_requests", "state"): ("PENDING", "APPROVED"),
    ("prod_payment_timers", "state"): ("SCHEDULED", "FIRED", "CANCELLED"),
    ("prod_holds", "state"): ("REQUESTED", "HELD", "CONSUMED", "RELEASED", "EXPIRED", "UNKNOWN"),
    ("prod_ledger_periods", "state"): ("OPEN", "CLOSED"),
    ("prod_gl_batches", "state"): ("DRAFT", "SENT", "ACK", "REJECTED"),
    ("prod_gl_receipts", "state"): ("ACK", "REJECTED"),
}

V1_COLUMNS: frozenset[StateColumn] = frozenset(
    {
        ("prod_tenants", "status"),
        ("prod_participants", "status"),
        ("prod_entitlements", "status"),
        ("prod_service_identities", "status"),
        ("prod_certificates", "status"),
        ("prod_accounts", "status"),
        ("prod_account_ownerships", "status"),
        ("prod_limit_profiles", "status"),
        ("prod_rulebook_acceptances", "status"),
        ("prod_mandates", "status"),
        ("prod_approvals", "state"),
        ("prod_payment_orders", "orchestration_state"),
        ("prod_payment_facts", "state"),
        ("prod_funding_reservations", "state"),
        ("prod_fx_quotes", "status"),
        ("prod_fx_trade_intents", "state"),
        ("prod_fx_trades", "contract_state"),
        ("prod_settlement_legs", "state"),
        ("prod_beneficiary_credits", "state"),
        ("prod_reconciliation_runs", "state"),
        ("prod_cancellation_requests", "state"),
        ("prod_investigation_cases", "state"),
        ("prod_return_payments", "state"),
        ("prod_journals", "state"),
        ("prod_idempotency_keys", "status"),
        ("prod_key_operation_audits", "status"),
        ("prod_corridor_admissions", "status"),
        ("prod_control_attestations", "status"),
        ("prod_outbox_events", "status"),
        ("prod_standard_artifacts", "status"),
        ("prod_reconciliation_breaks", "state"),
        ("prod_report_batches", "state"),
        ("prod_report_receipts", "state"),
    }
)

SPECIAL_LEGACY_NAMES: dict[StateColumn, str] = {
    ("prod_qualification_artifacts", "status"): "ck_prod_qualification_artifact_status",
}


def _constraint_name(table: str, column: str, version: str) -> str:
    return f"ck_{table}_{column}_state_{version}"


def _legacy_name(table: str, column: str) -> str | None:
    key = (table, column)
    if key in SPECIAL_LEGACY_NAMES:
        return SPECIAL_LEGACY_NAMES[key]
    if key in V1_COLUMNS:
        return _constraint_name(table, column, "v1")
    return None


def _expression(column: str, values: tuple[str, ...]) -> str:
    quoted = ",".join(repr(value) for value in values)
    return f"{column} IN ({quoted})"


def _available_constraints() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    checks = {
        table: {item["name"] for item in inspector.get_check_constraints(table) if item.get("name")}
        for table in tables
    }
    return {table: {column["name"] for column in inspector.get_columns(table)} for table in tables}, checks


def _group_existing(columns: dict[str, set[str]]) -> dict[str, list[tuple[str, tuple[str, ...]]]]:
    grouped: dict[str, list[tuple[str, tuple[str, ...]]]] = defaultdict(list)
    for (table, column), values in V2_CONSTRAINTS.items():
        if table in columns and column in columns[table]:
            grouped[table].append((column, values))
    return grouped


def upgrade() -> None:
    bind = op.get_bind()
    columns, checks = _available_constraints()
    grouped = _group_existing(columns)

    for table, state_columns in grouped.items():
        for column, values in state_columns:
            expression = _expression(column, values)
            invalid = bind.execute(
                sa.text(f'SELECT COUNT(*) FROM "{table}" WHERE NOT ({expression})')
            ).scalar_one()
            if invalid:
                raise RuntimeError(f"Cannot constrain {table}.{column}: {invalid} invalid states")

    for table, state_columns in grouped.items():
        with op.batch_alter_table(table, recreate="always") as batch:
            for column, values in state_columns:
                legacy_name = _legacy_name(table, column)
                if legacy_name and legacy_name in checks.get(table, set()):
                    batch.drop_constraint(legacy_name, type_="check")
                batch.create_check_constraint(
                    _constraint_name(table, column, "v2"),
                    _expression(column, values),
                )


def downgrade() -> None:
    columns, checks = _available_constraints()
    grouped = _group_existing(columns)

    for table, state_columns in reversed(tuple(grouped.items())):
        with op.batch_alter_table(table, recreate="always") as batch:
            for column, values in state_columns:
                v2_name = _constraint_name(table, column, "v2")
                if v2_name in checks.get(table, set()):
                    batch.drop_constraint(v2_name, type_="check")
                legacy_name = _legacy_name(table, column)
                if legacy_name:
                    batch.create_check_constraint(legacy_name, _expression(column, values))
