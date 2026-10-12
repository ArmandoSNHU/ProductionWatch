# ProductionWatch

Portfolio lab for a Tier 2 Application Support Engineer role. It's a synthetic accounts API (FastAPI + SQLite) with Prometheus metrics, Grafana dashboards, alert rules, structured logs, safe failure injection, and an incident record lifecycle, plus a Streamlit operator console and a static GitHub Pages simulation (`site/`). All data is fake. Never connect it to real financial services.

## Read order

1. `STATE.md` — current state and Restart Point (wins over anything else)
2. `README.md` — user-facing overview and commands
3. `docs/ARCHITECTURE.md` — endpoint table (enforced by `tests/test_docs_contract.py`), metrics, tradeoffs
4. `docs/INTERVIEW_DEMO.md`, `docs/INCIDENT_RUNBOOK.md`, `docs/TROUBLESHOOTING.md`

## Commands

```bash
.venv/Scripts/python.exe -m pytest -q          # tests (Windows venv path)
docker compose up --build -d                   # full stack
docker compose ps
bash scripts/run_incident_scenario.sh 60       # live end-to-end check against running stack
python scripts/build_grafana_dashboard.py grafana/dashboards/productionwatch.json  # regenerate dashboard
cd site && python -m http.server 8765          # preview Pages dashboard
```

Ports: api 8000, console 8501, prometheus 9090, grafana 3000.

## Architecture pointers

| Area | File |
|---|---|
| App factory, probes, accounts, /metrics, /ops | `app/main.py` |
| Request ID, metrics, access logs, SLI exclusions | `app/middleware.py` |
| Failure modes, token + DEMO_MODE guards | `app/demo_controls.py` |
| Incident lifecycle | `app/incident_routes.py` |
| Metric names (Grafana + alerts depend on them) | `app/metrics.py` |
| Alert rules | `prometheus/alert_rules.yml` |
| Grafana dashboard (generated) | `scripts/build_grafana_dashboard.py` → `grafana/dashboards/productionwatch.json` |
| Pages simulation | `site/index.html` (self-contained, no build) |

## Gotchas

- Renaming a metric breaks the Grafana JSON, alert rules **and** the Pages copy. Update all three.
- Adding a route requires a row in `docs/ARCHITECTURE.md` or the contract test fails.
- Grafana stat panels use instant queries. Range queries made the failure-mode tile show stale modes.
- `/metrics`, `/ops/*` are not logged or counted; `/admin/*` is logged as `operator action` but not counted.
- The Dockerfile.api HEALTHCHECK is inherited by `loadgen`; compose disables it there.
- Playwright MCP screenshots resolve relative paths against the session cwd and drop `.playwright-mcp/` there. Use absolute paths and delete that folder.

## Approval gates

- Pushing to `origin` (github.com/ArmandoSNHU/ProductionWatch) is authorized by the owner for this project.
- Never commit `.env`. The default demo token in compose/.env.example is a placeholder, not a secret.
- Keep interview docs truthful: no invented production experience.

## Completion standard

Tests pass (report the count), `docker compose up --build` is healthy, the incident scenario script completes, README commands match real behavior, and STATE.md has a dated entry.
