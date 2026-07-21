"""Institutional UI read models and backend-authoritative RBAC/ABAC decisions."""

from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import require_admin_token
from config import get_settings
from database import get_db
from nextgen.models import (
    CipsAccount,
    CipsSettlement,
    PaymentCase,
    PaymentLensEvent,
    PaymentLifecycle,
    PvpSettlement,
)
from nextgen.platform import PolicyEngine
from version import __version__

router = APIRouter(prefix="/nextgen/v1/ui", tags=["Institutional UI"])

RoleName = Literal[
    "executive_viewer",
    "settlement_operator",
    "payment_operations",
    "compliance_investigator",
    "standards_engineer",
    "cbdc_researcher",
    "platform_administrator",
]

WORKSPACES = (
    ("command", "Command Center", "指挥中心"),
    ("payments", "Payments", "支付运营"),
    ("investigations", "Investigations", "调查与案件"),
    ("settlement", "Settlement", "清算结算"),
    ("standards", "Standards", "标准与报文"),
    ("digital-currency", "Digital Currency", "数字货币"),
    ("risk-policy", "Risk & Policy", "风险与政策"),
    ("developer", "Developer", "开发者"),
    ("administration", "Administration", "系统管理"),
)

ROLE_LABELS = {
    "executive_viewer": ("Executive Viewer", "高层观察员"),
    "settlement_operator": ("Settlement Operator", "结算操作员"),
    "payment_operations": ("Payment Operations Analyst", "支付运营分析员"),
    "compliance_investigator": ("Compliance Investigator", "合规调查员"),
    "standards_engineer": ("Standards Engineer", "标准工程师"),
    "cbdc_researcher": ("CBDC Researcher", "数字货币研究员"),
    "platform_administrator": ("Platform Administrator", "平台管理员"),
}

ROLE_WORKSPACES = {
    "executive_viewer": {"command", "payments", "settlement", "risk-policy"},
    "settlement_operator": {
        "command",
        "payments",
        "settlement",
        "digital-currency",
        "risk-policy",
    },
    "payment_operations": {
        "command",
        "payments",
        "investigations",
        "standards",
        "risk-policy",
    },
    "compliance_investigator": {
        "command",
        "payments",
        "investigations",
        "risk-policy",
    },
    "standards_engineer": {"command", "payments", "standards", "developer"},
    "cbdc_researcher": {
        "command",
        "settlement",
        "digital-currency",
        "risk-policy",
    },
    "platform_administrator": {item[0] for item in WORKSPACES},
}

MUTATING_ACTIONS = {
    "settlement.release",
    "pvp.commit",
    "policy.change",
    "case.close",
    "administrator.configure",
}

_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "institutional_ui.json"


class AuthorizationRequest(BaseModel):
    action: str = Field(min_length=1, max_length=120)
    resource: str = Field(min_length=1, max_length=160)
    amount: int = Field(default=0, ge=0)
    jurisdiction: str | None = Field(default=None, max_length=12)
    purpose: str | None = Field(default=None, max_length=80)


def _role(value: str | None) -> RoleName:
    normalized = (value or "executive_viewer").strip().lower().replace("-", "_")
    if normalized not in ROLE_WORKSPACES:
        raise HTTPException(422, f"Unknown institutional role: {normalized}")
    return cast(RoleName, normalized)


def _read_representative_payload() -> dict[str, Any]:
    with _DATA_PATH.open(encoding="utf-8") as handle:
        return cast(dict[str, Any], json.load(handle))


def _evaluate(
    db: Session,
    *,
    subject: str,
    role: RoleName,
    action: str,
    resource: str,
    amount: int = 0,
    jurisdiction: str | None = None,
    purpose: str | None = None,
) -> dict[str, Any]:
    workspace = resource.removeprefix("workspace.").split(".", 1)[0]
    role_allows = workspace in ROLE_WORKSPACES[role]
    max_amount = (
        250_000_000
        if role in {"settlement_operator", "platform_administrator"}
        else 25_000_000
    )
    decision = PolicyEngine(db).evaluate(
        subject=subject,
        action=action,
        resource=resource,
        context={
            "roles": [role],
            "amount": amount,
            "jurisdiction": jurisdiction,
            "purpose": purpose,
        },
        policy={
            "required_roles": [role if role_allows else "__denied__"],
            "max_amount": max_amount,
            "allowed_jurisdictions": ["CN", "HK", "TH", "AE"] if jurisdiction else [],
            "allowed_purposes": (
                ["trade", "services", "treasury", "retail"] if purpose else []
            ),
        },
    )
    obligations: list[str] = []
    if decision.result == "allow" and action in MUTATING_ACTIONS:
        obligations.append("append_audit_evidence")
        if amount >= 10_000_000:
            obligations.extend(["dual_approval", "record_operator_reason"])
    redactions = (
        []
        if role in {"compliance_investigator", "platform_administrator"}
        else [
            "payment.party.account",
            "wallet.phone_hash",
            "case.personal_identifiers",
        ]
    )
    return {
        "decision_id": decision.decision_id,
        "subject": decision.subject,
        "action": decision.action,
        "resource": decision.resource,
        "result": decision.result,
        "reasons": json.loads(decision.reasons),
        "obligations": obligations,
        "redactions": redactions,
        "policy_version": "ui-v4.0.0",
    }


