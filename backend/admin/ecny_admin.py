"""Admin-only e-CNY provisioning and observability endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth.dependencies import require_admin_token
from config import get_settings
from database import (
    EcnyAccount,
    EcnyBridgeChannel,
    EcnyComplianceReport,
    EcnyTransaction,
    EcnyWallet,
    get_db,
)
from ecny.issuance import net_issuance
from ecny.ledger import get_or_create_account
from ecny.wallet import wallet_balance

router = APIRouter(
    prefix="/api/ecny",
    tags=["e-CNY admin"],
    dependencies=[Depends(require_admin_token)],
)


@router.post("/provision-operator")
def provision_operator(
    account_id: str,
    owner_ref: str,
    currency: str = "CNY",
    db: Session = Depends(get_db),
):
    currency = currency.upper()
    if len(currency) != 3 or not currency.isalpha():
        raise HTTPException(400, "currency must be a 3-letter code")
    account = get_or_create_account(db, account_id, "operator", owner_ref, currency)
    db.commit()
    return {
        "account_id": account.account_id,
        "owner_type": account.owner_type,
        "owner_ref": account.owner_ref,
        "currency": account.currency,
        "balance": account.balance,
    }


@router.post("/seed-foreign-account")
def seed_foreign_account(
    account_id: str,
    owner_ref: str,
    currency: str,
    balance_fen: int = Query(..., ge=0),
    db: Session = Depends(get_db),
):
    if not get_settings().is_sandbox:
        raise HTTPException(403, "fixture seeding is sandbox-only")
    currency = currency.upper()
    if currency == "CNY":
        raise HTTPException(400, "CNY must be issued through the issuance API")
    account = db.query(EcnyAccount).filter(EcnyAccount.account_id == account_id).first()
    if not account:
        account = EcnyAccount(
            account_id=account_id,
            owner_type="operator",
            owner_ref=owner_ref,
            currency=currency,
            balance=0,
        )
        db.add(account)
    elif account.currency != currency:
        raise HTTPException(409, "account already exists with another currency")
    account.balance = balance_fen
    db.commit()
    return {
        "account_id": account.account_id,
        "currency": account.currency,
        "balance": account.balance,
    }


@router.get("/stats")
def e_cny_stats(db: Session = Depends(get_db)):
    return {
        "net_issuance_fen": net_issuance(db),
        "wallets_total": db.query(EcnyWallet).count(),
        "ledger_transactions": db.query(EcnyTransaction).count(),
        "bridge_channels": db.query(EcnyBridgeChannel).count(),
        "compliance_reports": db.query(EcnyComplianceReport).count(),
    }


@router.get("/ledger-accounts")
def list_ledger_accounts(db: Session = Depends(get_db)):
    rows = db.query(EcnyAccount).order_by(EcnyAccount.account_id).all()
    return [
        {
            "account_id": row.account_id,
            "owner_type": row.owner_type,
            "owner_ref": row.owner_ref,
            "currency": row.currency,
            "balance": row.balance,
        }
        for row in rows
    ]


@router.get("/wallets")
def list_e_cny_wallets(db: Session = Depends(get_db)):
    rows = db.query(EcnyWallet).order_by(EcnyWallet.created_at.desc()).all()
    return [
        {
            "wallet_id": row.wallet_id,
            "tier": row.tier,
            "balance": wallet_balance(db, row),
            "status": row.status,
            "operator_id": row.operator_id,
        }
        for row in rows
    ]
