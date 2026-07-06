"""e-CNY business API router — mounted at /ecny/v1.

All write endpoints require OAuth2 Bearer with ecny.* scope (reuse the
existing get_cred / require_scopes machinery). Read endpoints (ledger
browser, bridge status) require ecny.ledger / ecny.bridge scopes.

This router exposes the e-CNY capabilities built in ecny/ (ledger, wallet,
issuance, bridge, compliance) as a clean REST surface.
"""
from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.dependencies import get_cred, require_scopes
from ecny.auth_dep import require_ecny_cred
from database import get_db
from api.ecny.schemas import (
    BridgeTxResponse, ComplianceReportResponse, CrossBorderRequest,
    IssuanceRequest, LedgerTransactionResponse, TransferRequest,
    WalletOpenRequest, WalletResponse,
)
from ecny.wallet import WalletError, check_limits, get_wallet, ledger_account_id_for, open_wallet
from ecny.issuance import IssuanceError, exchange_to_wallet, issue_to_operator, net_issuance, redeem_from_operator, redeem_from_wallet
from ecny.ledger import LedgerError, balance as ledger_balance, get_or_create_account, transfer
from ecny.bridge import BridgeError, get_bridge_tx, route_cross_border, settle_pvp, settle_via_cips
from ecny.compliance import check_transaction, list_reports
from database import EcnyAccount, EcnyTransaction


router = APIRouter(
    prefix="/ecny/v1",
    tags=["e-CNY"],
    dependencies=[Depends(require_ecny_cred)],
)


def _wallet_response(db, w) -> WalletResponse:
    return WalletResponse(
        wallet_id=w.wallet_id, tier=w.tier, balance=w.balance or 0,
        status=w.status, holder_id=w.holder_id, operator_id=w.operator_id,
        ledger_account_id=ledger_account_id_for(db, w.wallet_id),
    )


@router.post("/wallets", response_model=WalletResponse)
def open_wallet_endpoint(body: WalletOpenRequest, db: Session = Depends(get_db)):
    try:
        holder = None
        if body.holder_name or body.holder_id_hash:
            holder = {
                "real_name": body.holder_name,
                "id_type": body.holder_id_type,
                "id_hash": body.holder_id_hash,
                "country_code": body.holder_country,
            }
        w = open_wallet(db, operator_id=0, tier=body.tier, holder=holder,
                        operator_account_id=body.operator_account_id)
        db.commit()
        return _wallet_response(db, w)
    except WalletError as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.get("/wallets/{wallet_id}", response_model=WalletResponse)
def get_wallet_endpoint(wallet_id: str, db: Session = Depends(get_db)):
    w = get_wallet(db, wallet_id)
    if not w:
        raise HTTPException(404, "wallet not found")
    return _wallet_response(db, w)


@router.post("/transfers", response_model=LedgerTransactionResponse)
def transfer_endpoint(body: TransferRequest, db: Session = Depends(get_db)):
    """Wallet-to-wallet transfer. Enforces tier limits + compliance checks."""
    src = get_wallet(db, body.from_wallet_id)
    dst = get_wallet(db, body.to_wallet_id)
    if not src or not dst:
        raise HTTPException(404, "wallet not found")
    try:
        check_limits(db, src, body.amount_fen)
    except WalletError as e:
        raise HTTPException(400, str(e))
    # compliance pre-check (generates reports for large/suspicious)
    check_transaction(db, src, body.amount_fen, cross_border=False)
    try:
        src_acct = ledger_account_id_for(db, body.from_wallet_id)
        dst_acct = ledger_account_id_for(db, body.to_wallet_id)
        tx = transfer(db, src_acct, dst_acct, body.amount_fen,
                      memo=body.memo or {"action": "p2p"})
        src.balance = (src.balance or 0) - body.amount_fen
        dst.balance = (dst.balance or 0) + body.amount_fen
        db.commit()
        return _tx_response(tx)
    except LedgerError as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.post("/issuance", response_model=LedgerTransactionResponse)
def issuance_endpoint(body: IssuanceRequest, db: Session = Depends(get_db)):
    """Central bank issuance / redemption + operator<->wallet exchange.

    Actions: mint (PBOC->operator), burn (operator->PBOC),
    issue_to_wallet (operator->wallet), redeem_from_wallet (wallet->operator).
    """
    try:
        if body.action == "mint":
            tx_id = issue_to_operator(db, body.operator_account_id, body.amount_fen)
        elif body.action == "burn":
            tx_id = redeem_from_operator(db, body.operator_account_id, body.amount_fen)
        elif body.action == "issue_to_wallet":
            if not body.wallet_id:
                raise HTTPException(400, "wallet_id required for issue_to_wallet")
            tx_id = exchange_to_wallet(db, body.operator_account_id, body.wallet_id, body.amount_fen)
        elif body.action == "redeem_from_wallet":
            if not body.wallet_id:
                raise HTTPException(400, "wallet_id required for redeem_from_wallet")
            tx_id = redeem_from_wallet(db, body.wallet_id, body.operator_account_id, body.amount_fen)
        else:
            raise HTTPException(400, f"unknown action: {body.action}")
        db.commit()
        tx = db.query(EcnyTransaction).filter(EcnyTransaction.tx_id == tx_id).first()
        return _tx_response(tx)
    except IssuanceError as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.post("/cross-border", response_model=BridgeTxResponse)
