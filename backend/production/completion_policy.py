from __future__ import annotations

import json

from sqlalchemy import text

from config import get_settings

from .models import (
    ProductionCompletionProfile,
    ProductionFundingReservation,
    ProductionInvestigationCase,
    ProductionPaymentFact,
    ProductionPaymentOrder,
    ProductionReconciliationRun,
    ProductionSettlementLeg,
)


class CompletionPolicyEvaluator:
    def __init__(self, db):
        self.db = db

    def evaluate(self, order: ProductionPaymentOrder) -> dict:
        profile = self.db.query(ProductionCompletionProfile).filter_by(profile_id=order.completion_profile_id, active=True).one()
        facts = self.db.query(ProductionPaymentFact).filter_by(order_id=order.order_id).all()
        latest = {}
        for fact in facts:
            key = (fact.fact_type, fact.reference)
            if key not in latest or fact.fact_sequence > latest[key].fact_sequence:
                latest[key] = fact
        required = []
        for field in ("required_messages", "required_funding", "required_fx", "required_settlement", "required_credits"):
            required.extend(json.loads(getattr(profile, field) or "[]"))
        category = {"payment-message": "MESSAGE", "debit": "FUNDING", "credit": "FUNDING", "PAYMENT_VALUE": "SETTLEMENT", "beneficiary": "BENEFICIARY"}
        missing = [item for item in required if not any(item in (fact.reference or "") or category.get(item) == fact.fact_type for fact in latest.values())]
        reservations = self.db.query(ProductionFundingReservation).filter_by(order_id=order.order_id).filter(ProductionFundingReservation.state.in_(("RESERVED", "PENDING"))).count()
        cases = self.db.query(ProductionInvestigationCase).filter_by(order_id=order.order_id).filter(ProductionInvestigationCase.state.in_(("OPEN", "PENDING"))).count()
        reconciliation = self.db.query(ProductionReconciliationRun).filter_by(order_id=order.order_id, state="MATCHED").first()
        final_legs = self.db.query(ProductionSettlementLeg).filter_by(order_id=order.order_id).all()
        finality_ok = bool(final_legs) and all(leg.state == "FINAL" for leg in final_legs)
        strict_external = not get_settings().is_sandbox
        if strict_external:
            journals = self.db.execute(text("SELECT COUNT(*) FROM prod_journals WHERE order_id=:order_id"), {"order_id": order.order_id}).scalar_one()
        else:
            journals = 1
        return {"allowed": not missing and reservations == 0 and cases == 0 and reconciliation is not None and finality_ok and journals > 0, "missing": missing, "reservations": reservations, "cases": cases, "reconciliation": reconciliation is not None, "finality": finality_ok, "journals": journals, "profile_id": profile.profile_id, "profile_version": profile.projection_rule_version}
