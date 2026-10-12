"""Probes, synthetic account data, request IDs and error bodies."""
from app.seed import SEED_ACCOUNTS


def test_health_is_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "productionwatch-api"


def test_ready_reports_each_check(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": "ok", "ledger-service": "ok"},
    }


def test_accounts_are_seeded_with_synthetic_data(client):
    accounts = client.get("/accounts").json()
    assert len(accounts) == len(SEED_ACCOUNTS)
    for account in accounts:
        assert account["reference"].startswith("DEMO-")
        assert account["holder_alias"].startswith("Test Member")


def test_get_single_account(client):
    response = client.get("/accounts/1")
    assert response.status_code == 200
    assert response.json()["reference"] == "DEMO-CHK-0001"


def test_unknown_account_returns_404_with_request_id(client):
    response = client.get("/accounts/9999")
    assert response.status_code == 404
    body = response.json()
    assert "not found" in body["detail"]
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_transactions_are_newest_first_and_limited(client):
    response = client.get("/accounts/1/transactions", params={"limit": 5})
    assert response.status_code == 200
    transactions = response.json()
    assert len(transactions) == 5
    dates = [t["posted_at"] for t in transactions]
    assert dates == sorted(dates, reverse=True)
    assert all("(synthetic)" in t["description"] for t in transactions)


def test_incoming_request_id_is_echoed(client):
    response = client.get("/health", headers={"X-Request-ID": "trace-abc-123"})
    assert response.headers["X-Request-ID"] == "trace-abc-123"


def test_seed_is_idempotent(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    for _ in range(2):
        with TestClient(create_app(settings)) as c:
            assert len(c.get("/accounts").json()) == len(SEED_ACCOUNTS)
