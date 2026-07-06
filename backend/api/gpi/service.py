"""GPI Tracker service: payment lookup, status update, cancellation.

Mock tier queries/mutates the ``PaymentState`` table. The old prototype's
invented ``POST /payments/{uetr}/transition`` is removed (user decision 5);
state now moves via ``POST /payments/{uetr}/status`` status-confirmations
(CamtA0100105), matching the real SWIFT tracker.
"""
from __future__ import annotations

import json
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from core.errors import SwiftApiException, malformed_request, resource_not_found, SEVERITY_FATAL
from core.time import now_utc
from database import PaymentState
from iso20022.states import (
    PAYMENT_STATES,
    VALID_TRANSITIONS,
    is_valid_transition,
    CANC,
    ACSC,
    ACCC,
    PDNG,
)


def _row_to_details(p: PaymentState) -> dict:
    """Map a PaymentState row to the CamtA0200205 response shape."""
    history = json.loads(p.history or "[]")
    return {
        "uetr": p.uetr,
        "transaction_status": p.transaction_status,
        "instruction_identification": p.instruction_id,
        "end_to_end_identification": getattr(p, "end_to_end_id", None),
        "instructing_agent": {"bicfi": p.debtor_agent} if p.debtor_agent else None,
        "instructed_agent": {"bicfi": p.creditor_agent} if p.creditor_agent else None,
        "debtor": {"name": p.debtor_name} if p.debtor_name else None,
        "creditor": {"name": p.creditor_name} if p.creditor_name else None,
        "settlement_amount": {"amount": p.amount, "currency": p.currency} if p.amount else None,
        "acceptance_result": None,
        "last_status_update": p.updated_at.isoformat() if p.updated_at else None,
        "status_history": history,
        "cancellation_status": p.transaction_status if p.transaction_status == CANC else None,
    }


def get_payment(db: Session, uetr: str) -> dict:
    p = db.query(PaymentState).filter(PaymentState.uetr == uetr).first()
    if not p:
        raise resource_not_found(f"No GPI payment found for UETR: {uetr}")
    return _row_to_details(p)


def list_changed_payments(
    db: Session,
    from_dt: str,
    to_dt: str,
    maximum_number: int = 50,
    payment_scenario: Optional[str] = None,
) -> dict:
    """List payments whose ``updated_at`` falls in [from_dt, to_dt].

    Real SWIFT uses a ``next`` cursor; we return a simple list (cursor omitted
    for the mock since the dataset is small).
    """
    from core.time import now_utc
    from datetime import datetime, timezone
    try:
        f = datetime.fromisoformat(from_dt.replace("Z", "+00:00"))
        t = datetime.fromisoformat(to_dt.replace("Z", "+00:00"))
    except Exception:
        raise malformed_request("Invalid from_date_time/to_date_time format (use ISO-8601)")

    q = db.query(PaymentState).filter(
        PaymentState.updated_at >= f.replace(tzinfo=None),
        PaymentState.updated_at <= t.replace(tzinfo=None),
    )
    if payment_scenario:
        q = q.filter(PaymentState.payment_scenario == payment_scenario)
    rows = q.order_by(PaymentState.updated_at.desc()).limit(maximum_number).all()
    return {
        "from_date_time": from_dt,
        "to_date_time": to_dt,
        "next": None,
        "get_status": [{"uetr": r.uetr, "transaction_status": r.transaction_status} for r in rows],
    }


def confirm_status(db: Session, uetr: str, body: dict) -> None:
    """Apply a status confirmation (CamtA0100105). Validates the transition."""
    p = db.query(PaymentState).filter(PaymentState.uetr == uetr).first()
    if not p:
        raise resource_not_found(f"Payment {uetr} not found")
    new_status = body.get("transaction_status")
    if new_status not in PAYMENT_STATES:
        raise SwiftApiException("SwAP501", SEVERITY_FATAL, f"Invalid transaction_status: {new_status}", 400)
    if not is_valid_transition(p.transaction_status, new_status):
        valid = VALID_TRANSITIONS.get(p.transaction_status, [])
        raise SwiftApiException(
            "SwAP599", SEVERITY_LOGIC if False else "Fatal",
            f"Cannot transition from {p.transaction_status} to {new_status}. Valid: {valid or 'none (terminal)'}",
            422,
        )
    history = json.loads(p.history or "[]")
    history.append({
        "status": new_status,
        "timestamp": now_utc().isoformat(),
        "reason": "Status confirmation",
        "informing_party": body.get("from_") or body.get("from"),
    })
    p.transaction_status = new_status
    p.state = new_status  # legacy alias
    if body.get("instruction_identification"):
        p.instruction_id = body["instruction_identification"]
    p.history = json.dumps(history)
    p.updated_at = now_utc()
    if body.get("from_") or body.get("from"):
        p.from_bic = body.get("from_") or body.get("from")
    db.commit()


def request_cancellation(db: Session, uetr: str, body: dict) -> dict:
    """Process a cancellation request (CamtA0600104). Moves status to CANC."""
    p = db.query(PaymentState).filter(PaymentState.uetr == uetr).first()
    if not p:
        raise resource_not_found(f"Payment {uetr} not found")
    if not is_valid_transition(p.transaction_status, CANC):
        raise SwiftApiException(
            "SwAP599", SEVERITY_FATAL,
            f"Cannot cancel payment in terminal state {p.transaction_status}",
            422,
        )
    reason = body.get("cancellation_reason", "DUPL")
    history = json.loads(p.history or "[]")
    history.append({
        "status": CANC,
        "timestamp": now_utc().isoformat(),
        "reason": f"Cancellation requested: {reason}",
        "informing_party": body.get("from_") or body.get("from"),
    })
    p.transaction_status = CANC
    p.state = CANC
    p.history = json.dumps(history)
    p.updated_at = now_utc()
    db.commit()
    return {"uetr": uetr, "cancellation_status": "requested", "reason": reason}


def report_cancellation_status(db: Session, uetr: str, body: dict) -> dict:
    """Record the outcome of a cancellation investigation (CamtA0700104)."""
    p = db.query(PaymentState).filter(PaymentState.uetr == uetr).first()
    if not p:
        raise resource_not_found(f"Payment {uetr} not found")
    status = body.get("investigation_execution_status", "CNCL")
    history = json.loads(p.history or "[]")
    history.append({
        "status": p.transaction_status,
        "timestamp": now_utc().isoformat(),
        "reason": f"Cancellation investigation: {status}",
        "informing_party": body.get("from_") or body.get("from"),
    })
    p.history = json.dumps(history)
    p.updated_at = now_utc()
    db.commit()
    return {"uetr": uetr, "investigation_execution_status": status}
