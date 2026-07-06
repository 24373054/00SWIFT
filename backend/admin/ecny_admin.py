"""Admin endpoints for e-CNY provisioning and management.

Exposed under /api/ecny/* with X-Admin-Token (reuse existing require_admin_token
dependency). This allows operators and admin staff to create test wallets,
provide seeding data, and view dashboard statistics.
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from auth.dependencies import require_admin_token
from ecny.issuance import net_issuance

router = APIRouter(prefix="/api/ecny", tags=["e-CNY admin"])


@router.post("/provision-operator")
def provision_operator(account_id: str, owner_ref: str,
                       currency: str = "CNY",
                       _: None = Depends(require_admin_token)):
    """Create (idempotent) an operator ledger account for testing."""
    from database import EcnyAccount
    from ecny.ledger import get_or_create_account
    db = SessionLocal()
    try:
        acct = get_or_create_account(db, account_id, "operator", owner_ref, currency)
        db.commit()
        return {"account_id": acct.account_id, "owner_type": acct.owner_type,
                "owner_ref": acct.owner_ref, "currency": acct.currency,
                "balance": acct.balance}
    finally:
        db.close()


@router.post("/seed-foreign-account")
def seed_foreign_account(account_id: str, owner_ref: str, currency: str,
                         balance_fen: int,
                         _: None = Depends(require_admin_token)):
    """Create a foreign-currency account with a seed balance (for mBridge tests)."""
    from database import EcnyAccount
    db = SessionLocal()
    try:
        acct = db.query(EcnyAccount).filter(EcnyAccount.account_id == account_id).first()
        if not acct:
            acct = EcnyAccount(account_id=account_id, owner_type="operator",
                               owner_ref=owner_ref, currency=currency, balance=0)
            db.add(acct)
        acct.balance = balance_fen
        db.commit()
        return {"account_id": acct.account_id, "currency": acct.currency,
                "balance": acct.balance}
    finally:
        db.close()


@router.get("/stats")
def e_cny_stats(_: None = Depends(require_admin_token)):
    """Dashboard stats for e-CNY subsystem."""
    db = SessionLocal()
    try:
        from database import EcnyAccount, EcnyBridgeChannel, EcnyWallet, EcnyTransaction, EcnyComplianceReport
        net_issue = net_issuance(db)
        wallets = db.query(EcnyWallet).count()
        txs = db.query(EcnyTransaction).count()
        bridge_txs = db.query(EcnyBridgeChannel).count()
        reports = db.query(EcnyComplianceReport).count()
        return {
            "net_issuance_cny": net_issue / 100,  # fen -> CNY
            "wallets_total": wallets,
            "ledger_transactions": txs,
            "bridge_channels": bridge_txs,
            "compliance_reports": reports,
        }
    finally:
        db.close()


@router.get("/ledger-accounts")
def list_ledger_accounts(_: None = Depends(require_admin_token)):
    """List all e-CNY ledger accounts."""
    from database import EcnyAccount
    db = SessionLocal()
    try:
        rows = db.query(EcnyAccount).all()
        return [{"account_id": r.account_id, "owner_type": r.owner_type,
                 "owner_ref": r.owner_ref, "currency": r.currency,
                 "balance": r.balance} for r in rows]
    finally:
        db.close()


@router.get("/wallets")
def list_e_cny_wallets(_: None = Depends(require_admin_token)):
    """List all e-CNY wallets."""
    from database import EcnyWallet
    db = SessionLocal()
    try:
        rows = db.query(EcnyWallet).all()
        return [{"wallet_id": r.wallet_id, "tier": r.tier, "balance": r.balance,
                 "status": r.status, "operator_id": r.operator_id} for r in rows]
    finally:
        db.close()
