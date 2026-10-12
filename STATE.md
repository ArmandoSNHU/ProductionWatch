# ProductionWatch — State

## Restart Point (2026-10-12)

- **Status:** v1.0 complete and pushed to `origin/main` (github.com/ArmandoSNHU/ProductionWatch).
- **Verify before changing anything:** `.venv/Scripts/python.exe -m pytest -q` → `34 passed`.
- **Live check:** `docker compose up --build -d`, then `bash scripts/run_incident_scenario.sh 40` → ends with `incident N closed ['detection', 'triage', 'mitigation', 'recovery', 'follow_up']`.
- **Pages:** `site/index.html` deployed by `.github/workflows/pages.yml` to https://armandosnhu.github.io/ProductionWatch/ (Pages source must be "GitHub Actions").
- **Purpose:** portfolio demo for USAA Application Support Engineer – Intermediate (Job ID R0120538).

## Next ideas (not started)

- Alertmanager + webhook into a mock ticket queue (ServiceNow-style)
- Second service to demonstrate cross-service trace IDs
- Re-take `docs/screenshots/pages-dashboard.png` (log line format changed after it was captured)

## Session log

### 2026-10-12 — initial build (Claude Code)
- Built API, console, loadgen, Prometheus + alert rules, Grafana dashboard, Pages simulation, docs, CI.
- Verified: `34 passed`; Docker stack healthy (5 services); all three failure modes and reset checked with curl; Prometheus `HighErrorRate` fired during error mode; Grafana dashboard provisioned and queried; console rendered with live outage; scripted incident closed with all five phases.
- Fixes found during live validation: loadgen inherited API healthcheck (disabled); Grafana failure-mode stat showed stale series (instant queries); admin calls polluted SLIs (excluded, logged as operator action); docs used `{id}` vs `{incident_id}` (contract test).
