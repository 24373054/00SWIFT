"""GPI Tracker v4 schemas (Camt.020/010/060/070 — snake_case JSON).

Aligned with ``research/gpi-v5-demo-app/.../DemoApp.java`` (which uses
``TransactionIndividualStatus5Code.ACCC``) and the SWIFT-API-Guide naming
conventions. The old prototype returned a flat ad-hoc dict with invented
fields (``transaction_status_label``, ``recommendation``); those are removed
(labels/colors move to the frontend via ``/api/states``).
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class Amount(BaseModel):
    amount: str
    currency: str


class Agent(BaseModel):
    bicfi: Optional[str] = None


class Party(BaseModel):
    name: Optional[str] = None


class StatusHistoryEntry(BaseModel):
    status: str
    timestamp: str
    reason: Optional[str] = None
    informing_party: Optional[str] = None


class PaymentTransactionDetails(BaseModel):
    """CamtA0200205 — the response to GET /payments/{uetr}/transactions."""
    uetr: str
    transaction_status: str
    instruction_identification: Optional[str] = None
    end_to_end_identification: Optional[str] = None
    instructing_agent: Optional[Agent] = None
    instructed_agent: Optional[Agent] = None
    debtor: Optional[Party] = None
    creditor: Optional[Party] = None
    settlement_amount: Optional[Amount] = None
    acceptance_result: Optional[str] = None
    last_status_update: Optional[str] = None
    status_history: List[StatusHistoryEntry] = []
    cancellation_status: Optional[str] = None


class ChangedTransactionEntry(BaseModel):
    uetr: str
    transaction_status: str


class ChangedTransactionsReport(BaseModel):
    """CamtA0400205 — paginated list of changed payments in a time window."""
    from_date_time: str
    to_date_time: str
    next: Optional[str] = None
    get_status: List[ChangedTransactionEntry] = []


class StatusConfirmation(BaseModel):
    """CamtA0100105 — body for POST /payments/{uetr}/status."""
    from_: Optional[str] = None  # BIC of informing party
    business_service: Optional[str] = None
    update_payment_scenario: Optional[str] = None
    instruction_identification: Optional[str] = None
    originator: Optional[str] = None
    funds_available: Optional[bool] = None
    transaction_status: str
    confirmed_amount: Optional[Amount] = None


class CancellationRequest(BaseModel):
    """CamtA0600104 — body for POST /payments/{uetr}/cancellation."""
    from_: Optional[str] = None
    business_service: Optional[str] = None
    case_identification: Optional[str] = None
    original_instruction_identification: Optional[str] = None
    cancellation_reason: Optional[str] = "DUPL"
    indemnity_agreement: Optional[bool] = None


class CancellationStatusReport(BaseModel):
    """CamtA0700104 — body for POST /payments/{uetr}/cancellation/status."""
    from_: Optional[str] = None
    business_service: Optional[str] = None
    assignment_identification: Optional[str] = None
    case_identification: Optional[str] = None
    investigation_execution_status: str  # e.g. CNCL
    originator: Optional[str] = None
