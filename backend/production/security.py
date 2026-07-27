"""Production participant identity and entitlement enforcement."""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterable
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from auth.oauth import get_token_scopes, verify_bearer_token
from config import get_settings
from database import AppCredential, get_db

from .models import (
    ProductionAccount,
    ProductionAccountOwnership,
    ProductionCertificate,
    ProductionLimitProfile,
    ProductionParticipant,
    ProductionServiceIdentity,
    ProductionTenant,
    utcnow,
)


@dataclass(frozen=True)
class ProductionPrincipal:
    participant_id: str
    subject: str
    scopes: frozenset[str]
    source: str
    credential_id: int | None = None

    @property
    def tenant_id(self) -> str:
        return f"tenant:{self.participant_id}"

    def can(self, scope: str) -> bool:
        if scope in self.scopes:
            return True
        implied = {
            "production.admin": {"production.operator", "production.read", "production.write", "production.worker"},
            "production.operator": {"production.read"},
            "production.worker": {"production.read", "production.write"},
            "production.write": {"production.read"},
        }
        return any(parent in self.scopes and scope in children for parent, children in implied.items())


def _sandbox_principal(participant_id: str | None) -> ProductionPrincipal:
    return ProductionPrincipal(
        participant_id=(participant_id or "SANDBOX-ORIGIN").strip()[:80],
        subject="sandbox-participant",
        scopes=frozenset({
            "production.api",
            "production.read",
            "production.write",
            "production.operator",
            "production.worker",
        }),
        source="sandbox-explicit-header",
    )


def _principal_from_credential(
    credential: AppCredential,
    scopes: Iterable[str],
    db: Session,
) -> ProductionPrincipal:
    identity = (
        db.query(ProductionServiceIdentity)
        .filter(
            ProductionServiceIdentity.credential_id == credential.id,
            ProductionServiceIdentity.status == "ACTIVE",
        )
        .first()
    )
    settings = get_settings()
    if identity is None:
        if not settings.is_sandbox:
            raise HTTPException(403, "Credential is not mapped to an active production identity")
        participant_id = f"SANDBOX-{credential.app_name.strip().upper()[:48]}"
        return ProductionPrincipal(
            participant_id=participant_id,
            subject=credential.cert_subject or credential.app_name,
            scopes=frozenset(scopes),
            source="sandbox-credential",
            credential_id=credential.id,
        )
    _validate_identity_binding(db, identity, settings, utcnow())
    try:
        identity_scopes = set(json.loads(identity.scopes or "[]"))
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(403, "Production identity scopes are invalid") from exc
    effective_scopes = frozenset(set(scopes) & identity_scopes)
    if not effective_scopes:
        raise HTTPException(403, "Credential has no active production scopes")
    return ProductionPrincipal(
        participant_id=identity.participant_id,
        subject=credential.cert_subject or credential.app_name,
        scopes=effective_scopes,
        source="oauth-service-identity",
        credential_id=credential.id,
    )


def _validate_identity_binding(db: Session, identity: ProductionServiceIdentity, settings, now: dt.datetime) -> None:
    if identity.environment != settings.swift_env:
        raise HTTPException(403, "Service identity environment mismatch")
    participant = db.query(ProductionParticipant).filter_by(participant_id=identity.participant_id, status="ACTIVE").one_or_none()
    if participant is None or not participant.tenant_id:
        raise HTTPException(403, "Service identity participant is inactive or unbound")
    if not identity.certificate_fingerprint:
        if not settings.is_sandbox:
            raise HTTPException(403, "Production identity requires a bound certificate")
        return
    certificate = db.query(ProductionCertificate).filter_by(fingerprint=identity.certificate_fingerprint, status="ACTIVE").one_or_none()
    if certificate is None or certificate.participant_id != identity.participant_id:
        raise HTTPException(403, "Service identity certificate binding is invalid")
    not_before = certificate.not_before if certificate.not_before.tzinfo else certificate.not_before.replace(tzinfo=dt.UTC)
    not_after = certificate.not_after if certificate.not_after.tzinfo else certificate.not_after.replace(tzinfo=dt.UTC)
    if not_before > now or not_after <= now:
        raise HTTPException(403, "Service identity certificate is outside its validity window")


