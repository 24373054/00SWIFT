"""Wallet grading & controlled anonymity tests."""
import pytest
from ecny.wallet import (TIER_LIMITS, WalletError, check_limits, get_wallet,
                         is_traceable, open_wallet)
from ecny.ledger import get_or_create_account, mint


def test_open_tier3_anonymous(db):
    w = open_wallet(db, operator_id=1, tier=3)
    assert w.tier == 3
    assert w.holder_id is None  # anonymous
    assert is_traceable(w) is False


def test_open_tier1_requires_kyc(db):
    with pytest.raises(WalletError):
        open_wallet(db, operator_id=1, tier=1)  # no holder
    w = open_wallet(db, operator_id=1, tier=1, holder={
        "real_name": "Alice", "id_type": "id_card", "id_hash": "h1", "kyc_level": 3
    })
    assert w.holder_id is not None
    assert is_traceable(w) is True


def test_tier_limit_enforced(db):
    op = get_or_create_account(db, "acct-op", "operator", "OP")
    mint(db, "acct-op", 10_000_000)
    w = open_wallet(db, operator_id=1, tier=3)
    # tier 3 per_tx = 20000 fen
    with pytest.raises(WalletError):
        check_limits(db, w, 100_000)
    # within limit OK
    check_limits(db, w, 10_000)


def test_balance_cap_enforced(db):
    op = get_or_create_account(db, "acct-op", "operator", "OP")
    mint(db, "acct-op", 10_000_000)
    w = open_wallet(db, operator_id=1, tier=3)
    # tier 3 balance_cap = 500_000; set wallet near cap
    w.balance = 490_000
    with pytest.raises(WalletError):
        check_limits(db, w, 20_000)


def test_get_wallet(db):
    w = open_wallet(db, operator_id=1, tier=3)
    assert get_wallet(db, w.wallet_id) is not None
    assert get_wallet(db, "nonexistent") is None
