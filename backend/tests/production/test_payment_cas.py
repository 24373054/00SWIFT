import pytest

from production.models import ProductionPaymentOrder
from production.runtime import ProductionConflict
from production.service import set_order_state


def _order():
    return ProductionPaymentOrder(
        order_id="cas-1", uetr="323e4567-e89b-42d3-a456-426614174000", instruction_id="i1", tenant_id="tenant:P1", initiator_participant="P1", corridor="CN-HK", debtor_party_ref="d", debtor_account_ref="da", creditor_party_ref="c", creditor_account_ref="ca", amount_minor=100, currency="CNY", settlement_currency="CNY", purpose_code="TRADE", payload="{}", payload_hash="0" * 64, orchestration_state="CONTROL_CHECKS", completion_profile_id="cmp", projection_rule_version="v1", version=1,
    )


def test_stale_expected_version_cannot_overwrite_new_state(db):
    db.add(_order())
    db.commit()
    set_order_state(db, "cas-1", "RESERVATION_PENDING", expected_version=1)
    with pytest.raises(ProductionConflict, match="version"):
        set_order_state(db, "cas-1", "SUSPENDED", expected_version=1)


def test_duplicate_and_out_of_order_state_updates_are_rejected(db):
    db.add(_order())
    db.commit()
    set_order_state(db, "cas-1", "RESERVATION_PENDING", expected_version=1)
    with pytest.raises(ProductionConflict, match="Invalid payment transition"):
        set_order_state(db, "cas-1", "CUSTOMER_COMPLETED", expected_version=2)
    with pytest.raises(ProductionConflict, match="Invalid payment transition"):
        set_order_state(db, "cas-1", "CONTROL_CHECKS", expected_version=2)
