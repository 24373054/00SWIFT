from production.models import ProductionPaymentOrder


def test_payment_reference_fields_are_separate_and_scoped(db):
    order = ProductionPaymentOrder(
        order_id="refs-1", uetr="623e4567-e89b-42d3-a456-426614174000", instruction_id="i1", end_to_end_id="e2e-1", transaction_id="tx-1", tenant_id="tenant:P1", initiator_participant="P1", corridor="CN-HK", debtor_party_ref="d", debtor_account_ref="da", creditor_party_ref="c", creditor_account_ref="ca", amount_minor=100, currency="CNY", settlement_currency="CNY", purpose_code="TRADE", payload="{}", payload_hash="0" * 64, orchestration_state="CONTROL_CHECKS", completion_profile_id="cmp", projection_rule_version="v1",
    )
    db.add(order)
    db.commit()
    assert order.uetr != order.end_to_end_id != order.transaction_id
