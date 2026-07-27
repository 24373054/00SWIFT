import pytest

from production.payment_aggregate import PaymentAggregate
from production.runtime import ProductionConflict


def test_aggregate_commands_require_expected_version_and_guard_close(db):
    from production.models import ProductionPaymentOrder

    order = ProductionPaymentOrder(
        order_id="agg-1", uetr="123e4567-e89b-42d3-a456-426614174000", instruction_id="i1", tenant_id="tenant:P1", initiator_participant="P1", corridor="CN-HK", debtor_party_ref="d", debtor_account_ref="da", creditor_party_ref="c", creditor_account_ref="ca", amount_minor=100, currency="CNY", settlement_currency="CNY", purpose_code="TRADE", payload="{}", payload_hash="0" * 64, orchestration_state="CONTROL_CHECKS", completion_profile_id="cmp", projection_rule_version="v1", version=1,
    )
    db.add(order)
    db.commit()
    aggregate = PaymentAggregate(db, "agg-1")
    with pytest.raises(ProductionConflict, match="version"):
        aggregate.authorize(99)
    aggregate.authorize(1)
    with pytest.raises(ProductionConflict, match="credit"):
        aggregate.close(2)
