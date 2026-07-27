import pytest

from production.models import ProductionPaymentOrder
from production.return_service import ReturnService
from production.runtime import ProductionConflict


def _order():
    return ProductionPaymentOrder(order_id="ret-1", uetr="a23e4567-e89b-42d3-a456-426614174000", instruction_id="i1", end_to_end_id="e1", transaction_id="t1", tenant_id="tenant:P1", initiator_participant="P1", corridor="CN-HK", debtor_party_ref="d", debtor_account_ref="da", creditor_party_ref="c", creditor_account_ref="ca", amount_minor=10000, currency="CNY", settlement_currency="CNY", purpose_code="TRADE", payload="{}", payload_hash="0" * 64, orchestration_state="OPERATIONALLY_CLOSED", customer_outcome="COMPLETED", completion_profile_id="cmp", projection_rule_version="v1")


def test_return_sequence_and_over_return_are_atomic(db):
    db.add(_order())
    db.commit()
    service = ReturnService(db)
    first, leg = service.create_pending("ret-1", "60.00", "partial")
    assert first.return_sequence == 1 and first.return_leg_id == leg.leg_id
    with pytest.raises(ProductionConflict, match="exceeds"):
        service.create_pending("ret-1", "50.00", "over")
    second, _ = service.create_pending("ret-1", "40.00", "partial-2")
    assert second.return_sequence == 2
