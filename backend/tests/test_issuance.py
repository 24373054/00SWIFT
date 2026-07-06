"""Issuance & redemption tests."""
import pytest
from ecny.issuance import (ISSUANCE_CAP_FEN, IssuanceError, exchange_to_wallet,
                            issue_to_operator, net_issuance, redeem_from_operator,
                            redeem_from_wallet)
from ecny.ledger import balance, get_or_create_account, mint


def test_issue_to_operator(db):
    op = get_or_create_account(db, "acct-op", "operator", "OP")
    issue_to_operator(db, "acct-op", 500_000)
    assert balance(db, "acct-op") == 500_000
    assert net_issuance(db) == 500_000


def test_redeem_from_operator(db):
    op = get_or_create_account(db, "acct-op", "operator", "OP")
    issue_to_operator(db, "acct-op", 500_000)
    redeem_from_operator(db, "acct-op", 200_000)
    assert balance(db, "acct-op") == 300_000
    assert net_issuance(db) == 300_000


def test_exchange_to_wallet(db):
    op = get_or_create_account(db, "acct-op", "operator", "OP")
    issue_to_operator(db, "acct-op", 500_000)
    from ecny.wallet import open_wallet
    w = open_wallet(db, operator_id=1, tier=1, holder={"real_name": "A", "kyc_level": 3})
    exchange_to_wallet(db, "acct-op", w.wallet_id, 50_000)
    assert balance(db, "acct-op") == 450_000
    assert w.balance == 50_000


def test_redeem_from_wallet(db):
    op = get_or_create_account(db, "acct-op", "operator", "OP")
    issue_to_operator(db, "acct-op", 500_000)
    from ecny.wallet import open_wallet
    w = open_wallet(db, operator_id=1, tier=1, holder={"real_name": "A", "kyc_level": 3})
    exchange_to_wallet(db, "acct-op", w.wallet_id, 50_000)
    redeem_from_wallet(db, w.wallet_id, "acct-op", 20_000)
    assert balance(db, "acct-op") == 470_000
    assert w.balance == 30_000


def test_issuance_cap(db):
    op = get_or_create_account(db, "acct-op", "operator", "OP")
    with pytest.raises(IssuanceError):
        issue_to_operator(db, "acct-op", ISSUANCE_CAP_FEN + 1)
