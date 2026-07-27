from production.models import ProductionPaymentOrder


def test_payment_dimensions_are_independent_and_delivery_is_not_final(db):
    order = ProductionPaymentOrder(
        order_id="dim-1", uetr="223e4567-e89b-42d3-a456-426614174000", instruction_id="i1", end_to_end_id="e1", transaction_id="t1", tenant_id="tenant:P1", initiator_participant="P1", corridor="CN-HK", debtor_party_ref="d", debtor_account_ref="da", creditor_party_ref="c", creditor_account_ref="ca", amount_minor=100, currency="CNY", settlement_currency="CNY", purpose_code="TRADE", payload="{}", payload_hash="0" * 64, orchestration_state="MESSAGE_DELIVERED", completion_profile_id="cmp", projection_rule_version="v1",
        authorization_state="APPROVED", compliance_state="PASSED", funding_state="RESERVED", fx_state="NOT_REQUIRED", message_delivery_state="DELIVERED", value_settlement_state="PENDING", beneficiary_state="PENDING", reconciliation_state="PENDING",
    )
    db.add(order)
    db.commit()
    assert order.orchestration_state == "MESSAGE_DELIVERED"
    assert order.value_settlement_state == "PENDING"
    assert order.orchestration_state != "OPERATIONALLY_CLOSED"
