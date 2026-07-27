from __future__ import annotations

import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import ProductionPaymentOrder, ProductionReturnPayment, ProductionSettlementLeg
from .runtime import ProductionConflict, minor_amount

RETURN_STATES = {"REQUESTED": {"SENT", "REJECTED", "UNKNOWN"}, "SENT": {"ACCEPTED", "REJECTED", "UNKNOWN"}, "ACCEPTED": {"FINAL", "REJECTED", "UNKNOWN"}, "UNKNOWN": {"SENT", "CLOSED"}, "REJECTED": {"CLOSED"}, "FINAL": {"CLOSED"}, "CLOSED": set()}


class ReturnService:
    def __init__(self, db: Session):
        self.db = db

    def create_pending(self, order_id: str, amount: str | int, reason: str) -> tuple[ProductionReturnPayment, ProductionSettlementLeg]:
        order = self.db.query(ProductionPaymentOrder).filter_by(order_id=order_id).with_for_update().one()
        amount_minor = minor_amount(amount, order.currency)
        if order.customer_outcome != "COMPLETED":
            raise ProductionConflict("Only a completed payment can be returned")
        used = self.db.query(func.coalesce(func.sum(ProductionReturnPayment.amount_minor), 0)).filter(ProductionReturnPayment.original_order_id == order_id, ProductionReturnPayment.state.in_(("REQUESTED", "ACCEPTED", "FINAL"))).scalar() or 0
        if used + amount_minor > order.amount_minor:
            raise ProductionConflict("Return amount exceeds original payment")
        sequence = (self.db.query(func.coalesce(func.max(ProductionReturnPayment.return_sequence), 0)).filter_by(original_order_id=order_id).with_for_update().scalar() or 0) + 1
        return_payment = ProductionReturnPayment(return_payment_id=f"ret_{uuid.uuid4().hex}", original_order_id=order.order_id, original_uetr=order.uetr, return_uetr=str(uuid.uuid4()), amount_minor=amount_minor, currency=order.currency, reason=reason[:120], return_sequence=sequence, idempotency_context=f"return-{uuid.uuid4().hex}")
        self.db.add(return_payment)
        self.db.flush()
        leg = ProductionSettlementLeg(leg_id=f"leg_{uuid.uuid4().hex}", order_id=order.order_id, leg_role=f"RETURN:{return_payment.return_payment_id}", connector="sandbox-value-settlement", currency=order.currency, amount_minor=amount_minor, finality_profile_id="sandbox-finality-v1")
        self.db.add(leg)
        return_payment.return_leg_id = leg.leg_id
        self.db.flush()
        return return_payment, leg

    def transition(self, return_payment_id: str, state: str) -> ProductionReturnPayment:
        item = self.db.query(ProductionReturnPayment).filter_by(return_payment_id=return_payment_id).one()
        if state != item.state and state not in RETURN_STATES.get(item.state, set()):
            raise ProductionConflict(f"invalid return transition {item.state} -> {state}")
        item.state = state
        self.db.flush()
        return item
