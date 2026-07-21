"""DC/EP wallet grading, limits, and controlled anonymity.

The backing ledger account is the sole balance source. ``EcnyWallet.balance``
is retained only for schema compatibility and is never used for authorization
or monetary decisions.
"""

from __future__ import annotations

import uuid
from datetime import UTC
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.time import now_utc
from database import EcnyAccount, EcnyHolder, EcnyTransaction, EcnyWallet

TIER_LIMITS = {
    1: {"per_tx": 5_000_000, "daily": 20_000_000, "balance_cap": 100_000_000, "kyc_required": 3},
    2: {"per_tx": 100_000, "daily": 500_000, "balance_cap": 1_000_000, "kyc_required": 2},
    3: {"per_tx": 20_000, "daily": 200_000, "balance_cap": 500_000, "kyc_required": 0},
}
LARGE_CASH_THRESHOLD = 500_000


class WalletError(Exception):
    """Wallet operation is invalid."""


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def open_wallet(
    db: Session,
    operator_id: int,
    tier: int,
    holder: dict[str, Any] | None = None,
    operator_account_id: str | None = None,
) -> EcnyWallet:
    if tier not in TIER_LIMITS:
        raise WalletError(f"invalid tier: {tier}")
    limits = TIER_LIMITS[tier]

    operator = None
    if operator_account_id:
        operator = (
            db.query(EcnyAccount).filter(EcnyAccount.account_id == operator_account_id).first()
        )
        if not operator or operator.owner_type != "operator" or operator.currency != "CNY":
            raise WalletError("operator_account_id must reference a CNY operator account")
        operator_id = operator.id

    if tier < 3 and (not holder or not holder.get("real_name")):
        raise WalletError(f"tier {tier} requires KYC (real_name)")
    if holder and int(holder.get("kyc_level", limits["kyc_required"])) < limits["kyc_required"]:
        raise WalletError(f"tier {tier} requires KYC level {limits['kyc_required']}")

    holder_id = None
    if holder:
        entity = EcnyHolder(
            holder_id=_new_id("hld"),
            real_name=holder.get("real_name"),
            id_type=holder.get("id_type"),
            id_hash=holder.get("id_hash"),
            kyc_level=holder.get("kyc_level", limits["kyc_required"]),
            country_code=holder.get("country_code", "CN"),
        )
        db.add(entity)
        db.flush()
        holder_id = entity.holder_id

    wallet = EcnyWallet(
        wallet_id=_new_id("wlt"),
        holder_id=holder_id,
        tier=tier,
        operator_id=operator_id,
        currency="CNY",
        balance=0,
        status="active",
    )
    db.add(wallet)
    db.flush()
    account = EcnyAccount(
        account_id=_new_id("acct-w"),
        owner_type="wallet",
        owner_ref=wallet.wallet_id,
        currency="CNY",
        balance=0,
    )
    db.add(account)
    db.flush()
    wallet._ledger_account_id = account.account_id
    return wallet


def get_wallet(db: Session, wallet_id: str) -> EcnyWallet | None:
    return db.query(EcnyWallet).filter(EcnyWallet.wallet_id == wallet_id).first()


def ledger_account_id_for(db: Session, wallet_id: str) -> str:
    account = (
        db.query(EcnyAccount)
        .filter(
            EcnyAccount.owner_ref == wallet_id,
            EcnyAccount.owner_type == "wallet",
        )
        .first()
    )
    if not account:
        raise WalletError(f"ledger account not found for wallet {wallet_id}")
    return account.account_id


def wallet_balance(db: Session, wallet: EcnyWallet | str) -> int:
    wallet_id = wallet if isinstance(wallet, str) else wallet.wallet_id
    account_id = ledger_account_id_for(db, wallet_id)
    account = db.query(EcnyAccount).filter(EcnyAccount.account_id == account_id).first()
    if not account:
        raise WalletError("wallet ledger account not found")
    return int(account.balance or 0)


def _outgoing_today(db: Session, account_id: str) -> int:
    start = (
        now_utc().astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    )
    value = (
        db.query(func.coalesce(func.sum(EcnyTransaction.amount), 0))
        .filter(
            EcnyTransaction.from_account == account_id,
            EcnyTransaction.status == "settled",
            EcnyTransaction.created_at >= start,
        )
        .scalar()
    )
    return int(value or 0)


def check_limits(
    db: Session,
    wallet: EcnyWallet,
    amount: int,
    *,
    incoming: bool = False,
) -> None:
    """Enforce status, per-transaction, daily-outgoing, and balance-cap rules."""
    if wallet.status != "active":
        raise WalletError("wallet is not active")
    if amount <= 0:
        raise WalletError("amount must be positive")
    limits = TIER_LIMITS[wallet.tier]
    if amount > limits["per_tx"]:
        raise WalletError(
            f"per-tx limit exceeded: {amount} > {limits['per_tx']} (tier {wallet.tier})"
        )
    account_id = ledger_account_id_for(db, wallet.wallet_id)
    current = wallet_balance(db, wallet)
    if incoming:
        if current + amount > limits["balance_cap"]:
            raise WalletError(f"balance cap exceeded (tier {wallet.tier})")
    elif _outgoing_today(db, account_id) + amount > limits["daily"]:
        raise WalletError(f"daily outgoing limit exceeded (tier {wallet.tier})")


def is_traceable(wallet: EcnyWallet) -> bool:
    return wallet.tier < 3
