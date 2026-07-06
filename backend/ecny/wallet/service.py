"""DC/EP wallet grading (tier 1/2/3) and controlled anonymity.

Tier 1 — strong KYC, large value. Tier 2 — medium. Tier 3 — small, anonymous.

Controlled anonymity: tier-3 wallets are not linked to a holder identity
(id_hash null). Small-value transactions are untraceable; large-value or
tier-1 transactions are traceable. Thresholds are config-driven.

Limits are per-transaction and daily-cumulative (fen). Enforced on transfer.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from core.time import now_utc
from database import EcnyAccount, EcnyHolder, EcnyWallet


# Tier limits in fen (分). 1 CNY = 100 fen.
# Tier 1: per-tx 5,000,000 fen (50k CNY), daily 200k CNY, balance cap 1,000k CNY.
# Tier 2: per-tx 100,000 fen (1k CNY), daily 5k CNY, balance cap 10k CNY.
# Tier 3: per-tx 20,000 fen (200 CNY), daily 2k CNY, balance cap 5k CNY.
TIER_LIMITS = {
    1: {"per_tx": 5_000_000, "daily": 20_000_000, "balance_cap": 100_000_000, "kyc_required": 3},
    2: {"per_tx": 100_000, "daily": 500_000, "balance_cap": 1_000_000, "kyc_required": 2},
    3: {"per_tx": 20_000, "daily": 200_000, "balance_cap": 500_000, "kyc_required": 0},
}

LARGE_CASH_THRESHOLD = 500_000  # 5k CNY — triggers compliance flag


class WalletError(Exception):
    """Wallet operation invalid."""


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def open_wallet(db: Session, operator_id: int, tier: int,
                holder: Optional[Dict[str, Any]] = None,
                operator_account_id: Optional[str] = None) -> EcnyWallet:
    """Open a wallet of the given tier. For tier 1/2, holder KYC is required."""
    if tier not in TIER_LIMITS:
        raise WalletError(f"invalid tier: {tier}")
    lim = TIER_LIMITS[tier]

    # Tier 1/2 require KYC (holder with real_name).
    if tier < 3 and (not holder or not holder.get("real_name")):
        raise WalletError(f"tier {tier} requires KYC (real_name)")

    holder_id = None
    if holder:
        if tier < 3 and not holder.get("real_name"):
            raise WalletError(f"tier {tier} requires real_name (KYC)")
        h = EcnyHolder(
            holder_id=_new_id("hld"),
            real_name=holder.get("real_name"),
            id_type=holder.get("id_type"),
            id_hash=holder.get("id_hash"),
            kyc_level=holder.get("kyc_level", lim["kyc_required"]),
            country_code=holder.get("country_code", "CN"),
        )
        db.add(h)
        db.flush()
        holder_id = h.holder_id

    wallet_id = _new_id("wlt")
    wallet = EcnyWallet(
        wallet_id=wallet_id, holder_id=holder_id, tier=tier,
        operator_id=operator_id, currency="CNY", balance=0, status="active",
    )
    db.add(wallet)
    db.flush()

    # Create the backing ledger account for this wallet.
    acct = EcnyAccount(
        account_id=_new_id("acct-w"),
        owner_type="wallet", owner_ref=wallet_id, currency="CNY", balance=0,
    )
    db.add(acct)
    db.flush()
    wallet._ledger_account_id = acct.account_id  # ephemeral, not persisted
    return wallet


def get_wallet(db: Session, wallet_id: str) -> Optional[EcnyWallet]:
    return db.query(EcnyWallet).filter(EcnyWallet.wallet_id == wallet_id).first()


def ledger_account_id_for(db: Session, wallet_id: str) -> str:
    acct = db.query(EcnyAccount).filter(EcnyAccount.owner_ref == wallet_id,
                                        EcnyAccount.owner_type == "wallet").first()
    if not acct:
        raise WalletError(f"ledger account not found for wallet {wallet_id}")
    return acct.account_id


def check_limits(db: Session, wallet: EcnyWallet, amount: int) -> None:
    """Raise WalletError if the per-tx or balance-cap limit is exceeded."""
    if amount <= 0:
        raise WalletError("amount must be positive")
    lim = TIER_LIMITS[wallet.tier]
    if amount > lim["per_tx"]:
        raise WalletError(f"per-tx limit exceeded: {amount} > {lim['per_tx']} (tier {wallet.tier})")
    if wallet.balance + amount > lim["balance_cap"]:
        raise WalletError(f"balance cap exceeded (tier {wallet.tier})")


def is_traceable(wallet: EcnyWallet) -> bool:
    """Tier 1/2 wallets are traceable (linked to holder). Tier 3 anonymous."""
    return wallet.tier < 3
