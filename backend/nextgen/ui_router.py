"""Institutional UI read models and backend-authoritative RBAC/ABAC decisions."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import require_admin_token
from config import get_settings
from database import get_db
from nextgen.models import CipsAccount, CipsSettlement, PaymentCase, PaymentLensEvent, PaymentLifecycle, PvpSettlement
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
    "settlement_operator": {"command", "payments", "settlement", "digital-currency", "risk-policy"},
    "payment_operations": {"command", "payments", "investigations", "standards", "risk-policy"},
    "compliance_investigator": {"command", "payments", "investigations", "risk-policy"},
    "standards_engineer": {"command", "payments", "standards", "developer"},
    "cbdc_researcher": {"command", "settlement", "digital-currency", "risk-policy"},
    "platform_administrator": {item[0] for item in WORKSPACES},
}

MUTATING_ACTIONS = {"settlement.release", "pvp.commit", "policy.change", "case.close", "administrator.configure"}


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
    role_allows = workspace in ROLE_WORKSPACES[role] or role == "platform_administrator"
    max_amount = 250_000_000 if role in {"settlement_operator", "platform_administrator"} else 25_000_000
    decision = PolicyEngine(db).evaluate(
        subject=subject,
        action=action,
        resource=resource,
        context={"roles": [role], "amount": amount, "jurisdiction": jurisdiction, "purpose": purpose},
        policy={
            "required_roles": [role if role_allows else "__denied__"],
            "max_amount": max_amount,
            "allowed_jurisdictions": ["CN", "HK", "TH", "AE"] if jurisdiction else [],
            "allowed_purposes": ["trade", "services", "treasury", "retail"] if purpose else [],
        },
    )
    obligations: list[str] = []
    if decision.result == "allow" and action in MUTATING_ACTIONS:
        obligations.append("append_audit_evidence")
        if amount >= 10_000_000:
            obligations.extend(["dual_approval", "record_operator_reason"])
    redactions = [] if role in {"compliance_investigator", "platform_administrator"} else [
        "payment.party.account",
        "wallet.phone_hash",
        "case.personal_identifiers",
    ]
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
    decision = _evaluate(db, subject=subject, role=role, action="view", resource="workspace.command")
    db.commit()
    settings = get_settings()
    label, label_zh = ROLE_LABELS[role]
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
            "role_label": label,
            "role_label_zh": label_zh,
            "source": "admin-token-plus-role-attribute",
        },
        "workspaces": [
            {
                "id": workspace_id,
                "label": label_en,
                "label_zh": label_cn,
                "enabled": workspace_id in ROLE_WORKSPACES[role],
                "reason": None if workspace_id in ROLE_WORKSPACES[role] else f"Role {role} is not entitled to workspace.{workspace_id}",
            }
            for workspace_id, label_en, label_cn in WORKSPACES
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
    role = _role(x_user_role)
    decision = _evaluate(
        db,
        subject=(x_user_subject or "sandbox-user").strip()[:120],
        role=role,
        action=request.action,
        resource=request.resource,
        amount=request.amount,
        jurisdiction=request.jurisdiction,
        purpose=request.purpose,
    )
    db.commit()
    return decision


def _scenario(identifier: str, name: str, name_zh: str, expected: str, events: list[tuple[int, str, str, str, str]]) -> dict[str, Any]:
    return {
        "id": identifier,
        "name": name,
        "name_zh": name_zh,
        "duration": events[-1][0],
        "expected_state": expected,
        "events": [
            {
                "at": at,
                "system": system,
                "title": title,
                "title_zh": title_zh,
                "detail": detail,
                "detail_zh": detail,
                "state": state,
                "focus": "settlement" if system in {"CIPS", "RTGS", "PvP", "Liquidity"} else "payments",
            }
            for at, system, title, title_zh, state, detail in [
                (item[0], item[1], item[2], item[3], item[4], item[2]) for item in events
            ]
        ],
    }


def _representative_payload() -> dict[str, Any]:
    now = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    scenarios = [
        _scenario(
            "normal-cross-border",
            "Normal cross-border payment",
            "正常跨境支付",
            "SETTLED",
            [
                (0, "Origin Bank", "Payment initiated", "付款发起", "INITIATED"),
                (14, "Standards", "SR2026 validation passed", "SR2026 校验通过", "VALIDATED"),
                (29, "CIPS", "Direct participant selected", "选择直接参与者", "ROUTED"),
                (47, "RTGS", "Liquidity reserved", "流动性已预留", "RESERVED"),
                (66, "PvP", "Both legs committed", "双腿原子提交", "COMMITTED"),
                (84, "Tracker", "Universal confirmation received", "收到通用确认", "SETTLED"),
            ],
        ),
        _scenario(
            "rtgs-liquidity-release",
            "RTGS liquidity shortage and release",
            "RTGS 流动性不足与释放",
            "SETTLED_AFTER_QUEUE",
            [
                (0, "RTGS", "Payment queued", "支付进入队列", "QUEUED"),
                (25, "Liquidity", "Incoming dependency detected", "识别入账依赖", "DEPENDENCY"),
                (51, "RTGS", "Incoming payment settled", "入账支付完成", "FUNDED"),
                (73, "CIPS", "Priority release executed", "执行优先级释放", "RELEASED"),
                (96, "Tracker", "Queue cleared", "队列清空", "SETTLED_AFTER_QUEUE"),
            ],
        ),
        _scenario(
            "pvp-rollback",
            "PvP second-leg failure and rollback",
            "PvP 第二腿失败与回滚",
            "ABORTED",
            [
                (0, "FX", "Quote validated", "报价有效", "QUOTE_VALID"),
                (17, "Policy", "Jurisdiction policy allowed", "法域政策允许", "AUTHORIZED"),
                (34, "PvP", "CNY leg locked", "人民币腿锁定", "LEG_A_LOCKED"),
                (49, "PvP", "HKD leg rejected", "港币腿被拒绝", "LEG_B_FAILED"),
                (61, "PvP", "Atomic rollback", "原子回滚", "ROLLBACK"),
                (72, "Audit", "Abort evidence sealed", "终止证据封存", "ABORTED"),
            ],
        ),
    ]
    return {
        "generated_at": now,
        "data_mode": "representative",
        "totals": {
            "cross_border_volume": 12_845_000_000,
            "currency": "CNY",
            "active_payments": 1842,
            "queued_value": 438_000_000,
            "open_cases": 17,
            "available_liquidity": 7_200_000_000,
            "reserved_liquidity": 1_180_000_000,
            "system_availability": 99.982,
        },
        "corridors": [
            {"id": "cn-hk", "from": "Beijing", "to": "Hong Kong", "from_country": "CN", "to_country": "HK", "volume": 4_200_000_000, "currency": "CNY", "state": "settled", "channel": "CIPS / e-CNY", "message_state": "delivered", "value_state": "reserved", "settlement_state": "settled", "start": [-3.2, 0.7, 0.1], "end": [-1.7, -0.15, 0.55]},
            {"id": "cn-th", "from": "Shanghai", "to": "Bangkok", "from_country": "CN", "to_country": "TH", "volume": 2_810_000_000, "currency": "CNY", "state": "moving", "channel": "CIPS / PvP", "message_state": "accepted", "value_state": "locked", "settlement_state": "pending", "start": [-2.1, 0.4, -0.1], "end": [0.0, -1.1, 0.35]},
            {"id": "cn-ae", "from": "Shenzhen", "to": "Abu Dhabi", "from_country": "CN", "to_country": "AE", "volume": 1_780_000_000, "currency": "CNY", "state": "queued", "channel": "Multi-CBDC", "message_state": "delivered", "value_state": "reserved", "settlement_state": "queued", "start": [-1.9, -0.2, -0.1], "end": [2.6, -0.25, 0.7]},
            {"id": "hk-gb", "from": "Hong Kong", "to": "London", "from_country": "HK", "to_country": "GB", "volume": 1_410_000_000, "currency": "HKD", "state": "blocked", "channel": "SWIFT / PvP", "message_state": "delivered", "value_state": "not-moved", "settlement_state": "policy-blocked", "start": [-1.7, -0.15, 0.55], "end": [3.4, 1.35, 0.2]},
        ],
        "interventions": [
            {"id": "INT-0041", "severity": "critical", "title": "PvP second leg rejected", "title_zh": "PvP 第二腿被拒绝", "owner": "Settlement Ops", "due": "06:18", "reason": "HKD counterparty liquidity below reserved amount", "reason_zh": "港币对手方流动性低于预留金额"},
            {"id": "INT-0037", "severity": "warning", "title": "RTGS queue approaching SLA", "title_zh": "RTGS 队列接近 SLA", "owner": "Liquidity Desk", "due": "11:42", "reason": "Three priority payments depend on one incoming settlement", "reason_zh": "三笔优先支付依赖同一笔入账"},
            {"id": "INT-0029", "severity": "warning", "title": "SR2026 address exception", "title_zh": "SR2026 地址异常", "owner": "Standards", "due": "19:05", "reason": "Creditor town name is missing", "reason_zh": "收款人城镇名称缺失"},
        ],
        "events": [
            {"id": "EV-81", "time": "07:29:54", "system": "CIPS RTGS", "type": "settlement", "state": "SETTLED", "text": "Priority payment released after incoming liquidity", "text_zh": "优先支付在入账流动性到位后释放"},
            {"id": "EV-80", "time": "07:29:41", "system": "Policy", "type": "decision", "state": "DENY", "text": "GB corridor held for purpose review", "text_zh": "英国通道因用途复核被暂停"},
            {"id": "EV-79", "time": "07:29:17", "system": "PvP", "type": "lock", "state": "LOCKED", "text": "CNY debit leg reserved", "text_zh": "人民币借方腿已预留"},
            {"id": "EV-78", "time": "07:28:58", "system": "Standards", "type": "validation", "state": "WARNING", "text": "Hybrid address accepted with remediation", "text_zh": "混合地址已接受并附修复建议"},
        ],
        "liquidity": [
            {"participant": "CIPS-CN-A", "opening": 2_400_000_000, "balance": 1_920_000_000, "reserved": 460_000_000, "queued": 510_000_000, "expected_incoming": 720_000_000, "currency": "CNY"},
            {"participant": "CIPS-HK-B", "opening": 1_680_000_000, "balance": 1_020_000_000, "reserved": 310_000_000, "queued": 640_000_000, "expected_incoming": 190_000_000, "currency": "CNY"},
            {"participant": "CIPS-TH-C", "opening": 980_000_000, "balance": 760_000_000, "reserved": 210_000_000, "queued": 180_000_000, "expected_incoming": 340_000_000, "currency": "CNY"},
            {"participant": "CIPS-AE-D", "opening": 740_000_000, "balance": 510_000_000, "reserved": 120_000_000, "queued": 230_000_000, "expected_incoming": 95_000_000, "currency": "CNY"},
        ],
        "dns": {"participants": ["CN-A", "HK-B", "TH-C", "AE-D"], "obligations": [[0, 420, 180, 90], [260, 0, 120, 70], [80, 160, 0, 140], [110, 90, 130, 0]], "net_positions": [-250, 240, 30, -20], "gross_required": 1_850_000_000, "net_required": 510_000_000, "savings_ratio": 72.43, "blocked_participant": "HK-B", "state": "LIQUIDITY_CHECK"},
        "lifecycle": [
            {"code": "INITIATED", "label": "Initiated", "label_zh": "已发起", "system": "Origin Bank", "time": "07:24:02", "status": "completed", "reason": "UETR allocated", "reason_zh": "已分配 UETR"},
            {"code": "VALIDATED", "label": "Validated", "label_zh": "已校验", "system": "Standards", "time": "07:24:04", "status": "completed", "reason": "CBPR+ SR2026 valid", "reason_zh": "CBPR+ SR2026 有效"},
            {"code": "ROUTED", "label": "Routed", "label_zh": "已路由", "system": "CIPS", "time": "07:24:07", "status": "completed", "reason": "Direct participant selected", "reason_zh": "已选择直接参与者"},
            {"code": "RESERVED", "label": "Liquidity reserved", "label_zh": "流动性预留", "system": "RTGS", "time": "07:24:11", "status": "active", "reason": "Awaiting counter-leg lock", "reason_zh": "等待对手腿锁定"},
            {"code": "COMMITTED", "label": "Atomic commit", "label_zh": "原子提交", "system": "PvP", "time": "—", "status": "pending", "reason": "Both legs required", "reason_zh": "需要两腿同时满足"},
            {"code": "CONFIRMED", "label": "Universal confirmation", "label_zh": "通用确认", "system": "Tracker", "time": "—", "status": "pending", "reason": "Final confirmation pending", "reason_zh": "等待最终确认"},
        ],
        "pvp": [
            {"code": "QUOTE", "label": "Quote validated", "label_zh": "报价校验", "state": "complete"},
            {"code": "POLICY", "label": "Policy authorized", "label_zh": "策略授权", "state": "complete"},
            {"code": "LEG_A", "label": "CNY leg reserved", "label_zh": "人民币腿预留", "state": "active"},
            {"code": "LEG_B", "label": "HKD leg reserved", "label_zh": "港币腿预留", "state": "waiting"},
            {"code": "LOCK", "label": "Both legs locked", "label_zh": "双腿锁定", "state": "waiting"},
            {"code": "COMMIT", "label": "Atomic commit", "label_zh": "原子提交", "state": "waiting"},
            {"code": "CONFIRM", "label": "Confirmation", "label_zh": "结算确认", "state": "waiting"},
        ],
        "policy_matrix": [
            {"source": "CN", "destination": "HK", "status": "allow", "ceiling": 50_000_000, "purposes": ["trade", "services", "retail"], "residency": "CN/HK split", "reason": "Approved bilateral profile", "reason_zh": "已批准双边配置"},
            {"source": "CN", "destination": "TH", "status": "limited", "ceiling": 20_000_000, "purposes": ["trade", "services"], "residency": "local copy required", "reason": "Retail P2P excluded", "reason_zh": "不包含零售个人转账"},
            {"source": "CN", "destination": "AE", "status": "allow", "ceiling": 35_000_000, "purposes": ["trade", "treasury"], "residency": "federated digest", "reason": "Multi-CBDC predicates satisfied", "reason_zh": "多 CBDC 策略条件满足"},
            {"source": "HK", "destination": "GB", "status": "deny", "ceiling": 0, "purposes": [], "residency": "review required", "reason": "Purpose and participant role not permitted", "reason_zh": "用途与参与者角色不被允许"},
            {"source": "TH", "destination": "CN", "status": "limited", "ceiling": 15_000_000, "purposes": ["trade"], "residency": "TH source record", "reason": "Enhanced due diligence above threshold", "reason_zh": "超过阈值需增强尽调"},
        ],
        "iso_tree": [
            {"path": "AppHdr", "label": "Business Application Header", "value": "head.001.001.03", "required": True, "children": [
                {"path": "AppHdr/Fr/FIId/FinInstnId/BICFI", "label": "From BIC", "value": "AAAACNBJXXX", "required": True},
                {"path": "AppHdr/To/FIId/FinInstnId/BICFI", "label": "To BIC", "value": "BBBBHKHHXXX", "required": True},
                {"path": "AppHdr/BizMsgIdr", "label": "Business message ID", "value": "BIZ-20260722-0081", "required": True},
            ]},
            {"path": "Document/FIToFICstmrCdtTrf/GrpHdr", "label": "Group Header", "value": "pacs.008.001.13", "required": True, "children": [
                {"path": "Document/.../GrpHdr/MsgId", "label": "Message ID", "value": "MSG-20260722-0081", "required": True},
                {"path": "Document/.../GrpHdr/SttlmInf/SttlmMtd", "label": "Settlement method", "value": "CLRG", "required": True},
            ]},
            {"path": "Document/.../CdtTrfTxInf/Dbtr", "label": "Debtor", "value": "Beihang Research Settlement Lab", "required": True},
            {"path": "Document/.../CdtTrfTxInf/Cdtr/PstlAdr/TwnNm", "label": "Creditor town name", "value": "", "required": True, "severity": "warning", "rule": "SR2026-HYBRID-TOWN"},
            {"path": "Document/.../CdtTrfTxInf/RmtInf/Ustrd", "label": "Remittance information", "value": "Research infrastructure service", "required": False},
        ],
        "message_diff": [
            {"path": "AppHdr/BizMsgIdr", "kind": "unchanged", "before": "BIZ-20260722-0081", "after": "BIZ-20260722-0081", "source_party": "Origin Bank", "reason": "Identifier retained", "payload_hash": "2b278...8c1", "previous_hash": None},
            {"path": "Document/.../Cdtr/PstlAdr/TwnNm", "kind": "added", "before": None, "after": "Hong Kong", "source_party": "Intermediary Bank", "reason": "SR2026 remediation", "payload_hash": "a4f11...3d9", "previous_hash": "2b278...8c1"},
            {"path": "Document/.../IntrBkSttlmAmt", "kind": "modified", "before": "1000000.00", "after": "999850.00", "source_party": "Settlement Adapter", "reason": "Fee settlement copy", "payload_hash": "47e6d...118", "previous_hash": "a4f11...3d9"},
            {"path": "Document/.../RmtInf/Ustrd", "kind": "removed", "before": "Internal project code P-71", "after": None, "source_party": "Privacy Gateway", "reason": "Data minimisation policy", "payload_hash": "e80b1...12c", "previous_hash": "47e6d...118"},
        ],
        "scenarios": scenarios,
    }


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
            "active_payments": sum(item.status not in {"SETTLED", "REJECTED", "CANCELLED"} for item in lifecycles),
            "queued_value": sum(item.amount for item in settlements if item.status == "QUEUED"),
            "open_cases": len(cases),
            "available_liquidity": sum(max(item.balance - item.reserved, 0) for item in accounts),
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
                "queued": sum(item.amount for item in settlements if item.debtor_participant == account.participant_id and item.status == "QUEUED"),
                "expected_incoming": sum(item.amount for item in settlements if item.creditor_participant == account.participant_id and item.status == "QUEUED"),
                "currency": account.currency,
            }
            for account in accounts
        ]
    events = db.query(PaymentLensEvent).order_by(PaymentLensEvent.id.desc()).limit(8).all()
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
    decision = _evaluate(db, subject=subject, role=role, action="view", resource="workspace.command")
    if decision["result"] != "allow":
        db.rollback()
        raise HTTPException(403, detail=decision)
    payload = _representative_payload()
    _overlay_database(payload, db)
    payload["authorization"] = decision
    db.commit()
    return payload
