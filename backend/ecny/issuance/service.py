"""Central-bank issuance, redemption, and operator-wallet exchange."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import EcnyAccount
from ecny.ledger import LedgerError, burn, mint, transfer
from ecny.wallet import (
    WalletError,
    check_limits,
    get_wallet,
    ledger_account_id_for,
    wallet_balance,
)

ISSUANCE_CAP_FEN = 100_000_000_000


class IssuanceError(Exception):
    """Issuance operation is invalid."""


def _net_issuance(db: Session) -> int:
    """Outstanding CNY across operators and wallets (mint - burn - FX exit)."""
    value = (
        db.query(func.coalesce(func.sum(EcnyAccount.balance), 0))
        .filter(
            EcnyAccount.currency == "CNY",
            EcnyAccount.owner_type != "central_bank",
        )
        .scalar()
    )
    return int(value or 0)


def issue_to_operator(
    db: Session,
    operator_account_id: str,
    amount: int,
    memo: dict[str, Any] | None = None,
) -> str:
    if amount <= 0:
        raise IssuanceError("amount must be positive")
    if _net_issuance(db) + amount > ISSUANCE_CAP_FEN:
        raise IssuanceError("issuance cap exceeded")
    try:
        return mint(db, operator_account_id, amount, memo or {"action": "issuance"}).tx_id
    except LedgerError as exc:
        raise IssuanceError(str(exc)) from exc


def redeem_from_operator(
    db: Session,
    operator_account_id: str,
    amount: int,
    memo: dict[str, Any] | None = None,
) -> str:
    if amount <= 0:
        raise IssuanceError("amount must be positive")
    try:
        return burn(db, operator_account_id, amount, memo or {"action": "redemption"}).tx_id
    except LedgerError as exc:
        raise IssuanceError(str(exc)) from exc


def exchange_to_wallet(
    db: Session,
    operator_account_id: str,
    wallet_id: str,
    amount: int,
    memo: dict[str, Any] | None = None,
) -> str:
    wallet = get_wallet(db, wallet_id)
    if not wallet:
        raise IssuanceError(f"wallet not found: {wallet_id}")
    try:
        check_limits(db, wallet, amount, incoming=True)
        tx = transfer(
            db,
            operator_account_id,
            ledger_account_id_for(db, wallet_id),
            amount,
            memo or {"action": "exchange_to_wallet", "wallet": wallet_id},
        )
        return tx.tx_id
    except (WalletError, LedgerError) as exc:
        raise IssuanceError(str(exc)) from exc


def redeem_from_wallet(
    db: Session,
    wallet_id: str,
    operator_account_id: str,
    amount: int,
    memo: dict[str, Any] | None = None,
) -> str:
    wallet = get_wallet(db, wallet_id)
    if not wallet:
        raise IssuanceError(f"wallet not found: {wallet_id}")
    if amount <= 0 or wallet_balance(db, wallet) < amount:
        raise IssuanceError("insufficient wallet balance")
    try:
        check_limits(db, wallet, amount)
        tx = transfer(
            db,
            ledger_account_id_for(db, wallet_id),
            operator_account_id,
            amount,
            memo or {"action": "redeem_from_wallet", "wallet": wallet_id},
        )
        return tx.tx_id
    except (WalletError, LedgerError) as exc:
        raise IssuanceError(str(exc)) from exc


def net_issuance(db: Session) -> int:
    return _net_issuance(db)
