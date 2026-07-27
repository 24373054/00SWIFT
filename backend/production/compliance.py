"""Deterministic sandbox compliance gate with an explicit provider seam."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from .models import ProductionPaymentOrder


class ProductionComplianceService:
    rule_version = "sandbox-screening-v1"

    def __init__(self, db: Session):
        self.db = db

    def evaluate(self, order: ProductionPaymentOrder) -> str:
        payload: dict[str, Any] = json.loads(order.payload)
        purpose = str(payload.get("purpose", {}).get("code", "")).upper()
        blocked_terms = {"SANCTIONS", "TERROR", "PROHIBITED"}
        parties = json.dumps(payload.get("debtor", {}), ensure_ascii=False).upper() + json.dumps(payload.get("creditor", {}), ensure_ascii=False).upper()
        outcome = "REJECTED" if purpose in blocked_terms or any(term in parties for term in blocked_terms) else "PASSED"
        return outcome
