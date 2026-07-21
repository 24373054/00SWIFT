"""Tests for payment lifecycle, CIPS settlement and two-tier e-CNY operations."""

from __future__ import annotations

import json
import uuid

import pytest

from nextgen.cips import CipsService, EcnyOperatorService
from nextgen.models import CipsAccount, FieldLineage, TransactionCopy
from nextgen.payments import PaymentLifecycleError, PaymentService


def _uetr() -> str:
    return str(uuid.uuid4())


def _message(uetr: str) -> dict:
    return {
        "header": {
            "biz_msg_id": "BATCH2-1",
            "message_definition": "pacs.008",
            "business_service": "swift.cbprplus.03",
            "sender": "AAAAJPJT",
            "receiver": "BBBBUS33",
        },
        "document": {
            "message_id": "MSG-1",
            "uetr": uetr,
            "amount": "100.00",
            "currency": "CNY",
            "debtor": {"address": {"town": "Tokyo", "country": "JP"}},
            "creditor": {"address": {"town": "Shanghai", "country": "CN"}},
        },
    }


def test_payment_lifecycle_and_timeline(db):
    service = PaymentService(db)
    uetr = _uetr()
    payment = service.create(uetr)
    payment = service.transition(uetr, payment.version, "VALIDATED")
    payment = service.transition(uetr, payment.version, "IN_PROCESS")
    payment = service.transition(uetr, payment.version, "SETTLED")
    assert payment.status == "SETTLED"
    assert [event.status for event in service.timeline(uetr)] == [
        "RECEIVED",
        "VALIDATED",
        "IN_PROCESS",
        "SETTLED",
    ]


def test_illegal_lifecycle_transition_is_rejected(db):
    service = PaymentService(db)
    payment = service.create(_uetr())
    with pytest.raises(PaymentLifecycleError, match="Illegal transition"):
        service.transition(payment.uetr, payment.version, "SETTLED")


def test_cover_payment_must_inherit_uetr(db):
    with pytest.raises(PaymentLifecycleError, match="inherit"):
        PaymentService(db).create(_uetr(), scenario="COV", original_uetr=_uetr())


def test_transaction_copy_hash_chain_and_lineage(db):
    service = PaymentService(db)
    uetr = _uetr()
    service.create(uetr)
    first = service.append_transaction_copy(
        uetr,
        "m1",
        "pacs.008",
        _message(uetr),
        "AAAAJPJT",
    )
    second_payload = _message(uetr)
    second_payload["document"]["amount"] = "99.00"
    second = service.append_transaction_copy(
        uetr,
        "m2",
        "pacs.002",
        second_payload,
        "BBBBUS33",
        "status response",
    )
    assert second.previous_hash == first.payload_hash
    assert service.verify_copy_chain(uetr)
    assert db.query(FieldLineage).filter_by(uetr=uetr).count() > 10

    copy = db.query(TransactionCopy).filter_by(message_id="m1").one()
    copy.payload = json.dumps({"tampered": True})
    assert not service.verify_copy_chain(uetr)


def test_case_management_and_sla(db):
    service = PaymentService(db)
    uetr = _uetr()
    service.create(uetr)
    payment_case = service.open_case(uetr, "beneficiary_not_credited", "BANK-A", {})
    payment_case = service.update_case(payment_case.case_id, "IN_REVIEW", owner="BANK-B")
    payment_case = service.update_case(payment_case.case_id, "RESOLVED", details={"result": "paid"})
    payment_case = service.update_case(payment_case.case_id, "CLOSED")
    assert payment_case.status == "CLOSED"
    assert payment_case.owner == "BANK-B"


def test_data_quality_scores_and_integrity(db):
    service = PaymentService(db)
    uetr = _uetr()
    service.create(uetr)
    service.append_transaction_copy(uetr, "quality-1", "pacs.008", _message(uetr), "AAAAJPJT")
    metric = service.assess_quality(
        uetr,
        "cbpr-plus:sr2026",
        "pacs.008",
        _message(uetr),
    )
    assert metric.completeness == 100.0
    assert metric.validity == 100.0
    assert metric.consistency == 100.0
    assert metric.integrity == 100.0


def _participants(service: CipsService):
    service.register_participant(
        "CIPS-A",
        "Bank A",
        "direct",
        "CN",
        bic="AAAACNSH",
        capabilities=["RTGS", "DNS"],
    )
    service.register_participant(
        "CIPS-B",
        "Bank B",
        "direct",
        "HK",
        bic="BBBBHKHH",
        capabilities=["RTGS", "DNS"],
    )


def test_cips_route_ranking(db):
    service = CipsService(db)
    _participants(service)
    routes = service.route_candidates("HK", "RTGS", "BBBBHKHH")
    assert routes[0]["participant_id"] == "CIPS-B"
    assert routes[0]["score"] == 180


def test_rtgs_queues_then_releases_without_overdraft(db):
    service = CipsService(db)
    _participants(service)
    service.open_account("CIPS-A", initial_balance=100)
    service.open_account("CIPS-B", initial_balance=0)
    settlement = service.submit_settlement(
        _uetr(),
        "RTGS",
        "CIPS-A",
        "CIPS-B",
        150,
    )
    assert settlement.status == "QUEUED"
    debtor = db.query(CipsAccount).filter_by(participant_id="CIPS-A").one()
    debtor.balance += 100
    assert service.release_rtgs_queue() == [settlement.settlement_id]
    assert debtor.balance == 50
    creditor = db.query(CipsAccount).filter_by(participant_id="CIPS-B").one()
    assert creditor.balance == 150


def test_dns_batch_applies_net_positions_atomically(db):
    service = CipsService(db)
    _participants(service)
    service.open_account("CIPS-A", initial_balance=500)
    service.open_account("CIPS-B", initial_balance=500)
    service.submit_settlement(_uetr(), "DNS", "CIPS-A", "CIPS-B", 200, batch_id="D1")
    service.submit_settlement(_uetr(), "DNS", "CIPS-B", "CIPS-A", 50, batch_id="D1")
    net = service.settle_dns_batch("D1")
    assert net == {"CIPS-A": -150, "CIPS-B": 150}
    assert db.query(CipsAccount).filter_by(participant_id="CIPS-A").one().balance == 350
    assert db.query(CipsAccount).filter_by(participant_id="CIPS-B").one().balance == 650


def test_cips_prevalidation_uses_independent_profile(db):
    service = CipsService(db)
    payload = _message(_uetr())
    payload["document"]["currency"] = "USD"
    result = service.prevalidate("pacs.008", payload)
    assert not result["valid"]
    assert "CIPS-CNY-001" in {item["rule_id"] for item in result["findings"]}


def test_two_tier_operator_issuance_redeem_and_reconciliation(db):
    service = EcnyOperatorService(db)
    service.register("OP-A", "Operator A", issuance_limit=1000, reserve_amount=1000)
    issue = service.issue("OP-A", 600)
    assert issue.status == "settled"
    assert service.reconcile("OP-A")["reconciled"]
    redeem = service.redeem("OP-A", 200)
    assert redeem.status == "settled"
    reconciliation = service.reconcile("OP-A")
    assert reconciliation["issued_amount"] == 400
    assert reconciliation["ledger_balance"] == 400
    assert reconciliation["within_limit"]


def test_operator_cannot_exceed_issuance_limit(db):
    service = EcnyOperatorService(db)
    service.register("OP-A", "Operator A", issuance_limit=100)
    with pytest.raises(PaymentLifecycleError, match="limit"):
        service.issue("OP-A", 101)
