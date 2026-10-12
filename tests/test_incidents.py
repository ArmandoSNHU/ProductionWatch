"""Incident lifecycle and the full detect -> restore -> close recovery flow."""

NEW_INCIDENT = {
    "title": "Accounts API returning HTTP 500",
    "severity": "SEV2",
    "symptoms": "5xx error rate above 50% on /accounts",
    "impact": "Members cannot view account summaries",
}


def test_create_incident_requires_token(client):
    assert client.post("/incidents", json=NEW_INCIDENT).status_code == 401


def test_create_incident_starts_timeline_with_detection(client, auth):
    response = client.post("/incidents", json=NEW_INCIDENT, headers=auth)
    assert response.status_code == 201
    incident = response.json()
    assert incident["status"] == "open"
    assert incident["events"][0]["phase"] == "detection"


def test_invalid_severity_rejected(client, auth):
    bad = {**NEW_INCIDENT, "severity": "CRITICAL"}
    assert client.post("/incidents", json=bad, headers=auth).status_code == 422


def test_cannot_close_unresolved_incident(client, auth):
    incident_id = client.post("/incidents", json=NEW_INCIDENT, headers=auth).json()["id"]
    response = client.post(f"/incidents/{incident_id}/close",
                           json={"follow_up": "Add alert"}, headers=auth)
    assert response.status_code == 409


def test_missing_incident_returns_404(client):
    assert client.get("/incidents/404").status_code == 404


def test_full_recovery_flow(client, auth):
    # Detection: failure injected, users see 500s.
    client.post("/admin/demo/failure", json={"mode": "error"}, headers=auth)
    assert client.get("/accounts").status_code == 500

    incident_id = client.post("/incidents", json=NEW_INCIDENT, headers=auth).json()["id"]

    # Triage and mitigation notes on the timeline.
    client.post(f"/incidents/{incident_id}/events", headers=auth, json={
        "phase": "triage", "status": "investigating",
        "note": "Logs show injected application error on /accounts; health still 200",
    })
    client.post("/admin/demo/reset", headers=auth)
    client.post(f"/incidents/{incident_id}/events", headers=auth, json={
        "phase": "mitigation", "status": "mitigated",
        "note": "Disabled failing code path (demo reset)",
    })

    # Verify recovery before resolving.
    assert client.get("/accounts").status_code == 200
    assert client.get("/ready").status_code == 200
    resolved = client.post(f"/incidents/{incident_id}/resolve", headers=auth, json={
        "mitigation": "Reset failure mode to none",
        "resolution_verification": "GET /accounts 200, /ready 200, error rate back to 0",
    }).json()
    assert resolved["status"] == "resolved"
    assert resolved["resolved_at"] is not None

    closed = client.post(f"/incidents/{incident_id}/close", headers=auth, json={
        "follow_up": "Add alert on 5xx rate > 5% for 2 minutes",
    }).json()
    assert closed["status"] == "closed"
    assert [e["phase"] for e in closed["events"]] == [
        "detection", "triage", "mitigation", "recovery", "follow_up",
    ]

    # Closed incidents leave the open-incident gauge.
    assert "pw_open_incidents 0.0" in client.get("/metrics").text


def test_closed_incident_rejects_new_events(client, auth):
    incident_id = client.post("/incidents", json=NEW_INCIDENT, headers=auth).json()["id"]
    client.post(f"/incidents/{incident_id}/resolve", headers=auth,
                json={"mitigation": "Restarted", "resolution_verification": "Checks green"})
    client.post(f"/incidents/{incident_id}/close", headers=auth, json={"follow_up": "Runbook update"})
    response = client.post(f"/incidents/{incident_id}/events", headers=auth,
                           json={"phase": "triage", "note": "late note"})
    assert response.status_code == 409
