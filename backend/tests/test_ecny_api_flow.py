"""End-to-end e-CNY sandbox flow through the public/admin API surfaces."""

from version import __version__

ADMIN = {"X-Admin-Token": "test-admin-token"}


def test_full_ecny_flow(client):
    operator = client.post(
        "/api/ecny/provision-operator",
        headers=ADMIN,
        params={"account_id": "acct-op-api", "owner_ref": "ICBC", "currency": "CNY"},
    )
    assert operator.status_code == 200, operator.text

    def open_wallet(name):
        response = client.post(
            "/ecny/v1/wallets",
            headers=ADMIN,
            json={
                "tier": 1,
                "operator_account_id": "acct-op-api",
                "holder_name": name,
                "holder_id_type": "passport",
                "holder_id_hash": f"hash-{name}",
            },
        )
        assert response.status_code == 200, response.text
        return response.json()

    alice = open_wallet("Alice")
    bob = open_wallet("Bob")

    minted = client.post(
        "/ecny/v1/issuance",
        headers=ADMIN,
        json={"operator_account_id": "acct-op-api", "amount_fen": 1_000_000, "action": "mint"},
    )
    assert minted.status_code == 200, minted.text

    for wallet, amount in ((alice, 200_000), (bob, 50_000)):
        issued = client.post(
            "/ecny/v1/issuance",
            headers=ADMIN,
            json={
                "operator_account_id": "acct-op-api",
                "wallet_id": wallet["wallet_id"],
                "amount_fen": amount,
                "action": "issue_to_wallet",
            },
        )
        assert issued.status_code == 200, issued.text

    transferred = client.post(
        "/ecny/v1/transfers",
        headers=ADMIN,
        json={
            "from_wallet_id": alice["wallet_id"],
            "to_wallet_id": bob["wallet_id"],
            "amount_fen": 10_000,
            "memo": {"purpose": "integration-test"},
        },
    )
    assert transferred.status_code == 200, transferred.text

    alice_read = client.get(f"/ecny/v1/wallets/{alice['wallet_id']}", headers=ADMIN)
    bob_read = client.get(f"/ecny/v1/wallets/{bob['wallet_id']}", headers=ADMIN)
    assert alice_read.json()["balance"] == 190_000
    assert bob_read.json()["balance"] == 60_000

    seeded = client.post(
        "/api/ecny/seed-foreign-account",
        headers=ADMIN,
        params={
            "account_id": "acct-hkd-api",
            "owner_ref": "HKMA",
            "currency": "HKD",
            "balance_fen": 0,
        },
    )
    assert seeded.status_code == 200, seeded.text

    bridged = client.post(
        "/ecny/v1/cross-border",
        headers=ADMIN,
        json={
            "from_wallet_id": alice["wallet_id"],
            "to_account_id": "acct-hkd-api",
            "amount_fen": 10_000,
            "target_currency": "hkd",
            "counterparty": "HKMA",
        },
    )
    assert bridged.status_code == 200, bridged.text
    assert bridged.json()["status"] == "settled"
    assert bridged.json()["to_amount"] == 10_800

    tracked = client.get(f"/ecny/v1/cross-border/{bridged.json()['uetr']}", headers=ADMIN)
    assert tracked.status_code == 200
    assert client.get("/ecny/v1/bridge/channels", headers=ADMIN).status_code == 200
    assert client.get("/ecny/v1/compliance/reports", headers=ADMIN).status_code == 200
    assert client.get("/ecny/v1/ledger/transactions?limit=10", headers=ADMIN).status_code == 200
    assert client.get("/api/ecny/stats", headers=ADMIN).status_code == 200
    assert client.get("/api/ecny/wallets", headers=ADMIN).status_code == 200
    assert client.get("/api/ecny/ledger-accounts", headers=ADMIN).status_code == 200


def test_operational_endpoints(client):
    assert client.get("/health").json()["version"] == __version__
    assert client.get("/ready").json()["status"] == "ready"
    catalogue = client.get("/api/catalogue", headers=ADMIN)
    assert catalogue.status_code == 200
