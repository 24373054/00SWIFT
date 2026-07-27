from production.ledger_service import BalanceSnapshotService, ProductionLedgerService


def test_balance_snapshot_records_entry_hash(db):
    service = ProductionLedgerService(db)
    service.create_account("snap-a", "LE-CN", "SUBLEDGER", "CNY", "asset", opening_balance_minor=100)
    service.create_account("snap-l", "LE-CN", "SUBLEDGER", "CNY", "liability", opening_balance_minor=100)
    service.post_journal(journal_id="snap-j", legal_entity="LE-CN", book="SUBLEDGER", reason_code="test", entries=[{"account_id": "snap-a", "direction": "DEBIT", "currency": "CNY", "amount_minor": 2}, {"account_id": "snap-l", "direction": "CREDIT", "currency": "CNY", "amount_minor": 2}])
    snapshot = BalanceSnapshotService(db).create("snap-1", "tenant:P1", "SUBLEDGER", "snap-a", "2026-07-27")
    assert snapshot.source_max_entry_sequence > 0 and len(snapshot.source_hash) == 64
