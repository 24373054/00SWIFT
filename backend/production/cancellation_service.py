from __future__ import annotations

from sqlalchemy.orm import Session

from .models import (
    ProductionCancellationRequest,
    ProductionFundingReservation,
    ProductionPaymentOrder,
)
from .runtime import ProductionConflict, ProductionEvidenceService, utcnow
from .service import set_order_state

ALLOWED_CANCELLATION_STATES = {
    "REQUESTED": {"VALIDATING", "REJECTED"},
    "VALIDATING": {"SENT", "REJECTED", "UNKNOWN"},
    "SENT": {"ACCEPTED", "REJECTED", "UNKNOWN"},
    "ACCEPTED": {"CLOSED"},
    "REJECTED": {"CLOSED"},
    "UNKNOWN": {"CLOSED"},
    "CLOSED": set(),
}


class CancellationService:
    def __init__(self, db: Session):
        self.db = db

    def transition(self, request_id: str, state: str) -> ProductionCancellationRequest:
        request = self.db.query(ProductionCancellationRequest).filter_by(cancellation_request_id=request_id).one()
        if state != request.state and state not in ALLOWED_CANCELLATION_STATES.get(request.state, set()):
            raise ProductionConflict(f"invalid cancellation transition {request.state} -> {state}")
        request.state = state
        self.db.flush()
        return request

    def accept(self, request_id: str, *, evidence: dict) -> ProductionCancellationRequest:
        current = self.db.query(ProductionCancellationRequest).filter_by(cancellation_request_id=request_id).one()
        if current.state in {"REQUESTED", "VALIDATING"}:
            current.state = "SENT"
            self.db.flush()
        request = self.transition(request_id, "ACCEPTED")
        order = self.db.query(ProductionPaymentOrder).filter_by(order_id=request.order_id).one()
        for reservation in self.db.query(ProductionFundingReservation).filter_by(order_id=order.order_id, state="RESERVED").with_for_update().all():
            reservation.state = "RELEASED"
            reservation.updated_at = utcnow()
            reservation.evidence_ref = ProductionEvidenceService(self.db).record("funding.release", reservation.reservation_id, evidence).evidence_id
        set_order_state(self.db, order.order_id, "EXECUTION_CANCELLED", "CANCELLED", expected_version=order.version)
        self.db.refresh(order)
        set_order_state(self.db, order.order_id, "OPERATIONALLY_CLOSED_UNSUCCESSFUL", "CANCELLED", expected_version=order.version)
        request.external_reference = evidence.get("external_reference")
        request.evidence_ref = ProductionEvidenceService(self.db).record("payment.cancellation.accepted", request.cancellation_request_id, evidence).evidence_id
        self.db.flush()
        return request
