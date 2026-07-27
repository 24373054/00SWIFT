"""Explicit identity lifecycle service; business requests never bootstrap identities."""

from __future__ import annotations

import datetime as dt
import json
import uuid

from sqlalchemy.orm import Session

from .models import (
    ProductionCertificate,
    ProductionParticipant,
    ProductionServiceIdentity,
    ProductionTenant,
    utcnow,
)

LIFECYCLE = {"PENDING", "ACTIVE", "SUSPENDED", "REVOKED"}
TRANSITIONS = {
    "PENDING": {"ACTIVE", "REVOKED"},
    "ACTIVE": {"SUSPENDED", "REVOKED"},
    "SUSPENDED": {"ACTIVE", "REVOKED"},
    "REVOKED": set(),
}


class IdentityLifecycleError(ValueError):
    pass


class IdentityService:
    def __init__(self, db: Session):
        self.db = db

    def bootstrap_tenant(self, *, tenant_id: str, name: str, jurisdiction: str, data_region: str, actor: str) -> ProductionTenant:
        if not actor.strip():
            raise IdentityLifecycleError("bootstrap actor is required")
        if self.db.query(ProductionTenant).filter_by(tenant_id=tenant_id).first():
            raise IdentityLifecycleError("tenant already exists")
        tenant = ProductionTenant(tenant_id=tenant_id[:80], name=name[:200], jurisdiction=jurisdiction[:12], data_region=data_region[:80], status="PENDING")
        self.db.add(tenant)
        self.db.flush()
        return tenant

    def create_participant(self, *, participant_id: str, tenant_id: str, name: str, participant_type: str, jurisdiction: str) -> ProductionParticipant:
        if not self.db.query(ProductionTenant).filter_by(tenant_id=tenant_id, status="ACTIVE").first():
            raise IdentityLifecycleError("active tenant is required")
        if self.db.query(ProductionParticipant).filter_by(participant_id=participant_id).first():
            raise IdentityLifecycleError("participant already exists")
        participant = ProductionParticipant(participant_id=participant_id[:80], tenant_id=tenant_id, name=name[:200], participant_type=participant_type[:40], jurisdiction=jurisdiction[:12], status="PENDING")
        self.db.add(participant)
        self.db.flush()
        return participant

    def create_service_identity(self, *, identity_id: str, participant_id: str, scopes: list[str], environment: str) -> ProductionServiceIdentity:
        if not self.db.query(ProductionParticipant).filter_by(participant_id=participant_id, status="ACTIVE").first():
            raise IdentityLifecycleError("active participant is required")
        identity = ProductionServiceIdentity(identity_id=identity_id[:80], participant_id=participant_id, scopes=json.dumps(sorted(set(scopes))), environment=environment[:20], status="PENDING")
        self.db.add(identity)
        self.db.flush()
        return identity

    def create_certificate(self, *, certificate_id: str, participant_id: str, fingerprint: str, serial_number: str, issuer: str, trust_domain: str, not_before: dt.datetime, not_after: dt.datetime) -> ProductionCertificate:
        if not self.db.query(ProductionParticipant).filter_by(participant_id=participant_id, status="ACTIVE").first():
            raise IdentityLifecycleError("active participant is required")
        if not_after <= not_before:
            raise IdentityLifecycleError("certificate validity window is invalid")
        certificate = ProductionCertificate(certificate_id=certificate_id[:100], participant_id=participant_id, fingerprint=fingerprint[:128], serial_number=serial_number[:160], issuer=issuer[:200], trust_domain=trust_domain[:40], status="PENDING", not_before=not_before, not_after=not_after)
        self.db.add(certificate)
        self.db.flush()
        return certificate

    def transition(self, entity, target: str, *, maker: str, checker: str | None = None) -> None:
        if target not in LIFECYCLE or entity.status not in LIFECYCLE:
            raise IdentityLifecycleError("unknown lifecycle state")
        if target in {"ACTIVE", "REVOKED"} and (not checker or checker == maker):
            raise IdentityLifecycleError("activation/revocation requires distinct maker and checker")
        if target not in TRANSITIONS[entity.status]:
            raise IdentityLifecycleError(f"invalid identity transition {entity.status}->{target}")
        entity.status = target
        if isinstance(entity, ProductionCertificate) and target == "REVOKED":
            entity.revoked_at = utcnow()
        self.db.flush()


def new_identity_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
