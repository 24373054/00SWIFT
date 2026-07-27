"""Versioned state vocabulary shared by domain code and DB migrations.

The key includes the column name because a payment order has several
independent state dimensions.  Treating every dimension as one generic
``status`` vocabulary previously allowed invalid projections while rejecting
states that the payment worker actually persists.
"""

from __future__ import annotations

StateColumn = tuple[str, str]

STATE_VERSION = "state-v2"
ALLOWED_STATES: dict[StateColumn, frozenset[str]] = {
    ("prod_tenants", "status"): frozenset({"PENDING", "ACTIVE", "SUSPENDED", "REVOKED"}),
    ("prod_participants", "status"): frozenset({"PENDING", "ACTIVE", "SUSPENDED", "REVOKED"}),
    ("prod_entitlements", "status"): frozenset({"PENDING", "ACTIVE", "SUSPENDED", "EXPIRED", "REVOKED"}),
    ("prod_service_identities", "status"): frozenset({"PENDING", "ACTIVE", "SUSPENDED", "REVOKED"}),
    ("prod_certificates", "status"): frozenset({"PENDING", "ACTIVE", "EXPIRED", "REVOKED"}),
    ("prod_accounts", "status"): frozenset({"PENDING", "ACTIVE", "SUSPENDED", "CLOSED"}),
    ("prod_account_ownerships", "status"): frozenset({"PENDING", "ACTIVE", "EXPIRED", "REVOKED"}),
    ("prod_limit_profiles", "status"): frozenset({"PENDING", "ACTIVE", "SUSPENDED", "EXPIRED", "REVOKED"}),
    ("prod_rulebook_acceptances", "status"): frozenset({"PENDING", "ACCEPTED", "REJECTED", "EXPIRED"}),
    ("prod_mandates", "status"): frozenset({"PENDING", "ACTIVE", "EXPIRED", "REVOKED"}),
    ("prod_approvals", "state"): frozenset({"PENDING", "APPROVED", "REJECTED", "EXPIRED"}),
    ("prod_qualification_artifacts", "status"): frozenset({"VERIFIED", "ACTIVE", "EXPIRED", "REJECTED"}),
    ("prod_delivery_profiles", "required_network_state"): frozenset(
        {"NETWORK_ACKED", "DELIVERED", "BUSINESS_ACCEPTED"}
    ),
    (
        "prod_payment_orders",
        "orchestration_state",
    ): frozenset(
        {
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
        }
    ),
    (
        "prod_payment_orders",
        "authorization_state",
    ): frozenset(
        {
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
        }
    ),
    ("prod_payment_orders", "compliance_state"): frozenset(
        {"PENDING", "PASSED", "REJECTED", "REVIEW_REQUIRED", "UNKNOWN"}
    ),
    ("prod_payment_orders", "funding_state"): frozenset(
        {"PENDING", "RESERVED", "RELEASED", "CONSUMED", "FAILED", "EXPIRED", "UNKNOWN"}
    ),
    ("prod_payment_orders", "fx_state"): frozenset(
        {
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
        }
    ),
    ("prod_payment_orders", "message_delivery_state"): frozenset(
        {
            "PENDING",
            "VALIDATED",
            "NETWORK_ACKED",
            "NAK_RECEIVED",
            "DELIVERED",
            "UNDELIVERED",
            "FAILED",
            "UNKNOWN",
        }
    ),
    ("prod_payment_orders", "value_settlement_state"): frozenset(
        {"PENDING", "SUBMITTED", "FINAL", "FAILED", "CANCELLED", "UNKNOWN"}
    ),
    ("prod_payment_orders", "beneficiary_state"): frozenset(
        {"PENDING", "CREDITED", "FAILED", "REVERSED", "UNKNOWN"}
    ),
    ("prod_payment_orders", "reconciliation_state"): frozenset(
        {"PENDING", "UNMATCHED", "MATCHED", "BREAK", "FAILED"}
    ),
    ("prod_payment_facts", "state"): frozenset(
        {
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
        }
    ),
    ("prod_funding_reservations", "state"): frozenset(
        {"PENDING", "RESERVED", "RELEASED", "CONSUMED", "FAILED", "EXPIRED", "UNKNOWN"}
    ),
    ("prod_fx_quotes", "status"): frozenset(
        {"QUOTED", "ACCEPTED", "EXPIRED", "REJECTED", "CANCELLED", "UNKNOWN"}
    ),
    ("prod_fx_trade_intents", "state"): frozenset(
        {
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
        }
    ),
    ("prod_fx_trades", "contract_state"): frozenset(
        {
            "PREPARING",
            "EXECUTING",
            "TRADE_ACCEPTED",
            "ACCEPTED",
            "EXECUTED",
            "REJECTED",
            "FAILED",
            "CANCELLED",
            "UNKNOWN",
        }
    ),
    ("prod_settlement_legs", "state"): frozenset(
        {"PENDING", "SUBMITTED", "FINAL", "FAILED", "CANCELLED", "UNKNOWN"}
    ),
    ("prod_beneficiary_credits", "state"): frozenset(
        {"UNKNOWN", "PENDING", "CREDITED", "FAILED", "REVERSED"}
    ),
    ("prod_reconciliation_runs", "state"): frozenset({"UNMATCHED", "MATCHED", "BREAK", "FAILED"}),
    ("prod_cancellation_requests", "state"): frozenset(
        {"REQUESTED", "VALIDATING", "SENT", "ACCEPTED", "REJECTED", "UNKNOWN", "CLOSED"}
    ),
    ("prod_investigation_cases", "state"): frozenset({"OPEN", "IN_PROGRESS", "CLOSED"}),
    ("prod_return_payments", "state"): frozenset(
        {"REQUESTED", "SENT", "ACCEPTED", "FINAL", "REJECTED", "UNKNOWN", "CLOSED"}
    ),
    ("prod_journals", "state"): frozenset({"DRAFT", "VALIDATED", "POSTED", "VOIDED"}),
    ("prod_idempotency_keys", "status"): frozenset(
        {"STARTED", "COMPLETED", "EXPIRED", "FAILED_RETRYABLE", "FAILED_FINAL"}
    ),
    ("prod_key_operation_audits", "status"): frozenset({"STARTED", "COMPLETED", "FAILED"}),
    ("prod_corridor_admissions", "status"): frozenset({"PENDING", "ACTIVE", "EXPIRED", "REVOKED"}),
    ("prod_control_attestations", "status"): frozenset({"PENDING", "ACTIVE", "EXPIRED", "REVOKED"}),
    ("prod_outbox_events", "status"): frozenset({"PENDING", "PROCESSING", "PUBLISHED", "DEAD_LETTER"}),
    ("prod_standard_artifacts", "status"): frozenset({"PENDING", "ACTIVE", "EXPIRED", "REVOKED"}),
    ("prod_reconciliation_breaks", "state"): frozenset({"OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"}),
    ("prod_report_batches", "state"): frozenset({"CREATED", "GENERATED", "SUBMITTED", "ACCEPTED", "FAILED"}),
    ("prod_report_receipts", "state"): frozenset({"PENDING", "RECEIVED", "ACCEPTED", "REJECTED"}),
    ("prod_replay_requests", "state"): frozenset({"PENDING", "APPROVED"}),
    ("prod_payment_timers", "state"): frozenset({"SCHEDULED", "FIRED", "CANCELLED"}),
    ("prod_holds", "state"): frozenset({"REQUESTED", "HELD", "CONSUMED", "RELEASED", "EXPIRED", "UNKNOWN"}),
    ("prod_ledger_periods", "state"): frozenset({"OPEN", "CLOSED"}),
    ("prod_gl_batches", "state"): frozenset({"DRAFT", "SENT", "ACK", "REJECTED"}),
    ("prod_gl_receipts", "state"): frozenset({"ACK", "REJECTED"}),
}


def assert_state(table: str, column: str, state: str) -> str:
    allowed = ALLOWED_STATES.get((table, column))
    if allowed is None or state not in allowed:
        raise ValueError(f"invalid state for {table}.{column}: {state}")
    return state
