from __future__ import annotations

import datetime as dt
import hashlib

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db

from .models import ProductionRulebookAcceptance
from .rulebook_service import RulebookError, RulebookService
from .security import ProductionPrincipal, require_production_scope


class RulebookAcceptRequest(BaseModel):
    participant_id: str
    rulebook_version: str = Field(min_length=1, max_length=80)
    document: str = Field(min_length=1)
    document_digest: str = Field(min_length=64, max_length=64)
    effective_from: dt.datetime
    effective_to: dt.datetime | None = None
    evidence_ref: str = Field(min_length=1, max_length=120)


def accept_rulebook(request: RulebookAcceptRequest, principal: ProductionPrincipal = Depends(require_production_scope("production.admin")), db: Session = Depends(get_db)):
    try:
        digest = hashlib.sha256(request.document.encode()).hexdigest()
        if digest != request.document_digest:
            raise RulebookError("rulebook document digest mismatch")
        acceptance = RulebookService(db).accept(**request.model_dump(exclude={"document"}), document=request.document.encode(), accepted_by=principal.subject, signer_subject=principal.subject)
        db.commit()
        return {"acceptance_id": acceptance.acceptance_id, "participant_id": acceptance.participant_id, "status": acceptance.status, "document_digest": acceptance.document_digest}
    except RulebookError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc


def list_rulebooks(participant_id: str, principal: ProductionPrincipal = Depends(require_production_scope("production.read")), db: Session = Depends(get_db)):
    if participant_id != principal.participant_id and not principal.can("production.admin"):
        raise HTTPException(403, "participant scope mismatch")
    rows = db.query(ProductionRulebookAcceptance).filter_by(participant_id=participant_id).order_by(ProductionRulebookAcceptance.effective_from.desc()).all()
    return {"items": [{"acceptance_id": row.acceptance_id, "rulebook_version": row.rulebook_version, "status": row.status, "effective_from": row.effective_from, "effective_to": row.effective_to} for row in rows]}
