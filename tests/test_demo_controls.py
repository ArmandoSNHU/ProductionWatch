"""Failure injection: authorization, valid modes, effects and recovery."""
import time

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_admin_routes_reject_missing_token(client):
    assert client.post("/admin/demo/failure", json={"mode": "error"}).status_code == 401


def test_admin_routes_reject_wrong_token(client):
    response = client.post("/admin/demo/failure", json={"mode": "error"},
                           headers={"X-Demo-Token": "wrong"})
    assert response.status_code == 401


def test_admin_routes_disabled_without_demo_mode(settings, auth):
    off = Settings(**{**settings.__dict__, "demo_mode": False})
    with TestClient(create_app(off)) as c:
        response = c.post("/admin/demo/failure", json={"mode": "error"}, headers=auth)
    assert response.status_code == 403


def test_admin_routes_disabled_without_token_configured(settings, auth):
    no_token = Settings(**{**settings.__dict__, "demo_token": ""})
    with TestClient(create_app(no_token)) as c:
        response = c.get("/admin/demo/status", headers=auth)
    assert response.status_code == 503


def test_invalid_failure_mode_is_rejected(client, auth):
    response = client.post("/admin/demo/failure", json={"mode": "drop_database"}, headers=auth)
    assert response.status_code == 422


def test_error_mode_returns_500_and_reset_restores(client, auth):
    assert client.post("/admin/demo/failure", json={"mode": "error"}, headers=auth).status_code == 200
    failing = client.get("/accounts")
    assert failing.status_code == 500
    assert "Injected failure" in failing.json()["detail"]
    # Liveness stays green: the process is up even though requests fail.
    assert client.get("/health").status_code == 200

    status = client.post("/admin/demo/reset", headers=auth).json()
    assert status["failure_mode"] == "none"
    assert client.get("/accounts").status_code == 200


def test_latency_mode_slows_account_requests(client, auth):
    client.post("/admin/demo/failure", json={"mode": "latency"}, headers=auth)
    started = time.perf_counter()
    assert client.get("/accounts").status_code == 200
    assert time.perf_counter() - started >= 0.2
    client.post("/admin/demo/reset", headers=auth)


def test_dependency_outage_fails_readiness_and_transactions(client, auth):
    client.post("/admin/demo/failure", json={"mode": "dependency_outage"}, headers=auth)

    ready = client.get("/ready")
    assert ready.status_code == 503
    assert ready.json()["checks"]["ledger-service"] == "unavailable"
    assert client.get("/accounts/1/transactions").status_code == 503
    # Account reads do not use the ledger, so they keep working: partial outage.
    assert client.get("/accounts/1").status_code == 200

    client.post("/admin/demo/reset", headers=auth)
    assert client.get("/ready").status_code == 200


def test_status_reports_current_mode(client, auth):
    client.post("/admin/demo/failure", json={"mode": "latency"}, headers=auth)
    status = client.get("/admin/demo/status", headers=auth).json()
    assert status == {**status, "demo_mode": True, "failure_mode": "latency", "dependency_up": True}
    client.post("/admin/demo/reset", headers=auth)
