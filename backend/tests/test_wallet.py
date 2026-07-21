"""Wallet grading & controlled anonymity tests."""

import pytest

from ecny.ledger import get_or_create_account, mint
from ecny.wallet import (
    WalletError,
    check_limits,
    get_wallet,
    is_traceable,
    ledger_account_id_for,
    open_wallet,
)


def test_open_tier3_anonymous(db):
    w = open_wallet(db, operator_id=1, tier=3)
    assert w.tier == 3
    assert w.holder_id is None  # anonymous
    assert is_traceable(w) is False


def test_open_tier1_requires_kyc(db):
    with pytest.raises(WalletError):
        open_wallet(db, operator_id=1, tier=1)  # no holder
    w = open_wallet(
        db,
        operator_id=1,
        tier=1,
        holder={"real_name": "Alice", "id_type": "id_card", "id_hash": "h1", "kyc_level": 3},
    )
    assert w.holder_id is not None
    assert is_traceable(w) is True


def test_tier_limit_enforced(db):
    get_or_create_account(db, "acct-op", "operator", "OP")
    mint(db, "acct-op", 10_000_000)
    w = open_wallet(db, operator_id=1, tier=3)
    # tier 3 per_tx = 20000 fen
    with pytest.raises(WalletError):
        check_limits(db, w, 100_000)
    # within limit OK
    check_limits(db, w, 10_000)


def test_balance_cap_enforced(db):
    get_or_create_account(db, "acct-op", "operator", "OP")
    mint(db, "acct-op", 10_000_000)
    w = open_wallet(db, operator_id=1, tier=3)
    # The ledger account, not the legacy wallet cache, is authoritative.
    from database import EcnyAccount

    account = (
        db.query(EcnyAccount)
        .filter(EcnyAccount.account_id == ledger_account_id_for(db, w.wallet_id))
        .one()
    )
    account.balance = 490_000
    with pytest.raises(WalletError):
        check_limits(db, w, 20_000, incoming=True)


def test_get_wallet(db):
    w = open_wallet(db, operator_id=1, tier=3)
    assert get_wallet(db, w.wallet_id) is not None
    assert get_wallet(db, "nonexistent") is None


def test_daily_outgoing_limit_enforced_from_ledger(db):
    from core.time import now_utc
    from database import EcnyAccount, EcnyTransaction

    w = open_wallet(db, operator_id=1, tier=3)
    account_id = ledger_account_id_for(db, w.wallet_id)
    account = db.query(EcnyAccount).filter(EcnyAccount.account_id == account_id).one()
    account.balance = 500_000
    for index in range(10):
        db.add(
            EcnyTransaction(
                tx_id=f"daily-{index}",
                tx_type="transfer",
                status="settled",
                amount=20_000,
                currency="CNY",
                from_account=account_id,
                to_account="other",
                created_at=now_utc(),
                settled_at=now_utc(),
            )
        )
    db.flush()
    with pytest.raises(WalletError):
        check_limits(db, w, 1)
