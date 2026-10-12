#!/usr/bin/env bash
# Plays one full incident against the running Docker stack:
# inject HTTP 500s -> open incident -> triage -> restore -> resolve -> close.
# Usage: DEMO_TOKEN=... bash scripts/run_incident_scenario.sh [seconds_of_failure]
set -euo pipefail
API="${API_URL:-http://localhost:8000}"
TOKEN="${DEMO_TOKEN:-change-me-local-demo-token}"
FAIL_SECONDS="${1:-90}"
H=(-H "X-Demo-Token: $TOKEN" -H "Content-Type: application/json")

post() { curl -sf -X POST "${H[@]}" "$API$1" -d "${2:-{\}}"; echo; }

echo "== baseline"; curl -s "$API/ops/summary?window_seconds=60"; echo
echo "== inject error mode"; post /admin/demo/failure '{"mode":"error"}'
sleep 20
echo "== open incident"
ID=$(post /incidents '{"title":"Accounts API returning HTTP 500","severity":"SEV2","symptoms":"HighErrorRate alert firing; 5xx rate above 50% on /accounts routes","impact":"Members cannot load account summaries or transactions"}' | python -c "import sys,json;print(json.load(sys.stdin)['id'])")
post "/incidents/$ID/events" '{"phase":"triage","status":"investigating","note":"/health 200 but /accounts 500. Logs: failure_mode=error on all account routes. ledger-service healthy, DB ok."}' >/dev/null
sleep "$FAIL_SECONDS"
echo "== mitigate: reset failure mode"; post /admin/demo/reset
post "/incidents/$ID/events" '{"phase":"mitigation","status":"mitigated","note":"Rolled back faulty change (demo reset to failure_mode=none)."}' >/dev/null
sleep 30
echo "== verify"; curl -s "$API/ready"; echo; curl -s "$API/ops/summary?window_seconds=20"; echo
post "/incidents/$ID/resolve" '{"mitigation":"Rolled back the change that introduced the failing code path","resolution_verification":"/ready 200, GET /accounts 200, Grafana 5xx rate back to 0% for 30s, HighErrorRate alert cleared"}' >/dev/null
post "/incidents/$ID/close" '{"follow_up":"Add pre-deploy smoke test on /accounts; tighten HighErrorRate alert to page at 5% for 1m; update runbook step 3"}' | python -c "import sys,json;d=json.load(sys.stdin);print('incident',d['id'],d['status'],[e['phase'] for e in d['events']])"
