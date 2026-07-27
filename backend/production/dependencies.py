"""Unified production route dependency bundles.

The bundle makes identity, scope, tenant, message-integrity, idempotency and
audit context explicit at the route boundary. Individual services still
perform business authorization and state-transition checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from database import get_db

from .integrity import require_request_integrity
from .security import ProductionPrincipal, require_production_scope


@dataclass(frozen=True)
class ProductionDependencyBundle:
    principal: ProductionPrincipal
    db: Session
    tenant_id: str
    idempotency_key: str | None
    integrity: Any
    audit_context: dict[str, Any]


def _audit_context(request: Request) -> dict[str, Any]:
    return {
        "request_id": getattr(request.state, "request_id", None),
        "trace_id": getattr(request.state, "trace_id", None),
        "route": request.url.path,
    }


def require_production_read(
    request: Request,
    principal: ProductionPrincipal = Depends(require_production_scope("production.read")),
    db: Session = Depends(get_db),
) -> ProductionDependencyBundle:
    return ProductionDependencyBundle(
        principal=principal,
        db=db,
        tenant_id=f"tenant:{principal.participant_id}",
        idempotency_key=None,
        integrity=getattr(request.state, "signature_verification", None),
        audit_context=_audit_context(request),
    )


async def require_production_write(
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    principal: ProductionPrincipal = Depends(require_production_scope("production.write")),
    db: Session = Depends(get_db),
    integrity: Any = Depends(require_request_integrity),
) -> ProductionDependencyBundle:
    return ProductionDependencyBundle(
        principal=principal,
        db=db,
        tenant_id=f"tenant:{principal.participant_id}",
        idempotency_key=idempotency_key,
        integrity=integrity,
        audit_context=_audit_context(request),
    )


def require_operator_action(
    request: Request,
    principal: ProductionPrincipal = Depends(require_production_scope("production.operator")),
    db: Session = Depends(get_db),
) -> ProductionDependencyBundle:
    return ProductionDependencyBundle(
        principal=principal,
        db=db,
        tenant_id=f"tenant:{principal.participant_id}",
        idempotency_key=None,
        integrity=getattr(request.state, "signature_verification", None),
        audit_context=_audit_context(request),
    )


def require_admin_action(
    request: Request,
    principal: ProductionPrincipal = Depends(require_production_scope("production.admin")),
    db: Session = Depends(get_db),
) -> ProductionDependencyBundle:
    return ProductionDependencyBundle(
        principal=principal,
        db=db,
        tenant_id=f"tenant:{principal.participant_id}",
        idempotency_key=None,
        integrity=getattr(request.state, "signature_verification", None),
        audit_context=_audit_context(request),
    )
