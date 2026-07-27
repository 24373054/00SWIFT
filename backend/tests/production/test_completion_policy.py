import json

from production.completion_policy import CompletionPolicyEvaluator
from production.models import (
    ProductionCompletionProfile,
    ProductionPaymentFact,
    ProductionPaymentOrder,
    ProductionReconciliationRun,
    ProductionSettlementLeg,
)


def test_completion_policy_requires_facts_finality_reconciliation_and_no_reservations(db):
    order = ProductionPaymentOrder(order_id="cmp-1", uetr="c23e4567-e89b-42d3-a456-426614174000", instruction_id="i1", end_to_end_id="e1", transaction_id="t1", tenant_id="tenant:P1", initiator_participant="P1", corridor="CN-HK", debtor_party_ref="d", debtor_account_ref="da", creditor_party_ref="c", creditor_account_ref="ca", amount_minor=100, currency="CNY", settlement_currency="CNY", purpose_code="TRADE", payload="{}", payload_hash="0" * 64, orchestration_state="VALUE_SETTLEMENT", completion_profile_id="cmp", projection_rule_version="v1")
    profile = ProductionCompletionProfile(profile_id="cmp", corridor="CN-HK", required_messages=json.dumps(["payment-message"]), required_funding=json.dumps(["debit"]), required_fx="[]", required_settlement=json.dumps(["PAYMENT_VALUE"]), required_credits=json.dumps(["beneficiary"]), projection_rule_version="v1")
    db.add_all([order, profile, ProductionPaymentFact(fact_id="f1", order_id="cmp-1", fact_type="MESSAGE", state="DELIVERED", reference="payment-message", payload="{}"), ProductionPaymentFact(fact_id="f2", order_id="cmp-1", fact_type="FUNDING", state="CONSUMED", reference="debit", payload="{}"), ProductionPaymentFact(fact_id="f3", order_id="cmp-1", fact_type="SETTLEMENT", state="FINAL", reference="PAYMENT_VALUE", payload="{}"), ProductionPaymentFact(fact_id="f4", order_id="cmp-1", fact_type="BENEFICIARY", state="CREDITED", reference="beneficiary", payload="{}"), ProductionSettlementLeg(leg_id="leg-1", order_id="cmp-1", leg_role="PAYMENT_VALUE", connector="test", currency="CNY", amount_minor=100, state="FINAL", finality_profile_id="finality"), ProductionReconciliationRun(run_id="recon-1", order_id="cmp-1", state="MATCHED", payment_hash="0" * 64)])
    db.commit()
    assert CompletionPolicyEvaluator(db).evaluate(order)["allowed"] is True
