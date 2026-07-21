"""e-CNY centralized ledger engine.

Pure-Python double-entry ledger. No FastAPI dependency — takes a SQLAlchemy
Session so it is unit-testable. All amounts are integers in fen (分) to avoid
floating-point error.

Invariants enforced:
* Balance never negative (overdraft rejected).
* Every settled transaction has equal debit + credit (double-entry balance).
* Settled transactions are immutable (status terminal).

Account model (not UTXO): one balance per account, atomic debit/credit.
UTXO is better for DLT privacy; account model is simpler, faster, and
audit-friendly for a centralized ledger. DLT is a future pluggable swap.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from core.time import now_utc
from database import EcnyAccount, EcnyEntry, EcnyTransaction


class LedgerError(Exception):
    """Ledger invariant violation."""


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def get_or_create_account(
    db: Session, account_id: str, owner_type: str, owner_ref: str, currency: str = "CNY"
) -> EcnyAccount:
    acct = db.query(EcnyAccount).filter(EcnyAccount.account_id == account_id).first()
    if acct:
        return acct
    acct = EcnyAccount(
        account_id=account_id,
        owner_type=owner_type,
        owner_ref=owner_ref,
        currency=currency,
        balance=0,
    )
    db.add(acct)
    db.flush()
    return acct


def balance(db: Session, account_id: str) -> int:
    acct = db.query(EcnyAccount).filter(EcnyAccount.account_id == account_id).first()
    if not acct:
        raise LedgerError(f"account not found: {account_id}")
    return acct.balance


def _apply_transfer(
    db: Session, tx: EcnyTransaction, from_acct: EcnyAccount, to_acct: EcnyAccount, amount: int
) -> None:
    """Atomic debit/credit + double-entry legs. Raises if insufficient balance."""
    if amount <= 0:
        raise LedgerError("amount must be positive")
    if from_acct.account_id == to_acct.account_id:
        raise LedgerError("from and to must differ")
    if from_acct.currency != to_acct.currency:
        raise LedgerError("currency mismatch in plain transfer")
    if from_acct.balance < amount:
        raise LedgerError(f"insufficient balance: have {from_acct.balance}, need {amount}")
    from_acct.balance -= amount
    to_acct.balance += amount
    db.add(
        EcnyEntry(
            entry_id=_new_id("ent"),
            tx_id=tx.tx_id,
            account_id=from_acct.account_id,
            direction="debit",
            amount=amount,
            currency=from_acct.currency,
        )
    )
    db.add(
        EcnyEntry(
            entry_id=_new_id("ent"),
            tx_id=tx.tx_id,
            account_id=to_acct.account_id,
            direction="credit",
            amount=amount,
            currency=to_acct.currency,
        )
    )
    db.flush()


def _settle(db: Session, tx: EcnyTransaction) -> EcnyTransaction:
    tx.status = "settled"
    tx.settled_at = now_utc()
    return tx


def mint(
    db: Session, to_account_id: str, amount: int, memo: dict[str, Any] | None = None
) -> EcnyTransaction:
    """Central bank issuance: credit an operator account out of thin air.

    In a real CBDC system the central bank account is the liability side; here
    we model issuance as a one-sided credit (the CB account balance is not
    decremented — it represents the issuance wellspring). A paired burn removes.
    """
    if amount <= 0:
        raise LedgerError("mint amount must be positive")
    to_acct = db.query(EcnyAccount).filter(EcnyAccount.account_id == to_account_id).first()
    if not to_acct:
        raise LedgerError(f"account not found: {to_account_id}")
    if to_acct.owner_type != "operator":
        raise LedgerError("mint target must be an operator account")
    tx = EcnyTransaction(
        tx_id=_new_id("tx"),
        tx_type="mint",
        status="pending",
        amount=amount,
        currency=to_acct.currency,
        to_account=to_account_id,
        memo=json.dumps(memo or {}),
    )
    db.add(tx)
    db.flush()
    to_acct.balance += amount
    cb = (
        db.query(EcnyAccount)
        .filter(EcnyAccount.owner_type == "central_bank", EcnyAccount.currency == to_acct.currency)
        .first()
    )
    if not cb:
        raise LedgerError("central bank issuance account not found")
    db.add(
        EcnyEntry(
            entry_id=_new_id("ent"),
            tx_id=tx.tx_id,
            account_id=cb.account_id,
            direction="debit",
            amount=amount,
            currency=to_acct.currency,
        )
    )
    db.add(
        EcnyEntry(
            entry_id=_new_id("ent"),
            tx_id=tx.tx_id,
            account_id=to_account_id,
            direction="credit",
            amount=amount,
            currency=to_acct.currency,
        )
    )
    db.flush()
    return _settle(db, tx)


def burn(
    db: Session, from_account_id: str, amount: int, memo: dict[str, Any] | None = None
) -> EcnyTransaction:
    """Redeem e-CNY back to the central bank (removes from circulation)."""
    if amount <= 0:
        raise LedgerError("burn amount must be positive")
    from_acct = db.query(EcnyAccount).filter(EcnyAccount.account_id == from_account_id).first()
    if not from_acct:
        raise LedgerError(f"account not found: {from_account_id}")
    if from_acct.owner_type != "operator":
        raise LedgerError("burn source must be an operator account")
    if from_acct.balance < amount:
        raise LedgerError("insufficient balance to burn")
    tx = EcnyTransaction(
        tx_id=_new_id("tx"),
        tx_type="burn",
        status="pending",
        amount=amount,
        currency=from_acct.currency,
        from_account=from_account_id,
        memo=json.dumps(memo or {}),
    )
    db.add(tx)
    db.flush()
    from_acct.balance -= amount
    cb = (
        db.query(EcnyAccount)
        .filter(
            EcnyAccount.owner_type == "central_bank", EcnyAccount.currency == from_acct.currency
        )
        .first()
    )
    if not cb:
        raise LedgerError("central bank issuance account not found")
    db.add(
        EcnyEntry(
            entry_id=_new_id("ent"),
            tx_id=tx.tx_id,
            account_id=from_account_id,
            direction="debit",
            amount=amount,
            currency=from_acct.currency,
        )
    )
    db.add(
        EcnyEntry(
            entry_id=_new_id("ent"),
            tx_id=tx.tx_id,
            account_id=cb.account_id,
            direction="credit",
            amount=amount,
            currency=from_acct.currency,
        )
    )
    db.flush()
    return _settle(db, tx)


def transfer(
    db: Session,
    from_account_id: str,
    to_account_id: str,
    amount: int,
    memo: dict[str, Any] | None = None,
) -> EcnyTransaction:
    """Generic atomic transfer between two same-currency accounts."""
    from_acct = db.query(EcnyAccount).filter(EcnyAccount.account_id == from_account_id).first()
    to_acct = db.query(EcnyAccount).filter(EcnyAccount.account_id == to_account_id).first()
    if not from_acct or not to_acct:
        raise LedgerError("account not found")
    tx = EcnyTransaction(
        tx_id=_new_id("tx"),
        tx_type="transfer",
        status="pending",
        amount=amount,
        currency=from_acct.currency,
        from_account=from_account_id,
        to_account=to_account_id,
        memo=json.dumps(memo or {}),
    )
    db.add(tx)
    db.flush()
    _apply_transfer(db, tx, from_acct, to_acct, amount)
    return _settle(db, tx)


def exchange(
    db: Session,
    from_account_id: str,
    to_account_id: str,
    from_amount: int,
    to_amount: int,
    memo: dict[str, Any] | None = None,
) -> EcnyTransaction:
    """FX exchange (PvP basis): debit one currency account, credit another.

    Used by mBridge for atomic cross-currency settlement. Amounts are
    independent (different currencies), so double-entry balance is by value
    equivalence at the agreed rate, not by raw fen.
    """
    if from_amount <= 0 or to_amount <= 0:
        raise LedgerError("exchange amounts must be positive")
    from_acct = db.query(EcnyAccount).filter(EcnyAccount.account_id == from_account_id).first()
    to_acct = db.query(EcnyAccount).filter(EcnyAccount.account_id == to_account_id).first()
    if not from_acct or not to_acct:
        raise LedgerError("account not found")
    if from_acct.balance < from_amount:
        raise LedgerError("insufficient balance to exchange")
    tx = EcnyTransaction(
        tx_id=_new_id("tx"),
        tx_type="exchange",
        status="pending",
        amount=from_amount,
        currency=from_acct.currency,
        from_account=from_account_id,
        to_account=to_account_id,
        memo=json.dumps({**(memo or {}), "to_amount": to_amount, "to_currency": to_acct.currency}),
    )
    db.add(tx)
    db.flush()
    from_acct.balance -= from_amount
    to_acct.balance += to_amount
    db.add(
        EcnyEntry(
            entry_id=_new_id("ent"),
            tx_id=tx.tx_id,
            account_id=from_account_id,
            direction="debit",
            amount=from_amount,
            currency=from_acct.currency,
        )
    )
    db.add(
        EcnyEntry(
            entry_id=_new_id("ent"),
            tx_id=tx.tx_id,
            account_id=to_account_id,
            direction="credit",
            amount=to_amount,
            currency=to_acct.currency,
        )
    )
    return _settle(db, tx)


def transaction(db: Session, tx_id: str) -> EcnyTransaction | None:
    return db.query(EcnyTransaction).filter(EcnyTransaction.tx_id == tx_id).first()


def entries_for(db: Session, tx_id: str) -> list:
    return db.query(EcnyEntry).filter(EcnyEntry.tx_id == tx_id).all()