def cross_border_endpoint(body: CrossBorderRequest, db: Session = Depends(get_db)):
    """Initiate a cross-border payment via mBridge or CIPS."""
    src = get_wallet(db, body.from_wallet_id)
    if not src:
        raise HTTPException(404, "source wallet not found")
    try:
        check_limits(db, src, body.amount_fen)
    except WalletError as e:
        raise HTTPException(400, str(e))
    channel = body.channel or route_cross_border(body.target_currency)
    check_transaction(db, src, body.amount_fen, cross_border=True,
                      counterparty=body.counterparty)
    try:
        src_acct = ledger_account_id_for(db, body.from_wallet_id)
        if channel == "mbridge":
            btx = settle_pvp(db, src_acct, body.to_account_id, body.amount_fen,
                             "CNY", body.target_currency, body.counterparty)
        else:
            btx = settle_via_cips(db, src_acct, body.to_account_id,
                                  body.amount_fen, body.counterparty)
        src.balance = (src.balance or 0) - body.amount_fen
        db.commit()
        return BridgeTxResponse(
            uetr=btx.uetr, channel_id=btx.channel_id,
            from_currency=btx.from_currency, from_amount=btx.from_amount,
            to_currency=btx.to_currency, to_amount=btx.to_amount,
            fx_rate=btx.fx_rate, status=btx.status,
            counterparty_ref=btx.counterparty_ref,
        )
    except (BridgeError, LedgerError) as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.get("/cross-border/{uetr}", response_model=BridgeTxResponse)
def track_cross_border(uetr: str, db: Session = Depends(get_db)):
    btx = get_bridge_tx(db, uetr)
    if not btx:
        raise HTTPException(404, "cross-border transaction not found")
    return BridgeTxResponse(
        uetr=btx.uetr, channel_id=btx.channel_id,
        from_currency=btx.from_currency, from_amount=btx.from_amount,
        to_currency=btx.to_currency, to_amount=btx.to_amount,
        fx_rate=btx.fx_rate, status=btx.status,
        counterparty_ref=btx.counterparty_ref,
    )


@router.get("/ledger/transactions", response_model=List[LedgerTransactionResponse])
def list_transactions(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.query(EcnyTransaction).order_by(
        EcnyTransaction.created_at.desc()
    ).limit(limit).all()
    return [_tx_response(t) for t in rows]


@router.get("/ledger/balance/{account_id}")
def get_balance(account_id: str, db: Session = Depends(get_db)):
    try:
        return {"account_id": account_id, "balance": ledger_balance(db, account_id)}
    except LedgerError as e:
        raise HTTPException(404, str(e))


@router.get("/bridge/channels")
def list_bridge_channels(db: Session = Depends(get_db)):
    from database import EcnyBridgeChannel
    rows = db.query(EcnyBridgeChannel).all()
    return {"channels": [
        {"channel_id": c.channel_id, "channel_type": c.channel_type,
         "counterparty": c.counterparty, "currency_pair": c.currency_pair,
         "status": c.status, "fx_rate": json.loads(c.fx_rate or "{}")}
        for c in rows
    ]}


@router.get("/compliance/reports", response_model=List[ComplianceReportResponse])
def list_compliance_reports(limit: int = 100, db: Session = Depends(get_db)):
    rows = list_reports(db, limit)
    return [ComplianceReportResponse(
        report_id=r.report_id, tx_id=r.tx_id, report_type=r.report_type,
        amount=r.amount, currency=r.currency, threshold=r.threshold,
        details=json.loads(r.details or "{}"),
        created_at=r.created_at.isoformat() if r.created_at else "",
    ) for r in rows]


def _tx_response(t: EcnyTransaction) -> LedgerTransactionResponse:
    return LedgerTransactionResponse(
        tx_id=t.tx_id, tx_type=t.tx_type, status=t.status,
        amount=t.amount, currency=t.currency,
        from_account=t.from_account, to_account=t.to_account,
        uetr=t.uetr, memo=json.loads(t.memo or "{}"),
        created_at=t.created_at.isoformat() if t.created_at else "",
        settled_at=t.settled_at.isoformat() if t.settled_at else None,
    )
