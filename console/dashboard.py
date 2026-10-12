"""ProductionWatch operator console.

Run locally:  streamlit run console/dashboard.py
Talks to the API over HTTP only; it has no direct database access.
"""
import os
import time

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
DEMO_TOKEN = os.getenv("DEMO_TOKEN", "")
GRAFANA_URL = os.getenv("GRAFANA_PUBLIC_URL", "http://localhost:3000")
PROMETHEUS_URL = os.getenv("PROMETHEUS_PUBLIC_URL", "http://localhost:9090")
TIMEOUT = 5

FAILURE_MODES = {
    "none": "Healthy baseline",
    "latency": "Elevated latency on account endpoints",
    "error": "HTTP 500 on account endpoints",
    "dependency_outage": "Mock ledger-service outage (readiness fails, transactions 503)",
}
PHASES = ["detection", "triage", "mitigation", "recovery", "follow_up"]

st.set_page_config(page_title="ProductionWatch Console", layout="wide")


def call(method: str, path: str, **kwargs):
    """Returns (response or None, error message or None). Never raises."""
    headers = kwargs.pop("headers", {})
    if DEMO_TOKEN:
        headers["X-Demo-Token"] = DEMO_TOKEN
    try:
        return requests.request(method, f"{API_URL}{path}", headers=headers, timeout=TIMEOUT, **kwargs), None
    except requests.RequestException as exc:
        return None, f"{type(exc).__name__}: cannot reach API at {API_URL}"


def show_error(response, error):
    if error:
        st.error(error)
    elif response is not None and not response.ok:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = response.text[:200]
        st.error(f"HTTP {response.status_code}: {detail}")


st.title("ProductionWatch — Operator Console")
st.caption("Local reliability lab. All account data is synthetic. Not a production banking system.")

if not DEMO_TOKEN:
    st.warning("DEMO_TOKEN is not set for the console, so admin actions will be rejected.")

# ---------------------------------------------------------------- service status
health, health_err = call("GET", "/health")
if health_err:
    st.error(f"API is DOWN. {health_err}. Check `docker compose ps` and `docker compose logs api`.")
    st.stop()

ready, _ = call("GET", "/ready")
summary_resp, _ = call("GET", "/ops/summary", params={"window_seconds": 120})
status_resp, _ = call("GET", "/admin/demo/status")
summary = summary_resp.json() if summary_resp is not None and summary_resp.ok else {}
demo = status_resp.json() if status_resp is not None and status_resp.ok else {}
mode = demo.get("failure_mode", summary.get("failure_mode", "unknown"))

if mode not in ("none", "unknown"):
    st.warning(f"FAILURE INJECTION ACTIVE: **{mode}** — {FAILURE_MODES.get(mode, '')}")

cols = st.columns(5)
cols[0].metric("Liveness /health", "UP" if health.ok else f"HTTP {health.status_code}")
ready_ok = ready is not None and ready.ok
cols[1].metric("Readiness /ready", "READY" if ready_ok else "NOT READY")
cols[2].metric("Requests (2 min)", summary.get("requests", "–"))
cols[3].metric("5xx error rate", f"{summary.get('error_rate_pct', 0)}%")
cols[4].metric("p95 latency", f"{summary.get('p95_latency_ms', 0)} ms")
if ready is not None and not ready_ok:
    st.error(f"Readiness checks: {ready.json().get('checks')}")

st.markdown(f"Dashboards: [Grafana]({GRAFANA_URL}) · [Prometheus]({PROMETHEUS_URL}) · "
            f"[API docs]({os.getenv('API_PUBLIC_URL', 'http://localhost:8000')}/docs)")

left, right = st.columns([1, 1])

# ---------------------------------------------------------------- failure injection
with left:
    st.subheader("Failure injection (demo only)")
    if not demo.get("demo_mode", False):
        st.info("Failure injection is disabled. Set DEMO_MODE=true and DEMO_TOKEN to enable it.")
    else:
        choice = st.radio("Failure mode", list(FAILURE_MODES), format_func=lambda m: f"{m} — {FAILURE_MODES[m]}",
                          index=list(FAILURE_MODES).index(mode) if mode in FAILURE_MODES else 0)
        c1, c2 = st.columns(2)
        if c1.button("Apply failure mode", type="primary"):
            r, e = call("POST", "/admin/demo/failure", json={"mode": choice})
            show_error(r, e) if (e or not r.ok) else st.rerun()
        if c2.button("Reset to healthy"):
            r, e = call("POST", "/admin/demo/reset")
            show_error(r, e) if (e or not r.ok) else st.rerun()

    st.subheader("Generate traffic")
    burst = st.slider("Requests", 10, 100, 30, step=10)
    if st.button("Send traffic burst"):
        paths = ["/accounts", "/accounts/1", "/accounts/2/transactions", "/accounts/3"]
        results = {}
        for i in range(burst):
            r, _ = call("GET", paths[i % len(paths)])
            key = r.status_code if r is not None else "no response"
            results[key] = results.get(key, 0) + 1
        st.write("Status codes:", results)

