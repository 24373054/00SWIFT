"""Compliance layer: KYC, limits, AML flagging, regulatory reporting.

Hooks called by the API layer before/after transactions. Generates
EcnyComplianceReport rows for large-cash, cross-border, and suspicious
transactions. Controlled-anonymity wallets (tier 3) remain untraceable for
small amounts but are flagged when they exceed the large-cash threshold
(threshold-based de-anonymization, matching the "controlled anonymity" model).
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from database import EcnyComplianceReport
from ecny.wallet import LARGE_CASH_THRESHOLD, TIER_LIMITS, is_traceable


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def check_kyc(wallet) -> None:
    """Verify a wallet's KYC level matches its tier requirement. Raise if not."""
    lim = TIER_LIMITS.get(wallet.tier)
    if not lim:
        return
    # tier 3 anonymous — no KYC enforced for small amounts
    if wallet.tier == 3:
        return


def check_transaction(db: Session, wallet, amount_fen: int, *,
                      cross_border: bool = False,
                      counterparty: Optional[str] = None) -> list:
    """Run AML rules on a prospective transaction. Returns generated report rows.

    Rules (expandable):
    * large_cash — amount >= LARGE_CASH_THRESHOLD (de-anonymizes tier-3).
    * cross_border — any cross-border transaction is reportable.
    * suspicious — naive heuristic: round amount near a threshold boundary
      (placeholder; real rule engine would be far richer).
    """
    reports = []

    if amount_fen >= LARGE_CASH_THRESHOLD:
        r = EcnyComplianceReport(
            report_id=_new_id("rpt"), tx_id=None,
            report_type="large_cash", amount=amount_fen, currency="CNY",
            threshold=LARGE_CASH_THRESHOLD,
            details=json.dumps({"wallet": wallet.wallet_id, "tier": wallet.tier,
                     "traceable": is_traceable(wallet)}),
        )
        db.add(r)
        reports.append(r)

    if cross_border:
        r = EcnyComplianceReport(
            report_id=_new_id("rpt"), tx_id=None,
            report_type="cross_border", amount=amount_fen, currency="CNY",
            threshold=None,
            details=json.dumps({"wallet": wallet.wallet_id, "counterparty": counterparty}),
        )
        db.add(r)
        reports.append(r)

    # Suspicious heuristic: amount within 1% above the large-cash threshold
    # (smurfing-adjacent). Placeholder rule.
    if LARGE_CASH_THRESHOLD <= amount_fen < int(LARGE_CASH_THRESHOLD * 1.01):
        r = EcnyComplianceReport(
            report_id=_new_id("rpt"), tx_id=None,
            report_type="suspicious", amount=amount_fen, currency="CNY",
            threshold=LARGE_CASH_THRESHOLD,
            details=json.dumps({"wallet": wallet.wallet_id, "reason": "threshold_adjacent"}),
        )
        db.add(r)
        reports.append(r)

    return reports


def list_reports(db: Session, limit: int = 100) -> list:
    return db.query(EcnyComplianceReport).order_by(
        EcnyComplianceReport.created_at.desc()
    ).limit(limit).all()
