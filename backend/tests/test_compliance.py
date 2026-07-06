"""Compliance layer tests."""
from ecny.compliance import check_transaction, list_reports
from ecny.wallet import LARGE_CASH_THRESHOLD, open_wallet
from ecny.ledger import get_or_create_account, mint


def _anon_wallet(db):
    return open_wallet(db, operator_id=1, tier=3)


def test_small_transaction_no_report(db):
    w = _anon_wallet(db)
    reports = check_transaction(db, w, 5_000, cross_border=False)
    assert reports == []


def test_large_cash_flagged(db):
    w = _anon_wallet(db)
    reports = check_transaction(db, w, LARGE_CASH_THRESHOLD, cross_border=False)
    types = [r.report_type for r in reports]
    assert "large_cash" in types


def test_cross_border_flagged(db):
    w = _anon_wallet(db)
    reports = check_transaction(db, w, 5_000, cross_border=True, counterparty="HKMA")
    assert any(r.report_type == "cross_border" for r in reports)


def test_suspicious_threshold_adjacent(db):
    w = _anon_wallet(db)
    amt = LARGE_CASH_THRESHOLD  # exactly at threshold triggers large_cash + suspicious
    reports = check_transaction(db, w, amt, cross_border=False)
    types = [r.report_type for r in reports]
    assert "suspicious" in types


def test_reports_persisted(db):
    w = _anon_wallet(db)
    check_transaction(db, w, LARGE_CASH_THRESHOLD, cross_border=False)
    db.commit()
    assert len(list_reports(db)) >= 1
