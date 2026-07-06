"""mBridge multi-CBDC bridge.

Models a multi-central-bank platform where each participant issues its own
CBDC on a shared ledger. Cross-border payments settle atomically via PvP
(payment-versus-payment): the debit and credit happen together or not at all,
eliminating settlement risk.

FX rates are fixed-seed in sandbox (deterministic for tests). Live mode would
source real rates.

Accounts for foreign CBDCs are created on demand under owner_type 'operator'
with the foreign currency; the home e-CNY account is CNY.
"""
from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from core.time import now_utc
from database import EcnyAccount, EcnyBridgeChannel, EcnyBridgeTransaction
from ecny.ledger import LedgerError, exchange, get_or_create_account
from iso20022.uetr import generate_uetr

# Sandbox FX rates (CNY -> foreign). Deterministic seed.
SANDBOX_FX = {
    "CNY": Decimal("1.000000"),
    "HKD": Decimal("1.080000"),
    "THB": Decimal("4.900000"),
    "AED": Decimal("0.510000"),
    "USD": Decimal("0.139000"),
    "EUR": Decimal("0.128000"),
}


class BridgeError(Exception):
    pass


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def fx_rate(from_ccy: str, to_ccy: str) -> Decimal:
    """Cross rate via CNY as the bridge currency."""
    f = SANDBOX_FX.get(from_ccy)
    t = SANDBOX_FX.get(to_ccy)
    if not f or not t:
        raise BridgeError(f"unsupported currency pair: {from_ccy}/{to_ccy}")
    return (t / f)


def list_channels(db: Session, channel_type: str = "mbridge") -> list:
    return db.query(EcnyBridgeChannel).filter(
        EcnyBridgeChannel.channel_type == channel_type,
        EcnyBridgeChannel.status == "active",
    ).all()


def settle_pvp(db: Session, from_account_id: str, to_account_id: str,
               from_amount_fen: int, from_ccy: str, to_ccy: str,
               counterparty: Optional[str] = None) -> EcnyBridgeTransaction:
    """Atomic PvP settlement: debit source currency, credit target currency
    at the agreed FX rate. Returns the bridge transaction record.
    """
    if from_amount_fen <= 0:
        raise BridgeError("amount must be positive")
    rate = fx_rate(from_ccy, to_ccy)
    to_amount_fen = int(Decimal(from_amount_fen) * rate)
    if to_amount_fen <= 0:
        raise BridgeError("computed target amount is zero")
    uetr = generate_uetr()
    bridge_tx = EcnyBridgeTransaction(
        bridge_tx_id=_new_id("btx"), uetr=uetr,
        channel_id="ch-mbridge-0001",
        from_currency=from_ccy, from_amount=from_amount_fen,
        to_currency=to_ccy, to_amount=to_amount_fen,
        fx_rate=str(rate), status="pending",
        counterparty_ref=counterparty,
    )
    db.add(bridge_tx)
    db.flush()
    try:
        exchange(db, from_account_id, to_account_id, from_amount_fen, to_amount_fen,
                 memo={"uetr": uetr, "channel": "mbridge", "fx_rate": str(rate)})
    except LedgerError as e:
        bridge_tx.status = "failed"
        raise BridgeError(f"PvP settlement failed: {e}")
    bridge_tx.status = "settled"
    bridge_tx.settled_at = now_utc()
    return bridge_tx


def get_bridge_tx(db: Session, uetr: str) -> Optional[EcnyBridgeTransaction]:
    return db.query(EcnyBridgeTransaction).filter(EcnyBridgeTransaction.uetr == uetr).first()
