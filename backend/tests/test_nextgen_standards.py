"""Regression tests for standards profiles and durable runtime primitives."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from nextgen.runtime import (
    IdempotencyConflict,
    IdempotencyService,
    OutboxService,
    WorkflowService,
)
from nextgen.standards import (
    build_iso20022_xml,
    classify_address,
    parse_iso20022_xml,
    run_conformance,
    validate_message,
)


def _message(address=None):
    return {
        "header": {
            "biz_msg_id": "B1",
            "message_definition": "pacs.008",
            "business_service": "swift.cbprplus.03",
            "sender": "AAAAJPJT",
            "receiver": "BBBBUS33",
        },
        "document": {
            "message_id": "M1",
            "uetr": str(uuid.uuid4()),
            "amount": "10.00",
            "currency": "CNY",
            "debtor": {"address": address or {"town": "Tokyo", "country": "JP"}},
            "creditor": {"address": address or {"town": "New York", "country": "US"}},
        },
    }


def test_sr2026_accepts_structured_address():
    assert validate_message("cbpr-plus:sr2026", "pacs.008", _message()) == []


def test_sr2026_rejects_unstructured_address():
    findings = validate_message(
        "cbpr-plus:sr2026",
        "pacs.008",
        _message({"address_lines": ["unstructured"]}),
    )
    assert {finding.rule_id for finding in findings} >= {
        "CBPR-ADDR-2026-D",
        "CBPR-ADDR-2026-C",
    }


def test_classify_hybrid_address():
    assert classify_address({"town": "Tokyo", "address_lines": ["1 Chiyoda"]}) == "hybrid"


def test_bah_definition_must_match_document():
    payload = _message()
    payload["header"]["message_definition"] = "pacs.009"
    assert "ISO-BAH-001" in {
        finding.rule_id for finding in validate_message("iso20022-base:2026", "pacs.008", payload)
    }


def test_cips_profile_requires_cny():
    payload = _message()
    payload["document"]["currency"] = "USD"
    assert "CIPS-CNY-001" in {
        finding.rule_id for finding in validate_message("cips:2026", "pacs.008", payload)
    }


def test_xml_roundtrip():
    xml = build_iso20022_xml("pacs.008", _message())
    parsed = parse_iso20022_xml(xml)
    assert parsed["message_type"] == "pacs.008"
    assert parsed["document"]["message_id"] == "M1"


def test_xml_rejects_dtd():
    with pytest.raises(ValueError, match="DTD"):
        parse_iso20022_xml("<!DOCTYPE x><x/>")


def test_conformance_runner():
    result = run_conformance(
        [
            {
                "name": "valid SR2026 transfer",
                "profile": "cbpr-plus:sr2026",
                "message_type": "pacs.008",
                "payload": _message(),
                "expected_valid": True,
            }
        ]
    )
    assert result["passed"] == 1
    assert result["failed"] == 0


def test_idempotency_replay(db: Session):
    service = IdempotencyService(db)
    record, replay = service.begin("same-key", {"amount": 1})
    assert not replay
    service.complete(record, 200, {"ok": True})
    db.commit()

    second, replay = service.begin("same-key", {"amount": 1})
    assert replay
    assert second.status == "completed"


def test_idempotency_conflict(db: Session):
    service = IdempotencyService(db)
    service.begin("same-key", {"amount": 1})
    db.commit()
    with pytest.raises(IdempotencyConflict):
        service.begin("same-key", {"amount": 2})


def test_outbox_lifecycle(db: Session):
    service = OutboxService(db)
    event = service.enqueue("payment.accepted", "uetr-1", {"amount": 1})
    db.commit()
    claimed = service.claim()
    assert claimed[0].event_id == event.event_id
    service.complete(claimed[0])
    db.commit()
    assert event.status == "published"


def test_outbox_dead_letter(db: Session):
    service = OutboxService(db)
    event = service.enqueue("payment.failed", "uetr-1", {})
    event.attempts = 5
    service.fail(event, "downstream unavailable", max_attempts=5)
    assert event.status == "dead_letter"


def test_workflow_optimistic_version(db: Session):
    service = WorkflowService(db)
    workflow = service.create("payment", "STARTED", {})
    db.commit()
    workflow = service.transition(workflow.workflow_id, 1, "DONE")
    assert workflow.version == 2
    with pytest.raises(ValueError, match="version conflict"):
        service.transition(workflow.workflow_id, 1, "INVALID")
