from __future__ import annotations

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db

from .models import ProductionApproval, utcnow
from .security import ProductionPrincipal, require_production_scope


class ApprovalCreateRequest(BaseModel):
    aggregate_type: str
    aggregate_id: str
    action: str
    reason: str = Field(min_length=1, max_length=500)


class ApprovalDecisionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


def create_pending_approval(request: ApprovalCreateRequest, principal: ProductionPrincipal = Depends(require_production_scope("production.admin")), db: Session = Depends(get_db)):
    approval = ProductionApproval(approval_id=f"apr_{__import__('uuid').uuid4().hex}", aggregate_type=request.aggregate_type, aggregate_id=request.aggregate_id, action=request.action, maker=principal.subject, checker=None, state="PENDING", reason=request.reason)
    db.add(approval)
    db.commit()
    return {"approval_id": approval.approval_id, "state": approval.state, "maker": approval.maker}


def decide_approval(approval_id: str, request: ApprovalDecisionRequest, principal: ProductionPrincipal = Depends(require_production_scope("production.admin")), db: Session = Depends(get_db)):
    approval = db.query(ProductionApproval).filter_by(approval_id=approval_id, state="PENDING").one_or_none()
    if approval is None:
        raise HTTPException(404, "pending approval not found")
    if approval.maker == principal.subject:
        raise HTTPException(409, "maker and checker must be distinct")
    approval.checker = principal.subject
    approval.reason = request.reason
    approval.state = "APPROVED"
    approval.approved_at = utcnow()
    db.commit()
    return {"approval_id": approval.approval_id, "state": approval.state, "checker": approval.checker}