@router.get("/bootstrap")
def bootstrap(
    x_user_role: str | None = Header(None, alias="X-User-Role"),
    x_user_subject: str | None = Header(None, alias="X-User-Subject"),
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    role = _role(x_user_role)
    subject = (x_user_subject or "sandbox-user").strip()[:120]
    decision = _evaluate(
        db,
        subject=subject,
        role=role,
        action="view",
        resource="workspace.command",
    )
    db.commit()
    settings = get_settings()
    role_label, role_label_zh = ROLE_LABELS[role]
    return {
        "product": {
            "name": "Cross-Border Payment Infrastructure Lab",
            "version": __version__,
            "environment": settings.swift_env,
            "data_mode": "representative" if settings.is_sandbox else "live",
            "independent_sandbox": True,
        },
        "identity": {
            "subject": subject,
            "role": role,
            "role_label": role_label,
            "role_label_zh": role_label_zh,
            "source": "admin-token-plus-role-attribute",
        },
        "workspaces": [
            {
                "id": workspace_id,
                "label": label,
                "label_zh": label_zh,
                "enabled": workspace_id in ROLE_WORKSPACES[role],
                "reason": (
                    None
                    if workspace_id in ROLE_WORKSPACES[role]
                    else f"Role {role} is not entitled to workspace.{workspace_id}"
                ),
            }
            for workspace_id, label, label_zh in WORKSPACES
        ],
        "permissions": sorted(f"view:{item}" for item in ROLE_WORKSPACES[role]),
        "decision": decision,
    }


@router.post("/authorize")
def authorize(
    request: AuthorizationRequest,
    x_user_role: str | None = Header(None, alias="X-User-Role"),
    x_user_subject: str | None = Header(None, alias="X-User-Subject"),
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    decision = _evaluate(
        db,
        subject=(x_user_subject or "sandbox-user").strip()[:120],
        role=_role(x_user_role),
        action=request.action,
        resource=request.resource,
        amount=request.amount,
        jurisdiction=request.jurisdiction,
        purpose=request.purpose,
    )
    db.commit()
    return decision


def _overlay_database(payload: dict[str, Any], db: Session) -> None:
    lifecycles = db.query(PaymentLifecycle).all()
    settlements = db.query(CipsSettlement).all()
    accounts = db.query(CipsAccount).all()
    cases = db.query(PaymentCase).filter(PaymentCase.status != "CLOSED").all()
    pvp_items = db.query(PvpSettlement).all()
    if not any((lifecycles, settlements, accounts, cases, pvp_items)):
        return

    payload["data_mode"] = "live"
    payload["totals"].update(
        {
            "cross_border_volume": sum(item.amount for item in settlements),
            "active_payments": sum(
                item.status not in {"SETTLED", "REJECTED", "CANCELLED"}
                for item in lifecycles
            ),
            "queued_value": sum(
                item.amount for item in settlements if item.status == "QUEUED"
            ),
            "open_cases": len(cases),
            "available_liquidity": sum(
                max(item.balance - item.reserved, 0) for item in accounts
            ),
            "reserved_liquidity": sum(item.reserved for item in accounts),
        }
    )
    if accounts:
        payload["liquidity"] = [
            {
                "participant": account.participant_id,
                "opening": account.balance,
                "balance": account.balance,
                "reserved": account.reserved,
                "queued": sum(
                    item.amount
                    for item in settlements
                    if item.debtor_participant == account.participant_id
                    and item.status == "QUEUED"
                ),
                "expected_incoming": sum(
                    item.amount
                    for item in settlements
                    if item.creditor_participant == account.participant_id
                    and item.status == "QUEUED"
                ),
                "currency": account.currency,
            }
            for account in accounts
        ]
    events = (
        db.query(PaymentLensEvent)
        .order_by(PaymentLensEvent.id.desc())
        .limit(8)
        .all()
    )
    if events:
        payload["events"] = [
            {
                "id": f"EV-{event.id}",
                "time": event.created_at.strftime("%H:%M:%S"),
                "system": event.system,
                "type": event.event_type,
                "state": event.status,
                "text": event.event_type.replace("_", " ").title(),
                "text_zh": event.event_type.replace("_", " "),
            }
            for event in events
        ]


@router.get("/command-center")
def command_center(
    x_user_role: str | None = Header(None, alias="X-User-Role"),
    x_user_subject: str | None = Header(None, alias="X-User-Subject"),
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    role = _role(x_user_role)
    subject = (x_user_subject or "sandbox-user").strip()[:120]
    decision = _evaluate(
        db,
        subject=subject,
        role=role,
        action="view",
        resource="workspace.command",
    )
    if decision["result"] != "allow":
        db.rollback()
        raise HTTPException(403, detail=decision)

    payload = copy.deepcopy(_read_representative_payload())
    payload["generated_at"] = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    _overlay_database(payload, db)
    payload["authorization"] = decision
    db.commit()
    return payload
