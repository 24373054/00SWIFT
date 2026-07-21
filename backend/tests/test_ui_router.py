"""API coverage for the institutional frontend contract."""

from __future__ import annotations


def headers(role: str = "executive_viewer") -> dict[str, str]:
    return {
        "X-Admin-Token": "test-admin-token",
        "X-User-Role": role,
        "X-User-Subject": "test-user",
    }


def test_ui_bootstrap_is_backend_authoritative(client):
    response = client.get("/nextgen/v1/ui/bootstrap", headers=headers())
    assert response.status_code == 200
    body = response.json()
    assert body["product"]["name"] == "Cross-Border Payment Infrastructure Lab"
    assert body["identity"]["role"] == "executive_viewer"
    assert body["decision"]["result"] == "allow"
    admin = next(item for item in body["workspaces"] if item["id"] == "administration")
    assert admin["enabled"] is False


def test_platform_admin_receives_all_workspaces(client):
    response = client.get("/nextgen/v1/ui/bootstrap", headers=headers("platform_administrator"))
    assert response.status_code == 200
    assert all(item["enabled"] for item in response.json()["workspaces"])


def test_ui_abac_denies_amount_above_role_limit(client):
    response = client.post(
        "/nextgen/v1/ui/authorize",
        headers=headers("executive_viewer"),
        json={
            "action": "settlement.release",
            "resource": "workspace.settlement.payment",
            "amount": 30_000_000,
            "jurisdiction": "CN",
            "purpose": "trade",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "deny"
    assert "amount exceeds policy" in body["reasons"]


def test_ui_abac_requires_dual_approval_for_large_mutation(client):
    response = client.post(
        "/nextgen/v1/ui/authorize",
        headers=headers("settlement_operator"),
        json={
            "action": "settlement.release",
            "resource": "workspace.settlement.payment",
            "amount": 20_000_000,
            "jurisdiction": "HK",
            "purpose": "trade",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "allow"
    assert "dual_approval" in body["obligations"]
    assert body["decision_id"].startswith("decision-")


def test_command_center_contract_contains_eight_visualisation_models(client):
    response = client.get("/nextgen/v1/ui/command-center", headers=headers())
    assert response.status_code == 200
    body = response.json()
    for key in (
        "corridors",
        "lifecycle",
        "liquidity",
        "dns",
        "pvp",
        "policy_matrix",
        "iso_tree",
        "message_diff",
    ):
        assert body[key]
    assert body["authorization"]["result"] == "allow"
    assert body["data_mode"] in {"live", "representative"}
