
import pytest

from production.runtime import ProductionConflict, ProductionOutboxService


def test_outbox_enqueue_requires_scope_and_hashes_payload():
    class Query:
        def filter_by(self, **_kwargs):
            return self

        def one_or_none(self):
            return None

    class Db:
        def query(self, _model):
            return Query()

        def add(self, value):
            self.value = value

        def flush(self):
            return None

    with pytest.raises(ProductionConflict, match="tenant and participant"):
        ProductionOutboxService(Db()).enqueue("payment.created", "p1", {"x": 1})

    db = Db()
    event = ProductionOutboxService(db).enqueue("payment.created", "p1", {"tenant_id": "t1", "participant_id": "p1", "x": 1})
    assert event.tenant_id == "t1" and len(event.payload_hash) == 64