# ---------------------------------------------------------------- recent logs
with right:
    st.subheader("Recent structured logs")
    level = st.selectbox("Level", ["ALL", "ERROR", "WARNING", "INFO"])
    params = {"limit": 40}
    if level != "ALL":
        params["level"] = level
    logs_resp, logs_err = call("GET", "/ops/logs", params=params)
    if logs_err or not logs_resp.ok:
        show_error(logs_resp, logs_err)
    else:
        rows = [
            {k: e.get(k) for k in ("timestamp", "level", "status", "method", "endpoint",
                                   "duration_ms", "request_id", "failure_mode", "message")}
            for e in logs_resp.json()
        ]
        st.dataframe(rows, use_container_width=True, height=360)

# ---------------------------------------------------------------- incidents
st.divider()
st.subheader("Incidents")

with st.expander("Open a new incident"):
    with st.form("new_incident", clear_on_submit=True):
        title = st.text_input("Title", "Accounts API returning HTTP 500")
        severity = st.selectbox("Severity", ["SEV1", "SEV2", "SEV3", "SEV4"], index=1)
        symptoms = st.text_area("Symptoms (what monitoring/users show)", "5xx error rate spiked on /accounts")
        impact = st.text_area("Initial impact", "Members cannot load account summaries")
        if st.form_submit_button("Create incident"):
            r, e = call("POST", "/incidents", json={"title": title, "severity": severity,
                                                     "symptoms": symptoms, "impact": impact})
            show_error(r, e) if (e or not r.ok) else st.success(f"Incident #{r.json()['id']} opened")

incidents_resp, inc_err = call("GET", "/incidents")
if inc_err or not incidents_resp.ok:
    show_error(incidents_resp, inc_err)
    incidents = []
else:
    incidents = incidents_resp.json()

if not incidents:
    st.caption("No incidents recorded yet.")

for inc in incidents:
    header = f"#{inc['id']} [{inc['severity']}] {inc['title']} — {inc['status'].upper()}"
    with st.expander(header, expanded=inc["status"] != "closed"):
        st.markdown(f"**Symptoms:** {inc['symptoms']}  \n**Impact:** {inc['impact']}")
        if inc["mitigation"]:
            st.markdown(f"**Mitigation:** {inc['mitigation']}  \n"
                        f"**Verification:** {inc['resolution_verification']}")
        if inc["follow_up"]:
            st.markdown(f"**Follow-up:** {inc['follow_up']}")

        st.markdown("**Timeline**")
        for ev in inc["events"]:
            st.markdown(f"- `{ev['created_at'][:19]}` **{ev['phase']}** — {ev['note']}")

        if inc["status"] == "closed":
            continue
        key = f"inc{inc['id']}"
        if inc["status"] != "resolved":
            with st.form(f"{key}_note", clear_on_submit=True):
                phase = st.selectbox("Phase", PHASES[:4], index=1, key=f"{key}_phase")
                new_status = st.selectbox("Set status", ["(unchanged)", "investigating", "mitigated"],
                                          key=f"{key}_status")
                note = st.text_input("Note", key=f"{key}_text")
                if st.form_submit_button("Add timeline entry"):
                    body = {"phase": phase, "note": note}
                    if new_status != "(unchanged)":
                        body["status"] = new_status
                    r, e = call("POST", f"/incidents/{inc['id']}/events", json=body)
                    show_error(r, e) if (e or not r.ok) else st.rerun()
            with st.form(f"{key}_resolve"):
                mitigation = st.text_input("Mitigation applied", key=f"{key}_mit")
                verification = st.text_input("How recovery was verified", key=f"{key}_ver")
                if st.form_submit_button("Mark resolved"):
                    r, e = call("POST", f"/incidents/{inc['id']}/resolve",
                                json={"mitigation": mitigation, "resolution_verification": verification})
                    show_error(r, e) if (e or not r.ok) else st.rerun()
        else:
            with st.form(f"{key}_close"):
                follow_up = st.text_input("Post-incident improvement", key=f"{key}_fu")
                if st.form_submit_button("Close incident"):
                    r, e = call("POST", f"/incidents/{inc['id']}/close", json={"follow_up": follow_up})
                    show_error(r, e) if (e or not r.ok) else st.rerun()

st.caption(f"Console refreshed {time.strftime('%H:%M:%S')}. Use the browser refresh or any action to update.")
