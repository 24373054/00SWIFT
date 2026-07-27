"""Contract tests for the production payment-domain boundary."""

from __future__ import annotations


def _headers(key: str) -> dict[str, str]:
    return {"X-Participant-ID": "SANDBOX-ORIGIN", "Idempotency-Key": key}


def _payment() -> dict:
    return {
        "instruction_id": "UI-TEST-001",
        "message_type": "pacs.008",
        "uetr": "4f7b0b2d-5ef4-4a7b-a8b8-4a5d1e8f4a12",
        "corridor": "CN-HK",
        "debtor": {"party_id": "DEBTOR-001", "account_id": "CNY-001"},
        "creditor": {"party_id": "CREDITOR-001", "account_id": "CNY-002"},
        "instructed_amount": {"amount": "100.00", "currency": "CNY"},
        "settlement_currency": "CNY",
        "purpose": {"code": "TRADE"},
    }


def test_production_payment_is_idempotent_and_worker_completes(client):
    first = client.post("/production/v1/payments", json=_payment(), headers=_headers("prod-1"))
    second = client.post("/production/v1/payments", json=_payment(), headers=_headers("prod-1"))
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["payment_id"] == second.json()["payment_id"]

    for _ in range(8):
        client.post("/production/v1/worker/run", headers={"X-Participant-ID": "SANDBOX-ORIGIN"})
    item = client.get("/production/v1/payments", headers={"X-Participant-ID": "SANDBOX-ORIGIN"}).json()["items"][0]
    assert item["uetr"] == _payment()["uetr"]
    assert item["fact_summary"]["facts"]["beneficiary"]["latest"]["state"] == "UNKNOWN"


def test_production_standards_validation_records_evidence(client):
    response = client.post(
        "/production/v1/standards/validate",
        json={"profile": "iso20022-base:2026", "message_type": "pacs.008", "payload": {"header": {}, "document": {}}},
        headers=_headers("std-1"),
    )
    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert response.json()["evidence_id"].startswith("evd_")
