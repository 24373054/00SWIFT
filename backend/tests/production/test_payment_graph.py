from production.models import ProductionPaymentOrder
from production.payment_graph import load_payment_graph


def test_payment_graph_returns_explicit_related_aggregates(db):
    db.add(ProductionPaymentOrder(
        order_id="graph-1", uetr="723e4567-e89b-42d3-a456-426614174000", instruction_id="i1", end_to_end_id="e1", transaction_id="t1", tenant_id="tenant:P1", initiator_participant="P1", corridor="CN-HK", debtor_party_ref="d", debtor_account_ref="da", creditor_party_ref="c", creditor_account_ref="ca", amount_minor=100, currency="CNY", settlement_currency="CNY", purpose_code="TRADE", payload="{}", payload_hash="0" * 64, orchestration_state="CONTROL_CHECKS", completion_profile_id="cmp", projection_rule_version="v1",
    ))
    db.commit()
    graph = load_payment_graph(db, "graph-1")
    assert graph["original"].order_id == "graph-1"
    assert set(graph) == {"original", "cancellations", "returns", "investigations", "fx_trades", "settlement_legs", "journals", "reconciliations", "reports"}
