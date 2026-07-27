from __future__ import annotations


def test_production_health_reports_each_dependency_without_claiming_ready(client):
    response = client.get("/production/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert set(payload["dependencies"]) == {
        "database",
        "broker",
        "hsm",
        "signature_verifier",
        "connector",
        "standards_artifact",
        "worker_heartbeat",
    }
    assert payload["dependencies"]["connector"]["status"] == "simulation"


def test_readiness_is_not_200_when_simulation_or_dependency_missing(client):
    response = client.get("/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["ready"] is False
    assert payload["dependencies"]["hsm"]["status"] == "unconfigured"
    assert payload["dependencies"]["worker_heartbeat"]["status"] == "stale_or_missing"
