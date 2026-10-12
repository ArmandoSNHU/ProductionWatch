"""Metrics endpoint, structured logs and the ops summary."""
import re


def _metric_value(text: str, name: str, labels: dict[str, str]) -> float:
    for line in text.splitlines():
        if not line.startswith(name + "{"):
            continue
        if all(f'{key}="{value}"' in line for key, value in labels.items()):
            return float(line.rsplit(" ", 1)[1])
    return 0.0


def test_metrics_endpoint_exposes_app_metrics(client):
    client.get("/accounts")
    response = client.get("/metrics")
    assert response.status_code == 200
    for name in ("pw_http_requests_total", "pw_http_request_duration_seconds_bucket",
                 "pw_http_requests_in_progress", "pw_demo_failure_mode", "pw_dependency_up"):
        assert name in response.text


def test_requests_counted_by_route_template_not_raw_path(client):
    client.get("/accounts/2")
    text = client.get("/metrics").text
    assert 'route="/accounts/{account_id}"' in text
    assert 'route="/accounts/2"' not in text


def test_metrics_scrapes_are_excluded_from_slis(client):
    client.get("/metrics")
    assert 'route="/metrics"' not in client.get("/metrics").text


def test_injected_errors_increment_error_counter(client, auth):
    labels = {"route": "/accounts", "status": "500"}
    before = _metric_value(client.get("/metrics").text, "pw_http_errors_total", labels)
    client.post("/admin/demo/failure", json={"mode": "error"}, headers=auth)
    for _ in range(3):
        client.get("/accounts")
    client.post("/admin/demo/reset", headers=auth)
    after = _metric_value(client.get("/metrics").text, "pw_http_errors_total", labels)
    assert after - before == 3


def test_failure_mode_gauge_tracks_active_mode(client, auth):
    client.post("/admin/demo/failure", json={"mode": "dependency_outage"}, headers=auth)
    text = client.get("/metrics").text
    assert _metric_value(text, "pw_demo_failure_mode", {"mode": "dependency_outage"}) == 1
    assert _metric_value(text, "pw_dependency_up", {"dependency": "ledger-service"}) == 0
    client.post("/admin/demo/reset", headers=auth)
    text = client.get("/metrics").text
    assert _metric_value(text, "pw_demo_failure_mode", {"mode": "none"}) == 1


def test_recent_logs_are_structured_and_token_free(client, auth):
    client.get("/accounts", headers={"X-Request-ID": "log-check-1"})
    logs = client.get("/ops/logs", headers=auth).json()
    entry = next(e for e in logs if e.get("request_id") == "log-check-1")
    for field in ("timestamp", "level", "request_id", "endpoint", "status", "duration_ms"):
        assert field in entry
    assert entry["endpoint"] == "/accounts"
    assert "test-token" not in client.get("/ops/logs?limit=500", headers=auth).text


def test_recent_logs_require_token(client):
    assert client.get("/ops/logs").status_code == 401


def test_summary_reports_error_rate(client, auth):
    client.get("/accounts")
    client.post("/admin/demo/failure", json={"mode": "error"}, headers=auth)
    client.get("/accounts")
    client.post("/admin/demo/reset", headers=auth)
    summary = client.get("/ops/summary").json()
    assert summary["errors_5xx"] >= 1
    assert summary["error_rate_pct"] > 0
    assert summary["failure_mode"] == "none"
    assert re.match(r"^\d+(\.\d+)?$", str(summary["p95_latency_ms"]))


def test_admin_calls_are_excluded_from_slis(client, auth):
    client.get("/admin/demo/status", headers=auth)
    assert 'route="/admin/demo/status"' not in client.get("/metrics").text
