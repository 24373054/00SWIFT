import pytest

from production.ledger_service import BalanceSnapshotService
from production.models import ProductionInvestigationCase, ProductionJournalEntry
from production.runtime import ProductionConflict


def test_ledger_imbalance_creates_sev0_case(db):
    db.add(ProductionJournalEntry(entry_id="bad-entry", journal_id="bad-journal", account_id="a", direction="DEBIT", currency="CNY", amount_minor=1))
    db.flush()
    with pytest.raises(ProductionConflict, match="imbalance"):
        BalanceSnapshotService(db).assert_balanced("bad-journal")
    assert db.query(ProductionInvestigationCase).filter_by(case_type="SEV-0_LEDGER_IMBALANCE").count() == 1