def _optional_credential(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> AppCredential | None:
    if not authorization:
        return None
    return verify_bearer_token(authorization, db)


def get_production_principal(
    authorization: str | None = Header(None),
    participant_header: str | None = Header(None, alias="X-Participant-ID"),
    user_role_header: str | None = Header(None, alias="X-User-Role"),
    user_subject_header: str | None = Header(None, alias="X-User-Subject"),
    credential: AppCredential | None = Depends(_optional_credential),
    db: Session = Depends(get_db),
) -> ProductionPrincipal:
    """Resolve trusted identity.

    A participant header is accepted only in sandbox and is marked explicitly
    as sandbox identity. Pilot/live require a bearer token mapped to a
    persisted service identity; role headers are never consulted.
    """

    settings = get_settings()
    if not settings.is_sandbox and any((participant_header, user_role_header, user_subject_header)):
        raise HTTPException(403, "Sandbox identity headers are forbidden outside sandbox")
    if credential is None:
        if not settings.is_sandbox or settings.production_require_auth:
            raise HTTPException(401, "Bearer authentication is required")
        return _sandbox_principal(participant_header)
    return _principal_from_credential(credential, get_token_scopes(authorization, db), db)


def require_production_scope(scope: str):
    def dependency(principal: ProductionPrincipal = Depends(get_production_principal)):
        if not principal.can(scope):
            raise HTTPException(403, {"code": "INSUFFICIENT_SCOPE", "required": scope})
        return principal

    return dependency


def ensure_participant(
    db: Session,
    participant_id: str,
    *,
    name: str | None = None,
    participant_type: str = "BANK",
    jurisdiction: str = "CN",
) -> ProductionParticipant:
    settings = get_settings()
    tenant = ensure_tenant(db, f"tenant:{participant_id}", name or participant_id, jurisdiction)
    participant = (
        db.query(ProductionParticipant).filter_by(participant_id=participant_id).first()
    )
    if participant is None:
        if not settings.is_sandbox:
            raise HTTPException(403, "Participant must be provisioned through identity bootstrap")
        participant = ProductionParticipant(
            participant_id=participant_id,
            name=name or participant_id,
            participant_type=participant_type,
            jurisdiction=jurisdiction,
            status="ACTIVE" if participant_id.startswith("SANDBOX-") else "PENDING",
            rulebook_version="sandbox-v1" if participant_id.startswith("SANDBOX-") else None,
            tenant_id=tenant.tenant_id,
        )
        db.add(participant)
        db.flush()
    return participant


def ensure_tenant(db: Session, tenant_id: str, name: str, jurisdiction: str) -> ProductionTenant:
    settings = get_settings()
    tenant = db.query(ProductionTenant).filter_by(tenant_id=tenant_id).first()
    if tenant is None:
        if not settings.is_sandbox:
            raise HTTPException(403, "Tenant must be provisioned through identity bootstrap")
        tenant = ProductionTenant(
            tenant_id=tenant_id,
            name=name[:200],
            jurisdiction=jurisdiction[:12],
            data_region="sandbox-local" if tenant_id.startswith("tenant:SANDBOX-") else jurisdiction[:12],
            status="ACTIVE" if tenant_id.startswith("tenant:SANDBOX-") else "PENDING",
            rulebook_version="sandbox-v1" if tenant_id.startswith("tenant:SANDBOX-") else None,
        )
        db.add(tenant)
        db.flush()
    return tenant


def assert_account_access(
    db: Session,
    principal: ProductionPrincipal,
    account_id: str,
    currency: str,
    owner_ref: str,
) -> ProductionAccount:
    participant = ensure_participant(db, principal.participant_id)
    account = db.query(ProductionAccount).filter_by(account_id=account_id, tenant_id=principal.tenant_id, participant_id=principal.participant_id).one_or_none()
    if account is None and principal.source.startswith("sandbox"):
        account = ProductionAccount(
            account_id=account_id[:120],
            tenant_id=participant.tenant_id or f"tenant:{principal.participant_id}",
            participant_id=principal.participant_id,
            account_type="SANDBOX",
            currency=currency,
            owner_ref=owner_ref[:160],
            status="ACTIVE",
        )
        db.add(account)
        db.flush()
        db.add(
            ProductionAccountOwnership(
                ownership_id=f"own_{account_id[:40]}",
                account_id=account.account_id,
                participant_id=principal.participant_id,
                role="OWNER",
                status="ACTIVE",
            )
        )
        db.flush()
    if (
        account is None
        or account.status != "ACTIVE"
        or account.participant_id != principal.participant_id
        or account.currency != currency
        or account.owner_ref != owner_ref
    ):
        raise HTTPException(403, {"code": "ACCOUNT_ACCESS_DENIED", "account_id": account_id})
    ownership = db.query(ProductionAccountOwnership).filter(
        ProductionAccountOwnership.account_id == account.account_id,
        ProductionAccountOwnership.participant_id == principal.participant_id,
        ProductionAccountOwnership.status == "ACTIVE",
        ProductionAccountOwnership.effective_from <= utcnow(),
        (ProductionAccountOwnership.effective_to.is_(None) | (ProductionAccountOwnership.effective_to >= utcnow())),
    ).first()
    if ownership is None:
        raise HTTPException(403, {"code": "ACCOUNT_OWNERSHIP_REQUIRED", "account_id": account_id})
    return account


def assert_limit(
    db: Session,
    principal: ProductionPrincipal,
    *,
    service: str,
    corridor: str,
    currency: str,
    amount_minor: int,
) -> None:
    now = utcnow()
    profile = (
        db.query(ProductionLimitProfile)
        .filter(
            ProductionLimitProfile.participant_id == principal.participant_id,
            ProductionLimitProfile.service == service,
            ProductionLimitProfile.status == "ACTIVE",
            ProductionLimitProfile.effective_from <= now,
            (ProductionLimitProfile.effective_to.is_(None) | (ProductionLimitProfile.effective_to >= now)),
            ProductionLimitProfile.corridor.in_(["*", corridor]),
            ProductionLimitProfile.currency.in_(["*", currency]),
        )
        .order_by(ProductionLimitProfile.id.desc())
        .first()
    )
    if profile is None:
        if principal.source.startswith("sandbox"):
            return
        raise HTTPException(403, {"code": "LIMIT_PROFILE_REQUIRED", "service": service})
    if profile.max_amount_minor is not None and amount_minor > profile.max_amount_minor:
        raise HTTPException(403, {"code": "AMOUNT_LIMIT_EXCEEDED", "limit_minor": profile.max_amount_minor})
    if profile.daily_amount_minor is not None:
        from .models import ProductionPaymentOrder

        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        total = sum(
            row.amount_minor
            for row in db.query(ProductionPaymentOrder)
            .filter(
                ProductionPaymentOrder.initiator_participant == principal.participant_id,
                ProductionPaymentOrder.currency == currency,
                ProductionPaymentOrder.created_at >= start,
            )
            .all()
        )
        if total + amount_minor > profile.daily_amount_minor:
            raise HTTPException(403, {"code": "DAILY_LIMIT_EXCEEDED", "limit_minor": profile.daily_amount_minor})


def assert_entitlement(
    db: Session,
    principal: ProductionPrincipal,
    *,
    service: str,
    corridor: str,
    currency: str,
    message_type: str = "*",
    counterparty_id: str = "*",
    direction: str = "OUTBOUND",
    amount_minor: int = 0,
) -> object | None:
    """Enforce default-deny bilateral entitlement.

    Sandbox participants are granted only the local simulation entitlement;
    every pilot/live request must match an active persisted rule.
    """

    participant = ensure_participant(db, principal.participant_id)
    if participant.status != "ACTIVE":
        raise HTTPException(403, "Participant is not active")
    if principal.source.startswith("sandbox"):
        return None
    from .entitlement_service import EntitlementError, EntitlementService

    try:
        return EntitlementService(db).match(
            participant_id=principal.participant_id,
            counterparty_id=counterparty_id,
            direction=direction,
            service=service,
            message_type=message_type,
            corridor=corridor,
            currency=currency,
            amount_minor=amount_minor,
            allow_approved_wildcard=True,
        )
    except EntitlementError as exc:
        raise HTTPException(
            403,
            {
                "code": "ENTITLEMENT_REQUIRED",
                "participant_id": principal.participant_id,
                "service": service,
                "corridor": corridor,
            },
        ) from exc


def scopes_json(principal: ProductionPrincipal) -> str:
    return json.dumps(sorted(principal.scopes), separators=(",", ":"))
