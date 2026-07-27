"""Rulebook acceptance with digest, signer and effective-window enforcement."""

from __future__ import annotations

import datetime as dt
import hashlib
import uuid

from sqlalchemy.orm import Session

from .models import ProductionParticipant, ProductionRulebookAcceptance, utcnow


class RulebookError(ValueError):
    pass


class RulebookService:
    def __init__(self, db: Session):
        self.db = db

    def accept(self, *, participant_id: str, rulebook_version: str, document: bytes, document_digest: str, accepted_by: str, signer_subject: str, effective_from: dt.datetime, effective_to: dt.datetime | None, evidence_ref: str) -> ProductionRulebookAcceptance:
        participant = self.db.query(ProductionParticipant).filter_by(participant_id=participant_id, status="ACTIVE").one_or_none()
        if participant is None:
            raise RulebookError("active participant is required")
        if not accepted_by.strip() or accepted_by != signer_subject:
            raise RulebookError("accepted_by must match authenticated signer subject")
        calculated = hashlib.sha256(document).hexdigest()
        if calculated != document_digest:
            raise RulebookError("rulebook document digest mismatch")
        if effective_to is not None and effective_to <= effective_from:
            raise RulebookError("rulebook effective window is invalid")
        if not evidence_ref.strip():
            raise RulebookError("rulebook evidence_ref is required")
        acceptance = ProductionRulebookAcceptance(acceptance_id=f"rba_{uuid.uuid4().hex}", participant_id=participant_id, rulebook_version=rulebook_version[:80], document_digest=document_digest, accepted_by=accepted_by[:200], signer_subject=signer_subject[:200], effective_from=effective_from, effective_to=effective_to, status="ACCEPTED", accepted_at=utcnow(), evidence_ref=evidence_ref[:120])
        self.db.add(acceptance)
        self.db.flush()
        return acceptance

    def assert_current(self, participant_id: str, *, now: dt.datetime | None = None) -> ProductionRulebookAcceptance:
        current = now or utcnow()
        acceptance = self.db.query(ProductionRulebookAcceptance).filter(ProductionRulebookAcceptance.participant_id == participant_id, ProductionRulebookAcceptance.status == "ACCEPTED", ProductionRulebookAcceptance.effective_from <= current, (ProductionRulebookAcceptance.effective_to.is_(None) | (ProductionRulebookAcceptance.effective_to >= current))).order_by(ProductionRulebookAcceptance.effective_from.desc()).first()
        if acceptance is None:
            raise RulebookError("current rulebook acceptance is required")
        return acceptance
