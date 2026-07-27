from __future__ import annotations


def _headers(key: str) -> dict[str, str]:
    return {"X-Participant-ID": "SANDBOX-ORIGIN", "Idempotency-Key": key}


def _payment() -> dict:
    return {
        "instruction_id": "IDEMPOTENCY-CONTRACT",
        "message_type": "pacs.008",
        "uetr": "123e4567-e89b-42d3-a456-426614174000",
        "corridor": "CN-HK",
        "debtor": {"party_id": "DEBTOR-001", "account_id": "CNY-001"},
        "creditor": {"party_id": "CREDITOR-001", "account_id": "CNY-002"},
        "instructed_amount": {"amount": "100.00", "currency": "CNY"},
        "settlement_currency": "CNY",
        "purpose": {"code": "TRADE"},
    }


def test_payment_post_same_key_same_body_replays_exact_response(client):
    headers = _headers("contract-1")
    first = client.post("/production/v1/payments", json=_payment(), headers=headers)
    replay = client.post("/production/v1/payments", json=_payment(), headers=headers)
    assert first.status_code == replay.status_code == 202
    assert first.json() == replay.json()


def test_payment_post_same_key_different_body_is_conflict(client):
    headers = _headers("contract-2")
    first = client.post("/production/v1/payments", json=_payment(), headers=headers)
    altered = _payment()
    altered["purpose"]["code"] = "SALARY"
    conflict = client.post("/production/v1/payments", json=altered, headers=headers)
    assert first.status_code == 202
    assert conflict.status_code == 409
