from __future__ import annotations

from sqlalchemy import BigInteger

from production.models import (
    ProductionFxQuote,
    ProductionJournalEntry,
    ProductionLedgerAccount,
    ProductionPaymentOrder,
)


def test_monetary_columns_use_bigint():
    for model, column in (
        (ProductionPaymentOrder, "amount_minor"), (ProductionFxQuote, "base_amount_minor"),
        (ProductionLedgerAccount, "balance_minor"), (ProductionJournalEntry, "amount_minor"),
    ):
        assert isinstance(getattr(model, column).property.columns[0].type, BigInteger)
