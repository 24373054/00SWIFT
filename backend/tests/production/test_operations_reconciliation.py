from production.models import ProductionPaymentOrder
from production.operations import reconciliation_report


def _completed_order(order_id: str, uetr: str) -> ProductionPaymentOrder:
    return ProductionPaymentOrder(
        order_id=order_id,
        uetr=uetr,
        instruction_id=f"instruction-{order_id}",
        end_to_end_id=f"e2e-{order_id}",
        transaction_id=f"transaction-{order_id}",
        tenant_id="tenant:P1",
        initiator_participant="P1",
        corridor="CN-HK",
        debtor_party_ref="debtor",
        debtor_account_ref="debtor-account",
        creditor_party_ref="creditor",
        creditor_account_ref="creditor-account",
        amount_minor=100,
        currency="CNY",
        settlement_currency="CNY",
        purpose_code="TRADE",
        payload="{}",
        payload_hash="0" * 64,
        orchestration_state="OPERATIONALLY_CLOSED",
        customer_outcome="COMPLETED",
        completion_profile_id="completion-v1",
        projection_rule_version="v1",
    )


def test_reconciliation_checks_every_completed_order_without_journals(db):
    db.add_all(
        [
            _completed_order("recon-order-1", "103e4567-e89b-42d3-a456-426614174000"),
            _completed_order("recon-order-2", "203e4567-e89b-42d3-a456-426614174000"),
        ]
    )
    db.commit()

    report = reconciliation_report(db, record_audit=False)

    missing = {
        item["order_id"]
        for item in report["breaks"]
        if item["reason"] == "completed order has no matched reconciliation"
    }
    assert missing == {"recon-order-1", "recon-order-2"}
