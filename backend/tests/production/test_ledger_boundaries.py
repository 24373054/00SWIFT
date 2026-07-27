import pytest

from production.gl_bridge import GlBridge
from production.ledger_service import ProductionLedgerService
from production.runtime import ProductionConflict


def test_ledger_service_boundary_and_gl_ack_are_explicit(db):
    service = ProductionLedgerService(db)
    account = service.create_account("payer", "LE-CN", "SUBLEDGER", "CNY", "asset", opening_balance_minor=1000)
    assert account.account_id == "payer"
    batch = GlBridge().build_batch("batch-1", ["j-2", "j-1"], "map-v1")
    assert batch.journal_ids == ("j-1", "j-2")
    with pytest.raises(ProductionConflict, match="receipt hash"):
        GlBridge().acknowledge("ACK")


def test_account_type_controls_normal_balance_direction(db):
    service = ProductionLedgerService(db)
    service.create_account("asset", "LE-CN", "SUBLEDGER", "CNY", "asset", opening_balance_minor=100)
    service.create_account("liability", "LE-CN", "SUBLEDGER", "CNY", "liability", opening_balance_minor=100)
    service.post_journal(journal_id="j-1", legal_entity="LE-CN", book="SUBLEDGER", reason_code="funding", entries=[{"account_id": "asset", "direction": "CREDIT", "currency": "CNY", "amount_minor": 10}, {"account_id": "liability", "direction": "DEBIT", "currency": "CNY", "amount_minor": 10}])


def test_journal_lifecycle_and_posted_immutability(db):
    service = ProductionLedgerService(db)
    service.create_account("a", "LE-CN", "SUBLEDGER", "CNY", "asset", opening_balance_minor=100)
    service.create_account("l", "LE-CN", "SUBLEDGER", "CNY", "liability", opening_balance_minor=100)
    draft = service.create_journal_draft(journal_id="j-life", legal_entity="LE-CN", book="SUBLEDGER", reason_code="funding", entries=[{"account_id": "a", "direction": "CREDIT", "currency": "CNY", "amount_minor": 10}, {"account_id": "l", "direction": "DEBIT", "currency": "CNY", "amount_minor": 10}])
    assert draft.state == "DRAFT"
    assert service.validate_journal("j-life").state == "VALIDATED"
    posted = service.post_journal(journal_id="j-post", legal_entity="LE-CN", book="SUBLEDGER", reason_code="funding", entries=[{"account_id": "a", "direction": "CREDIT", "currency": "CNY", "amount_minor": 10}, {"account_id": "l", "direction": "DEBIT", "currency": "CNY", "amount_minor": 10}])
    posted.reason_code = "tampered"
    with pytest.raises(ValueError, match="immutable"):
        db.flush()


def test_multi_currency_requires_balanced_clearing_legs(db):
    service = ProductionLedgerService(db)
    for account_id, currency in (("cny-a", "CNY"), ("cny-fx", "CNY"), ("hkd-a", "HKD"), ("hkd-fx", "HKD")):
        service.create_account(account_id, "LE-CN", "SUBLEDGER", currency, "asset", opening_balance_minor=100)
    journals = service.post_multi_currency(journal_id="j-fx", legal_entity="LE-CN", book="SUBLEDGER", reason_code="fx", entries=[{"account_id": "cny-a", "direction": "DEBIT", "currency": "CNY", "amount_minor": 10}, {"account_id": "cny-fx", "direction": "CREDIT", "currency": "CNY", "amount_minor": 10}, {"account_id": "hkd-a", "direction": "DEBIT", "currency": "HKD", "amount_minor": 20}, {"account_id": "hkd-fx", "direction": "CREDIT", "currency": "HKD", "amount_minor": 20}], fx_clearing_accounts={"CNY": "cny-fx", "HKD": "hkd-fx"})
    assert {journal.journal_id for journal in journals} == {"j-fx:CNY", "j-fx:HKD"}


def test_trial_balance_rebuilds_from_posted_entries(db):
    service = ProductionLedgerService(db)
    service.create_account("tb-a", "LE-CN", "SUBLEDGER", "CNY", "asset", opening_balance_minor=999)
    service.create_account("tb-l", "LE-CN", "SUBLEDGER", "CNY", "liability", opening_balance_minor=999)
    service.post_journal(journal_id="tb-j", legal_entity="LE-CN", book="SUBLEDGER", reason_code="test", entries=[{"account_id": "tb-a", "direction": "DEBIT", "currency": "CNY", "amount_minor": 15}, {"account_id": "tb-l", "direction": "CREDIT", "currency": "CNY", "amount_minor": 15}])
    result = service.trial_balance("CNY")
    balances = {item["account_id"]: item["balance_minor"] for item in result["accounts"]}
    assert balances["tb-a"] == 15 and balances["tb-l"] == 15
