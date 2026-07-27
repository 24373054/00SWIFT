import datetime as dt

import pytest

from production.models import ProductionPaymentOrder
from production.timer_service import TimerService


def test_timer_types_are_unique_and_due_claim_is_atomic(db):
    order = ProductionPaymentOrder(order_id="timer-1", uetr="b23e4567-e89b-42d3-a456-426614174000", instruction_id="i1", end_to_end_id="e1", transaction_id="t1", tenant_id="tenant:P1", initiator_participant="P1", corridor="CN-HK", debtor_party_ref="d", debtor_account_ref="da", creditor_party_ref="c", creditor_account_ref="ca", amount_minor=100, currency="CNY", settlement_currency="CNY", purpose_code="TRADE", payload="{}", payload_hash="0" * 64, orchestration_state="CONTROL_CHECKS", completion_profile_id="cmp", projection_rule_version="v1")
    db.add(order)
    db.commit()
    service = TimerService(db)
    timer = service.schedule("timer-1", "settlement", dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1))
    assert service.schedule("timer-1", "settlement", dt.datetime.now(dt.UTC)) is timer
    assert service.claim_due()[0].state == "FIRED"
    with pytest.raises(ValueError, match="unsupported"):
        service.schedule("timer-1", "unknown", dt.datetime.now(dt.UTC))
