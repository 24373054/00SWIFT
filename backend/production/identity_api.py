"""Controlled identity administration API backed by IdentityService."""

from __future__ import annotations

import datetime as dt

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db

from .identity_service import IdentityLifecycleError, IdentityService
from .models import (
    ProductionCertificate,
    ProductionParticipant,
    ProductionServiceIdentity,
    ProductionTenant,
)
from .security import ProductionPrincipal, require_production_scope


class TenantCreate(BaseModel):
    tenant_id: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    jurisdiction: str = Field(min_length=2, max_length=12)
    data_region: str = Field(min_length=2, max_length=80)


class ParticipantCreate(BaseModel):
    participant_id: str = Field(min_length=2, max_length=80)
    tenant_id: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    participant_type: str = Field(min_length=2, max_length=40)
    jurisdiction: str = Field(min_length=2, max_length=12)


class IdentityCreate(BaseModel):
    identity_id: str = Field(min_length=2, max_length=80)
    participant_id: str = Field(min_length=2, max_length=80)
    scopes: list[str] = Field(default_factory=list)
    environment: str = Field(default="pilot", min_length=2, max_length=20)


class CertificateCreate(BaseModel):
    certificate_id: str = Field(min_length=2, max_length=100)
    participant_id: str = Field(min_length=2, max_length=80)
    fingerprint: str = Field(min_length=16, max_length=128)
    serial_number: str = Field(min_length=1, max_length=160)
    issuer: str = Field(min_length=1, max_length=200)
    trust_domain: str = Field(min_length=1, max_length=40)
    not_before: dt.datetime
    not_after: dt.datetime


class TransitionRequest(BaseModel):
    target: str
    checker: str | None = None


_admin = require_production_scope("production.admin")


def _run(action, db: Session):
    try:
        result = action()
        db.commit()
        return result
    except IdentityLifecycleError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc


def create_tenant(request: TenantCreate, principal: ProductionPrincipal = Depends(_admin), db: Session = Depends(get_db)):
    tenant = _run(lambda: IdentityService(db).bootstrap_tenant(**request.model_dump(), actor=principal.subject), db)
    return {"tenant_id": tenant.tenant_id, "status": tenant.status}


def get_tenant(tenant_id: str, principal: ProductionPrincipal = Depends(_admin), db: Session = Depends(get_db)):
    tenant = db.query(ProductionTenant).filter_by(tenant_id=tenant_id).one_or_none()
    if tenant is None:
        raise HTTPException(404, "tenant not found")
    return {"tenant_id": tenant.tenant_id, "status": tenant.status, "name": tenant.name, "jurisdiction": tenant.jurisdiction}


def create_participant(request: ParticipantCreate, principal: ProductionPrincipal = Depends(_admin), db: Session = Depends(get_db)):
    participant = _run(lambda: IdentityService(db).create_participant(**request.model_dump()), db)
    return {"participant_id": participant.participant_id, "tenant_id": participant.tenant_id, "status": participant.status}


def get_participant(participant_id: str, principal: ProductionPrincipal = Depends(_admin), db: Session = Depends(get_db)):
    participant = db.query(ProductionParticipant).filter_by(participant_id=participant_id).one_or_none()
    if participant is None:
        raise HTTPException(404, "participant not found")
    return {"participant_id": participant.participant_id, "tenant_id": participant.tenant_id, "status": participant.status}


def create_service_identity(request: IdentityCreate, principal: ProductionPrincipal = Depends(_admin), db: Session = Depends(get_db)):
    identity = _run(lambda: IdentityService(db).create_service_identity(**request.model_dump()), db)
    return {"identity_id": identity.identity_id, "participant_id": identity.participant_id, "status": identity.status}


def get_service_identity(identity_id: str, principal: ProductionPrincipal = Depends(_admin), db: Session = Depends(get_db)):
    identity = db.query(ProductionServiceIdentity).filter_by(identity_id=identity_id).one_or_none()
    if identity is None:
        raise HTTPException(404, "service identity not found")
    return {"identity_id": identity.identity_id, "participant_id": identity.participant_id, "status": identity.status}


def create_certificate(request: CertificateCreate, principal: ProductionPrincipal = Depends(_admin), db: Session = Depends(get_db)):
    certificate = _run(lambda: IdentityService(db).create_certificate(**request.model_dump()), db)
    return {"certificate_id": certificate.certificate_id, "participant_id": certificate.participant_id, "status": certificate.status}


def transition_resource(kind: str, resource_id: str, request: TransitionRequest, principal: ProductionPrincipal = Depends(_admin), db: Session = Depends(get_db)):
    model = {"tenant": ProductionTenant, "participant": ProductionParticipant, "service-identity": ProductionServiceIdentity, "certificate": ProductionCertificate}.get(kind)
    field = {"tenant": "tenant_id", "participant": "participant_id", "service-identity": "identity_id", "certificate": "certificate_id"}.get(kind)
    if model is None or field is None:
        raise HTTPException(404, "unknown identity resource")
    entity = db.query(model).filter(getattr(model, field) == resource_id).one_or_none()
    if entity is None:
        raise HTTPException(404, "identity resource not found")
    _run(lambda: IdentityService(db).transition(entity, request.target, maker=principal.subject, checker=request.checker), db)
    return {"resource_id": resource_id, "status": entity.status}


def transition_tenant(tenant_id: str, request: TransitionRequest, principal: ProductionPrincipal = Depends(_admin), db: Session = Depends(get_db)):
    return transition_resource("tenant", tenant_id, request, principal, db)


def transition_participant(participant_id: str, request: TransitionRequest, principal: ProductionPrincipal = Depends(_admin), db: Session = Depends(get_db)):
    return transition_resource("participant", participant_id, request, principal, db)


def transition_service_identity(identity_id: str, request: TransitionRequest, principal: ProductionPrincipal = Depends(_admin), db: Session = Depends(get_db)):
    return transition_resource("service-identity", identity_id, request, principal, db)


def transition_certificate(certificate_id: str, request: TransitionRequest, principal: ProductionPrincipal = Depends(_admin), db: Session = Depends(get_db)):
    return transition_resource("certificate", certificate_id, request, principal, db)
