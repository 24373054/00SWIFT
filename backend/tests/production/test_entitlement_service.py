import datetime as dt

import pytest

from production.entitlement_service import EntitlementError, EntitlementService


def test_entitlement_amount_band_and_bilateral_match_are_fail_closed():
    class Query:
        def filter(self, *_predicates):
            return self

        def order_by(self, *_predicates):
            return self

        def all(self):
            return []

    class Db:
        def query(self, _model):
            return Query()

    with pytest.raises(EntitlementError, match="bilateral"):
        EntitlementService(Db()).match(participant_id="A", counterparty_id="B", direction="OUTBOUND", service="payment.create", message_type="pacs.008", corridor="CN-HK", currency="CNY", amount_minor=100, now=dt.datetime.now(dt.UTC))
