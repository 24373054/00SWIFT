from production.security import ProductionPrincipal
from production.service import ProductionPaymentService


class _Query:
    def __init__(self):
        self.predicates = []

    def filter_by(self, **kwargs):
        self.predicates.extend(kwargs.items())
        return self

    def filter(self, *predicates):
        self.predicates.extend(predicates)
        return self

    def one_or_none(self):
        return None


class _Db:
    def __init__(self):
        self.query_obj = _Query()

    def query(self, _model):
        return self.query_obj


def test_order_lookup_always_applies_tenant_filter_even_for_admin():
    principal = ProductionPrincipal("participant-a", "subject", frozenset({"production.admin"}), "test")
    db = _Db()
    try:
        ProductionPaymentService(db).get_order("order-a", principal)
    except Exception as exc:  # expected not-found path after predicate construction
        assert "not found" in str(exc)
    assert any("tenant_id" in str(predicate) for predicate in db.query_obj.predicates)
    assert principal.tenant_id == "tenant:participant-a"
