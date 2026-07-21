"""CIPS bilateral channel (Cross-Border Interbank Payment System).

Models e-CNY <-> offshore RMB cross-border settlement via CIPS. Unlike
mBridge (multi-CBDC PvP), CIPS is a single-currency (CNY) rail: the e-CNY
is converted to/from offshore RMB at 1:1, and the cross-border leg is tracked
by UETR reusing the GPI tracker model.

route_cross_border decides mBridge vs CIPS based on the target currency:
same-currency (CNY->CNY) or RMB-zone counterparties go via CIPS; foreign-CBDC
settlement goes via mBridge.
"""

from __future__ import annotations

from core.time import now_utc
from database import EcnyBridgeTransaction
from ecny.bridge.mbridge import _new_id
from ecny.ledger import LedgerError, transfer
from iso20022.uetr import generate_uetr


class CipsError(Exception):
    pass


def route_cross_border(target_currency: str) -> str:
    """Decide the bridge channel for a given target currency.

    CIPS for CNY (offshore RMB zone); mBridge for foreign CBDCs.
    """
    if target_currency == "CNY":
        return "cips"
    return "mbridge"


def settle_via_cips(
    db,
    from_account_id: str,
    to_account_id: str,
    amount_fen: int,
    counterparty_ref: str | None = None,
) -> EcnyBridgeTransaction:
    """Settle a CNY->CNY cross-border payment via CIPS (1:1)."""
    if amount_fen <= 0:
        raise CipsError("amount must be positive")
    uetr = generate_uetr()
    bridge_tx = EcnyBridgeTransaction(
        bridge_tx_id=_new_id("btx"),
        uetr=uetr,
        channel_id="ch-cips-0001",
        from_currency="CNY",
        from_amount=amount_fen,
        to_currency="CNY",
        to_amount=amount_fen,
        fx_rate="1.000000",
        status="pending",
        counterparty_ref=counterparty_ref,
    )
    db.add(bridge_tx)
    db.flush()
    try:
        transfer(
            db, from_account_id, to_account_id, amount_fen, memo={"uetr": uetr, "channel": "cips"}
        )
    except LedgerError as e:
        bridge_tx.status = "failed"
        raise CipsError(f"CIPS settlement failed: {e}") from e
    bridge_tx.status = "settled"
    bridge_tx.settled_at = now_utc()
    return bridge_tx
