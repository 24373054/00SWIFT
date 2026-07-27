"""Bilateral entitlement policy service with explicit amount bands and versions."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.orm import Session

from .models import ProductionEntitlement, utcnow


class EntitlementError(ValueError):
    pass


class EntitlementService:
    def __init__(self, db: Session):
        self.db = db

    def create_pending(self, *, participant_id: str, counterparty_id: str, direction: str, service: str, message_type: str, corridor: str, currency: str, min_amount_minor: int, max_amount_minor: int, effective_from: dt.datetime, effective_to: dt.datetime | None, version: int, evidence_ref: str | None) -> ProductionEntitlement:
        if min_amount_minor < 0 or max_amount_minor < min_amount_minor:
            raise EntitlementError("invalid entitlement amount band")
        if effective_to is not None and effective_to <= effective_from:
            raise EntitlementError("invalid entitlement effective window")
        entitlement = ProductionEntitlement(entitlement_id=f"ent_{uuid.uuid4().hex}", participant_id=participant_id, counterparty_id=counterparty_id, direction=direction, service=service, message_type=message_type, corridor=corridor, currency=currency.upper(), min_amount_minor=min_amount_minor, max_amount_minor=max_amount_minor, version=version, status="PENDING", effective_from=effective_from, effective_to=effective_to, evidence_ref=evidence_ref)
        self.db.add(entitlement)
        self.db.flush()
        return entitlement

    def activate(self, entitlement: ProductionEntitlement, *, maker: str, checker: str, approved_by: str) -> None:
        if entitlement.status != "PENDING" or maker == checker or not approved_by.strip():
            raise EntitlementError("entitlement activation requires pending record, approval and distinct maker/checker")
        entitlement.status = "ACTIVE"
        entitlement.approved_by = approved_by
        self.db.flush()

    def revoke(self, entitlement: ProductionEntitlement, *, maker: str, checker: str) -> None:
        if entitlement.status != "ACTIVE" or maker == checker:
            raise EntitlementError("entitlement revocation requires active record and distinct maker/checker")
        entitlement.status = "REVOKED"
        self.db.flush()

    def match(self, *, participant_id: str, counterparty_id: str, direction: str, service: str, message_type: str, corridor: str, currency: str, amount_minor: int, now: dt.datetime | None = None, allow_approved_wildcard: bool = False) -> ProductionEntitlement:
        current = now or utcnow()
        rows = self.db.query(ProductionEntitlement).filter(ProductionEntitlement.participant_id == participant_id, ProductionEntitlement.service == service, ProductionEntitlement.status == "ACTIVE", ProductionEntitlement.effective_from <= current, (ProductionEntitlement.effective_to.is_(None) | (ProductionEntitlement.effective_to >= current)), ProductionEntitlement.min_amount_minor <= amount_minor, ProductionEntitlement.max_amount_minor >= amount_minor).order_by(ProductionEntitlement.version.desc(), ProductionEntitlement.id.desc()).all()
        for row in rows:
            wildcard = "*" in {row.counterparty_id, row.direction, row.message_type, row.corridor, row.currency}
            if wildcard and not allow_approved_wildcard:
                continue
            if row.counterparty_id not in {"*", counterparty_id} or row.direction not in {"*", direction} or row.message_type not in {"*", message_type} or row.corridor not in {"*", corridor} or row.currency not in {"*", currency.upper()}:
                continue
            if wildcard and (not row.approved_by or not row.evidence_ref):
                continue
            return row
        raise EntitlementError("bilateral entitlement not found")
