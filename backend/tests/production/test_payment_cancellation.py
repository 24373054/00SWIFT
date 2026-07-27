import pytest

from production.cancellation_service import CancellationService
from production.models import (
    ProductionCancellationRequest,
    ProductionFundingReservation,
    ProductionPaymentOrder,
)
from production.runtime import ProductionConflict


def _order():
    return ProductionPaymentOrder(
        order_id="cancel-1", uetr="823e4567-e89b-42d3-a456-426614174000", instruction_id="i1", end_to_end_id="e1", transaction_id="t1", tenant_id="tenant:P1", initiator_participant="P1", corridor="CN-HK", debtor_party_ref="d", debtor_account_ref="da", creditor_party_ref="c", creditor_account_ref="ca", amount_minor=100, currency="CNY", settlement_currency="CNY", purpose_code="TRADE", payload="{}", payload_hash="0" * 64, orchestration_state="RESERVATION_PENDING", completion_profile_id="cmp", projection_rule_version="v1", version=1,
    )


def test_cancel_accept_releases_reservation_and_closes_unsuccessfully(db):
    db.add_all([_order(), ProductionCancellationRequest(cancellation_request_id="can-1", order_id="cancel-1", reason="duplicate", idempotency_context="ctx-1"), ProductionFundingReservation(reservation_id="res-1", reservation_intent_id="intent-1", order_id="cancel-1", funding_reference="P1:CNY", currency="CNY", amount_minor=100, state="RESERVED")])
    db.commit()
    request = CancellationService(db).transition("can-1", "VALIDATING")
    assert request.state == "VALIDATING"
    request = CancellationService(db).accept("can-1", evidence={"external_reference": "ext-1"})
    assert request.state == "ACCEPTED"
    assert db.query(ProductionFundingReservation).filter_by(reservation_id="res-1").one().state == "RELEASED"
    assert db.query(ProductionPaymentOrder).filter_by(order_id="cancel-1").one().orchestration_state == "EXECUTION_CANCELLED"
    with pytest.raises(ProductionConflict, match="invalid"):
        CancellationService(db).transition("can-1", "SENT")
