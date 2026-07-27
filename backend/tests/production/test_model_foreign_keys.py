from __future__ import annotations

from production.models import (
    ProductionInboxMessage,
    ProductionJournalEntry,
    ProductionPaymentFact,
    ProductionPaymentOrder,
    ProductionReportReceipt,
)


def test_core_production_models_declare_restrictive_foreign_keys_without_delete_cascade():
    for model in (ProductionPaymentOrder, ProductionPaymentFact, ProductionJournalEntry, ProductionInboxMessage, ProductionReportReceipt):
        foreign_keys = list(model.__table__.foreign_keys)
        assert foreign_keys, model.__name__
        assert all(key.ondelete == "RESTRICT" for key in foreign_keys)
    assert ProductionPaymentOrder.facts.property.viewonly
    assert not ProductionPaymentOrder.facts.property.cascade.delete
