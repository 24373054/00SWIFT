"""GPI Tracker v4 schemas (Camt.020/010/060/070 — snake_case JSON).

Aligned with ``research/gpi-v5-demo-app/.../DemoApp.java`` (which uses
``TransactionIndividualStatus5Code.ACCC``) and the SWIFT-API-Guide naming
conventions. The old prototype returned a flat ad-hoc dict with invented
fields (``transaction_status_label``, ``recommendation``); those are removed
(labels/colors move to the frontend via ``/api/states``).
"""

from __future__ import annotations

from pydantic import BaseModel


class Amount(BaseModel):
    amount: str
    currency: str


class Agent(BaseModel):
    bicfi: str | None = None


class Party(BaseModel):
    name: str | None = None


class StatusHistoryEntry(BaseModel):
    status: str
    timestamp: str
    reason: str | None = None
    informing_party: str | None = None


class PaymentTransactionDetails(BaseModel):
    """CamtA0200205 — the response to GET /payments/{uetr}/transactions."""

    uetr: str
    transaction_status: str
    instruction_identification: str | None = None
    end_to_end_identification: str | None = None
    instructing_agent: Agent | None = None
    instructed_agent: Agent | None = None
    debtor: Party | None = None
    creditor: Party | None = None
    settlement_amount: Amount | None = None
    acceptance_result: str | None = None
    last_status_update: str | None = None
    status_history: list[StatusHistoryEntry] = []
    cancellation_status: str | None = None


class ChangedTransactionEntry(BaseModel):
    uetr: str
    transaction_status: str


class ChangedTransactionsReport(BaseModel):
    """CamtA0400205 — paginated list of changed payments in a time window."""

    from_date_time: str
    to_date_time: str
    next: str | None = None
    get_status: list[ChangedTransactionEntry] = []


class StatusConfirmation(BaseModel):
    """CamtA0100105 — body for POST /payments/{uetr}/status."""

    from_: str | None = None  # BIC of informing party
    business_service: str | None = None
    update_payment_scenario: str | None = None
    instruction_identification: str | None = None
    originator: str | None = None
    funds_available: bool | None = None
    transaction_status: str
    confirmed_amount: Amount | None = None


class CancellationRequest(BaseModel):
    """CamtA0600104 — body for POST /payments/{uetr}/cancellation."""

    from_: str | None = None
    business_service: str | None = None
    case_identification: str | None = None
    original_instruction_identification: str | None = None
    cancellation_reason: str | None = "DUPL"
    indemnity_agreement: bool | None = None


class CancellationStatusReport(BaseModel):
    """CamtA0700104 — body for POST /payments/{uetr}/cancellation/status."""

    from_: str | None = None
    business_service: str | None = None
    assignment_identification: str | None = None
    case_identification: str | None = None
    investigation_execution_status: str  # e.g. CNCL
    originator: str | None = None
