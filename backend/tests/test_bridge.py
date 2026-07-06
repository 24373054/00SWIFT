"""Bridge (mBridge PvP + CIPS) tests."""
import pytest
from database import EcnyAccount
from ecny.bridge import (BridgeError, get_bridge_tx, route_cross_border,
                          settle_pvp, settle_via_cips)
from ecny.ledger import get_or_create_account, mint


def _seed(db):
    cny = get_or_create_account(db, "acct-cny", "operator", "C", "CNY")
    hkd = EcnyAccount(account_id="acct-hkd", owner_type="operator", owner_ref="H",
                      currency="HKD", balance=10_000_000)
    db.add(hkd); db.flush()
    mint(db, "acct-cny", 1_000_000)
    return cny, hkd


def test_route_cny_uses_cips(db):
    assert route_cross_border("CNY") == "cips"


def test_route_foreign_uses_mbridge(db):
    assert route_cross_border("HKD") == "mbridge"
    assert route_cross_border("USD") == "mbridge"


def test_mbridge_pvp_settles(db):
    cny, hkd = _seed(db)
    btx = settle_pvp(db, "acct-cny", "acct-hkd", 100_000, "CNY", "HKD", "HKMA")
    assert btx.status == "settled"
    assert btx.to_currency == "HKD"
    assert btx.to_amount == 108_000  # 100000 * 1.08
    assert get_bridge_tx(db, btx.uetr) is not None


def test_cips_settles_1to1(db):
    cny2 = EcnyAccount(account_id="acct-cny2", owner_type="operator", owner_ref="C2",
                       currency="CNY", balance=0)
    db.add(cny2); db.flush()
    cny, _ = _seed(db)
    btx = settle_via_cips(db, "acct-cny", "acct-cny2", 50_000, "participant")
    assert btx.status == "settled"
    assert btx.to_amount == 50_000


def test_mbridge_rejects_zero(db):
    cny, hkd = _seed(db)
    with pytest.raises(BridgeError):
        settle_pvp(db, "acct-cny", "acct-hkd", 0, "CNY", "HKD")


def test_mbridge_insufficient_funds(db):
    cny, hkd = _seed(db)
    with pytest.raises(BridgeError):
        settle_pvp(db, "acct-cny", "acct-hkd", 999_999_999, "CNY", "HKD")
