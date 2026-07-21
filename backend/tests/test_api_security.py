"""API-level authentication and sensitive-data handling tests."""

import base64

from database import ApiRequest, AppCredential, OAuthToken, SessionLocal

ADMIN = {"X-Admin-Token": "test-admin-token"}


def _create_credential(client):
    response = client.post(
        "/api/credentials",
        headers=ADMIN,
        json={"app_name": "integration-test", "allowed_scopes": "ecny.ledger ecny.wallet"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_credentials_disclose_secret_once_and_store_hash(client):
    created = _create_credential(client)
    assert created["consumer_secret"]

    listed = client.get("/api/credentials", headers=ADMIN)
    assert listed.status_code == 200
    assert "consumer_secret" not in listed.json()[0]

    db = SessionLocal()
    try:
        row = db.query(AppCredential).filter(AppCredential.id == created["id"]).one()
        assert row.consumer_secret.startswith("pbkdf2_sha256$")
        assert created["consumer_secret"] not in row.consumer_secret
    finally:
        db.close()


def test_dev_token_is_hashed_at_rest_and_authorizes_scope(client):
    created = _create_credential(client)
    signed = client.post(
        "/api/dev/sign",
        headers=ADMIN,
        json={
            "consumer_key": created["consumer_key"],
            "body": "",
            "audience": "testserver/ecny/v1/ledger/transactions",
            "scope": "ecny.ledger",
        },
    )
    assert signed.status_code == 200, signed.text
    raw_token = signed.json()["access_token"]

    db = SessionLocal()
    try:
        row = db.query(OAuthToken).one()
        assert row.access_token != raw_token
        assert len(row.access_token) == 64
    finally:
        db.close()

    response = client.get(
        "/ecny/v1/ledger/transactions",
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert response.status_code == 200, response.text


def test_invalid_admin_token_is_rejected(client):
    response = client.get("/api/credentials", headers={"X-Admin-Token": "wrong"})
    assert response.status_code == 401
    response = client.get("/ecny/v1/ledger/transactions", headers={"X-Admin-Token": "wrong"})
    assert response.status_code == 401


def test_oauth_assertion_is_redacted_from_audit(client):
    basic = base64.b64encode(b"unknown:unknown").decode()
    response = client.post(
        "/oauth2/token",
        headers={"Authorization": f"Basic {basic}"},
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": "super-secret-assertion",
        },
    )
    assert response.status_code == 401
    db = SessionLocal()
    try:
        row = db.query(ApiRequest).order_by(ApiRequest.id.desc()).first()
        assert row is not None
        assert "super-secret-assertion" not in row.request_body
    finally:
        db.close()
