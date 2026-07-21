"""API-level tests for the next-generation platform."""

from __future__ import annotations

import uuid


def _payload():
    return {
        "header": {
            "biz_msg_id": "BIZ-1",
            "message_definition": "pacs.008",
            "business_service": "swift.cbprplus.03",
            "sender": "AAAAJPJT",
            "receiver": "BBBBUS33",
        },
        "document": {
            "message_id": "MSG-1",
            "uetr": str(uuid.uuid4()),
            "amount": "100.00",
            "currency": "CNY",
            "debtor": {"address": {"town": "Tokyo", "country": "JP"}},
            "creditor": {"address": {"town": "Shanghai", "country": "CN"}},
        },
    }


def test_list_profiles(client):
    response = client.get("/nextgen/v1/standards/profiles")
    assert response.status_code == 200
    assert {item["key"] for item in response.json()["profiles"]} >= {
        "iso20022-base:2026",
        "cbpr-plus:sr2026",
        "cips:2026",
    }


def test_validate_sr2026_message(client):
    response = client.post(
        "/nextgen/v1/standards/validate",
        json={
            "profile": "cbpr-plus:sr2026",
            "message_type": "pacs.008",
            "payload": _payload(),
        },
    )
    assert response.status_code == 200
    assert response.json() == {"valid": True, "findings": []}


def test_outbox_is_idempotent(client):
    request = {
        "topic": "payment.accepted",
        "aggregate_id": "uetr-1",
        "payload": {"amount": 100},
    }
    headers = {"Idempotency-Key": "api-idempotency-key"}
    first = client.post("/nextgen/v1/runtime/outbox", json=request, headers=headers)
    second = client.post("/nextgen/v1/runtime/outbox", json=request, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["event_id"] == second.json()["event_id"]
