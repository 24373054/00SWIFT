"""Internal payment management — inject test payments for the tracker flow.

The real SWIFT tracker doesn't create payments (they originate via Messaging);
but the mock needs a way to seed a PaymentState so the tracker endpoints can
be exercised end-to-end. This admin-only endpoint does that.
"""
from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.dependencies import require_admin_token
from core.time import now_utc
from database import PaymentState, get_db
from iso20022.builder import build_pacs008_xml
from iso20022.uetr import generate_uetr
from iso20022.states import PDNG

router = APIRouter(prefix="/api/payments", tags=["Admin — Payments"], dependencies=[Depends(require_admin_token)])


class InjectPaymentRequest(BaseModel):
    amount: str = "10000.00"
    currency: str = "EUR"
    debtor_agent: str = "BANKDEFFXXX"
    creditor_agent: str = "BANKFRPPXXX"
    debtor_name: Optional[str] = "Sender Corp"
    creditor_name: Optional[str] = "Receiver Corp"
    instruction_id: Optional[str] = None
    uetr: Optional[str] = None


@router.get("")
def list_payments(db: Session = Depends(get_db)):
    rows = db.query(PaymentState).order_by(PaymentState.updated_at.desc()).limit(100).all()
    return [
        {
            "id": p.id,
            "uetr": p.uetr,
            "instruction_id": p.instruction_id,
            "amount": p.amount,
            "currency": p.currency,
            "debtor_agent": p.debtor_agent,
            "creditor_agent": p.creditor_agent,
            "transaction_status": p.transaction_status,
            "created_at": p.created_at.isoformat() if p.created_at else "",
            "updated_at": p.updated_at.isoformat() if p.updated_at else "",
        }
        for p in rows
    ]


@router.post("")
def inject_payment(body: InjectPaymentRequest, db: Session = Depends(get_db)):
    """Inject a test payment (PDNG) so tracker endpoints can query/mutate it."""
    uetr = body.uetr or generate_uetr()
    if db.query(PaymentState).filter(PaymentState.uetr == uetr).first():
        raise HTTPException(status_code=409, detail=f"Payment with UETR {uetr} already exists")
    iso_msg = build_pacs008_xml(
        uetr=uetr,
        instruction_id=body.instruction_id,
        amount=body.amount,
        currency=body.currency,
        debtor_name=body.debtor_name or "",
        debtor_agent_bic=body.debtor_agent,
        creditor_name=body.creditor_name or "",
        creditor_agent_bic=body.creditor_agent,
    )
    p = PaymentState(
        uetr=uetr,
        instruction_id=body.instruction_id or f"INSTR-{uuid.uuid4().hex[:12].upper()}",
        amount=body.amount,
        currency=body.currency,
        debtor_agent=body.debtor_agent,
        creditor_agent=body.creditor_agent,
        debtor_name=body.debtor_name,
        creditor_name=body.creditor_name,
        transaction_status=PDNG,
        state=PDNG,
        iso20022_msg=iso_msg,
        history=json.dumps([{"status": PDNG, "timestamp": now_utc().isoformat(), "reason": "Payment initiated"}]),
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(p)
    db.commit()
    return {"uetr": uetr, "transaction_status": PDNG, "iso20022_payload": iso_msg}


@router.delete("/{payment_id}")
def delete_payment(payment_id: int, db: Session = Depends(get_db)):
    p = db.query(PaymentState).filter(PaymentState.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    db.delete(p)
    db.commit()
    return {"status": "deleted"}
