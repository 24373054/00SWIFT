"""Central bank issuance & redemption, plus operator <-> wallet exchange.

issue_to_operator   — PBOC mints e-CNY to an operator account (ledger.mint).
redeem_from_operator — operator burns e-CNY back to PBOC (ledger.burn).
exchange_to_wallet   — operator debits its account, credits a wallet (transfer).
redeem_from_wallet   — wallet debits, operator credits (transfer).

Total issuance is capped by config (issuance_cap_fen) to model central bank
quota control. The cap tracks cumulative net issuance (mint - burn).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from ecny.ledger import LedgerError, burn, get_or_create_account, mint, transfer
from ecny.wallet import get_wallet, ledger_account_id_for

# Sandbox issuance cap: 1 billion CNY = 100,000,000,000 fen.
ISSUANCE_CAP_FEN = 100_000_000_000


class IssuanceError(Exception):
    pass


def _net_issuance(db: Session) -> int:
    """Cumulative mint minus burn across all operator accounts."""
    from database import EcnyAccount
    total = 0
    for acct in db.query(EcnyAccount).filter(EcnyAccount.owner_type == "operator").all():
        total += acct.balance
    return total


def issue_to_operator(db: Session, operator_account_id: str, amount: int,
                      memo: Optional[Dict[str, Any]] = None) -> str:
    """PBOC issues e-CNY to an operator. Returns tx_id."""
    if amount <= 0:
        raise IssuanceError("amount must be positive")
    if _net_issuance(db) + amount > ISSUANCE_CAP_FEN:
        raise IssuanceError("issuance cap exceeded")
    try:
        tx = mint(db, operator_account_id, amount, memo or {"action": "issuance"})
    except LedgerError as e:
        raise IssuanceError(str(e))
    return tx.tx_id


def redeem_from_operator(db: Session, operator_account_id: str, amount: int,
                         memo: Optional[Dict[str, Any]] = None) -> str:
    """Operator redeems e-CNY back to PBOC. Returns tx_id."""
    if amount <= 0:
        raise IssuanceError("amount must be positive")
    try:
        tx = burn(db, operator_account_id, amount, memo or {"action": "redemption"})
    except LedgerError as e:
        raise IssuanceError(str(e))
    return tx.tx_id


def exchange_to_wallet(db: Session, operator_account_id: str,
                       wallet_id: str, amount: int,
                       memo: Optional[Dict[str, Any]] = None) -> str:
    """Operator exchanges e-CNY into a wallet (operator -> wallet)."""
    wallet = get_wallet(db, wallet_id)
    if not wallet:
        raise IssuanceError(f"wallet not found: {wallet_id}")
    from ecny.wallet import check_limits, WalletError
    try:
        check_limits(db, wallet, amount)
    except WalletError as e:
        raise IssuanceError(str(e))
    wallet_acct = ledger_account_id_for(db, wallet_id)
    try:
        tx = transfer(db, operator_account_id, wallet_acct, amount,
                      memo or {"action": "exchange_to_wallet", "wallet": wallet_id})
    except LedgerError as e:
        raise IssuanceError(str(e))
    # reflect ledger balance onto the wallet row for fast reads
    wallet.balance = (wallet.balance or 0) + amount
    return tx.tx_id


def redeem_from_wallet(db: Session, wallet_id: str,
                       operator_account_id: str, amount: int,
                       memo: Optional[Dict[str, Any]] = None) -> str:
    """Wallet redeems e-CNY back to operator (wallet -> operator)."""
    wallet = get_wallet(db, wallet_id)
    if not wallet:
        raise IssuanceError(f"wallet not found: {wallet_id}")
    if amount <= 0 or (wallet.balance or 0) < amount:
        raise IssuanceError("insufficient wallet balance")
    wallet_acct = ledger_account_id_for(db, wallet_id)
    try:
        tx = transfer(db, wallet_acct, operator_account_id, amount,
                      memo or {"action": "redeem_from_wallet", "wallet": wallet_id})
    except LedgerError as e:
        raise IssuanceError(str(e))
    wallet.balance = (wallet.balance or 0) - amount
    return tx.tx_id


def net_issuance(db: Session) -> int:
    """Public accessor for cumulative net issuance (mint - burn)."""
    return _net_issuance(db)
