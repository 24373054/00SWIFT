import datetime as dt
from types import SimpleNamespace

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


def test_bilateral_matrix_direction_counterparty_and_wildcard_policy():
    class Query:
        def filter(self, *_predicates):
            return self

        def order_by(self, *_predicates):
            return self

        def all(self):
            return [SimpleNamespace(id=1, counterparty_id="B", direction="OUTBOUND", service="payment.create", message_type="pacs.008", corridor="CN-HK", currency="CNY", min_amount_minor=1, max_amount_minor=1000, effective_to=None, approved_by="maker", evidence_ref="e", version=1, entitlement_id="ent-1")]

    class Db:
        def query(self, _model):
            return Query()

    service = EntitlementService(Db())
    assert service.match(participant_id="A", counterparty_id="B", direction="OUTBOUND", service="payment.create", message_type="pacs.008", corridor="CN-HK", currency="CNY", amount_minor=100).entitlement_id == "ent-1"
    with pytest.raises(EntitlementError, match="bilateral"):
        service.match(participant_id="A", counterparty_id="B", direction="INBOUND", service="payment.create", message_type="pacs.008", corridor="CN-HK", currency="CNY", amount_minor=100)
    with pytest.raises(EntitlementError, match="bilateral"):
        service.match(participant_id="A", counterparty_id="C", direction="OUTBOUND", service="payment.create", message_type="pacs.008", corridor="CN-HK", currency="CNY", amount_minor=100)
