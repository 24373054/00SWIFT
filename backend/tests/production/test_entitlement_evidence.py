from types import SimpleNamespace

from production.service import ProductionPaymentService


def test_entitlement_fact_payload_contract_includes_version_and_evidence():
    service = ProductionPaymentService.__new__(ProductionPaymentService)
    calls = []
    service._fact = lambda _order, fact_type, state, reference, payload: calls.append((fact_type, state, reference, payload))
    entitlement = SimpleNamespace(entitlement_id="ent-1", version=3, evidence_ref="evidence://ent-1")
    service._fact(SimpleNamespace(order_id="order-1"), "ENTITLEMENT", "MATCHED", entitlement.entitlement_id, {"version": entitlement.version, "evidence_ref": entitlement.evidence_ref})
    assert calls == [("ENTITLEMENT", "MATCHED", "ent-1", {"version": 3, "evidence_ref": "evidence://ent-1"})]
