from production.models import ProductionPaymentOrder
from production.service import ProductionPaymentService


def test_append_fact_keeps_business_reference_and_adds_sequence_hashes(db):
    db.add(ProductionPaymentOrder(
        order_id="fact-1", uetr="423e4567-e89b-42d3-a456-426614174000", instruction_id="i1", tenant_id="tenant:P1", initiator_participant="P1", corridor="CN-HK", debtor_party_ref="d", debtor_account_ref="da", creditor_party_ref="c", creditor_account_ref="ca", amount_minor=100, currency="CNY", settlement_currency="CNY", purpose_code="TRADE", payload="{}", payload_hash="0" * 64, orchestration_state="CONTROL_CHECKS", completion_profile_id="cmp", projection_rule_version="v1",
    ))
    db.commit()
    service = ProductionPaymentService(db)
    first = service.append_fact("fact-1", "COMPLIANCE", "PENDING", "screen-1", {"rule_version": "r1"})
    second = service.append_fact("fact-1", "COMPLIANCE", "PASSED", "screen-1", {"rule_version": "r1", "evidence_id": "ev-1"})
    db.commit()
    assert first.reference == second.reference == "screen-1"
    assert second.fact_sequence == 2 and second.supersedes_fact_id == first.fact_id
    assert len(second.input_hash) == 64 and len(second.output_hash) == 64
