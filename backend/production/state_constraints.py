"""Versioned state vocabulary shared by domain code and DB migrations."""

from __future__ import annotations

STATE_VERSION = "state-v1"
ALLOWED_STATES = {
    "prod_tenants": {"PENDING", "ACTIVE", "SUSPENDED", "REVOKED"},
    "prod_participants": {"PENDING", "ACTIVE", "SUSPENDED", "REVOKED"},
    "prod_entitlements": {"PENDING", "ACTIVE", "SUSPENDED", "EXPIRED", "REVOKED"},
    "prod_service_identities": {"PENDING", "ACTIVE", "SUSPENDED", "REVOKED"},
    "prod_certificates": {"PENDING", "ACTIVE", "EXPIRED", "REVOKED"},
    "prod_accounts": {"PENDING", "ACTIVE", "SUSPENDED", "CLOSED"},
    "prod_account_ownerships": {"PENDING", "ACTIVE", "EXPIRED", "REVOKED"},
    "prod_limit_profiles": {"PENDING", "ACTIVE", "SUSPENDED", "EXPIRED", "REVOKED"},
    "prod_rulebook_acceptances": {"PENDING", "ACCEPTED", "REJECTED", "EXPIRED"},
    "prod_mandates": {"PENDING", "ACTIVE", "EXPIRED", "REVOKED"},
    "prod_approvals": {"PENDING", "APPROVED", "REJECTED", "EXPIRED"},
    "prod_payment_orders": {"RECEIVED", "CONTROL_CHECKS", "RESERVATION_PENDING", "FX_ACCEPTANCE_PENDING", "FX_ACCEPTED", "MESSAGE_DELIVERED", "VALUE_SETTLEMENT", "CUSTOMER_COMPLETED", "COMPLIANCE_REJECTED", "EXECUTION_CANCELLED", "SUSPENDED", "OPERATIONALLY_CLOSED", "OPERATIONALLY_CLOSED_UNSUCCESSFUL"},
    "prod_payment_facts": {"RECEIVED", "VALIDATED", "ACCEPTED", "REJECTED", "APPLIED"},
    "prod_funding_reservations": {"PENDING", "RESERVED", "RELEASED", "CONSUMED", "FAILED"},
    "prod_fx_quotes": {"QUOTED", "ACCEPTED", "EXPIRED", "REJECTED", "CANCELLED"},
    "prod_fx_trade_intents": {"PREPARING", "REQUESTED", "ACCEPTED", "REJECTED", "CANCELLED", "COMPLETED"},
    "prod_fx_trades": {"PREPARING", "EXECUTING", "EXECUTED", "FAILED", "CANCELLED"},
    "prod_settlement_legs": {"PENDING", "SUBMITTED", "FINAL", "FAILED", "CANCELLED"},
    "prod_beneficiary_credits": {"UNKNOWN", "PENDING", "CREDITED", "FAILED", "REVERSED"},
    "prod_reconciliation_runs": {"UNMATCHED", "MATCHED", "BREAK", "FAILED"},
    "prod_cancellation_requests": {"REQUESTED", "ACCEPTED", "REJECTED", "COMPLETED", "FAILED", "CANCELLED"},
    "prod_investigation_cases": {"OPEN", "IN_PROGRESS", "CLOSED"},
    "prod_return_payments": {"REQUESTED", "APPROVED", "SUBMITTED", "COMPLETED", "REJECTED", "FAILED"},
    "prod_journals": {"DRAFT", "POSTED", "VOIDED"},
    "prod_idempotency_keys": {"STARTED", "COMPLETED", "EXPIRED", "FAILED"},
    "prod_key_operation_audits": {"REQUESTED", "APPROVED", "COMPLETED", "REJECTED", "FAILED"},
    "prod_corridor_admissions": {"PENDING", "ACTIVE", "EXPIRED", "REVOKED"},
    "prod_control_attestations": {"PENDING", "ACTIVE", "EXPIRED", "REVOKED"},
    "prod_outbox_events": {"PENDING", "PROCESSING", "SENT", "FAILED", "DLQ"},
    "prod_standard_artifacts": {"PENDING", "ACTIVE", "EXPIRED", "REVOKED"},
    "prod_reconciliation_breaks": {"OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"},
    "prod_report_batches": {"CREATED", "GENERATED", "SUBMITTED", "ACCEPTED", "FAILED"},
    "prod_report_receipts": {"PENDING", "RECEIVED", "ACCEPTED", "REJECTED"},
}


def assert_state(table: str, state: str) -> str:
    allowed = ALLOWED_STATES.get(table)
    if allowed is None or state not in allowed:
        raise ValueError(f"invalid state for {table}: {state}")
    return state
