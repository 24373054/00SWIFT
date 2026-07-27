from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from .connector_recovery import query_or_dispatch
from .models import ProductionInvestigationCase


class RecoveryService:
    def __init__(self, db: Session):
        self.db = db

    def recover(self, order_id: str, client_reference: str, query, dispatch):
        result, dispatched = query_or_dispatch(query, dispatch, client_reference)
        if result.state == "UNKNOWN" or result.evidence.get("query_required"):
            case = ProductionInvestigationCase(case_id=f"case_{uuid.uuid4().hex}", order_id=order_id, case_type="EXTERNAL_OUTCOME_UNKNOWN", priority="P1", reason=f"Unable to determine connector outcome for {client_reference}", evidence_ref=result.evidence.get("evidence_id"))
            self.db.add(case)
            self.db.flush()
            return {"state": "CASE_OPENED", "case_id": case.case_id, "dispatched": dispatched}
        return {"state": result.state, "external_reference": result.external_reference, "dispatched": dispatched}
