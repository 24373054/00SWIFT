"""Ledger engine unit tests — invariants and atomicity."""
import pytest
from ecny.ledger import (
    LedgerError, balance, burn, exchange, get_or_create_account, mint, transfer,
)


def test_mint_and_balance(db):
    op = get_or_create_account(db, "acct-op-1", "operator", "OP1")
    mint(db, "acct-op-1", 1_000_000)
    assert balance(db, "acct-op-1") == 1_000_000


def test_mint_rejects_non_operator(db):
    w = get_or_create_account(db, "acct-w-1", "wallet", "W1")
    with pytest.raises(LedgerError):
        mint(db, "acct-w-1", 100)


def test_transfer_atomic(db):
    a = get_or_create_account(db, "acct-a", "operator", "A")
    b = get_or_create_account(db, "acct-b", "operator", "B")
    mint(db, "acct-a", 500)
    transfer(db, "acct-a", "acct-b", 200)
    assert balance(db, "acct-a") == 300
    assert balance(db, "acct-b") == 200


def test_overdraft_rejected(db):
    a = get_or_create_account(db, "acct-a", "operator", "A")
    b = get_or_create_account(db, "acct-b", "operator", "B")
    mint(db, "acct-a", 100)
    with pytest.raises(LedgerError):
        transfer(db, "acct-a", "acct-b", 999)


def test_negative_amount_rejected(db):
    a = get_or_create_account(db, "acct-a", "operator", "A")
    with pytest.raises(LedgerError):
        mint(db, "acct-a", -5)


def test_self_transfer_rejected(db):
    a = get_or_create_account(db, "acct-a", "operator", "A")
    mint(db, "acct-a", 100)
    with pytest.raises(LedgerError):
        transfer(db, "acct-a", "acct-a", 50)


def test_burn_reduces_balance(db):
    a = get_or_create_account(db, "acct-a", "operator", "A")
    mint(db, "acct-a", 1_000)
    burn(db, "acct-a", 400)
    assert balance(db, "acct-a") == 600


def test_exchange_atomic(db):
    from database import EcnyAccount
    cny = get_or_create_account(db, "acct-cny", "operator", "C", "CNY")
    hkd = EcnyAccount(account_id="acct-hkd", owner_type="operator", owner_ref="H", currency="HKD", balance=0)
    db.add(hkd); db.flush()
    mint(db, "acct-cny", 10_000)
    exchange(db, "acct-cny", "acct-hkd", 1_000, 1_080)
    assert balance(db, "acct-cny") == 9_000
    assert balance(db, "acct-hkd") == 1_080


def test_double_entry_balance(db):
    from database import EcnyEntry
    a = get_or_create_account(db, "acct-a", "operator", "A")
    b = get_or_create_account(db, "acct-b", "operator", "B")
    mint(db, "acct-a", 500)
    tx = transfer(db, "acct-a", "acct-b", 200)
    entries = db.query(EcnyEntry).filter(EcnyEntry.tx_id == tx.tx_id).all()
    assert len(entries) == 2
    debit = sum(e.amount for e in entries if e.direction == "debit")
    credit = sum(e.amount for e in entries if e.direction == "credit")
    assert debit == credit == 200
