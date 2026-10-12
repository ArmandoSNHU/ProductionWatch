# Incident Runbook — ProductionWatch API

Scope: the `productionwatch-api` service and its mock `ledger-service` dependency. This runbook follows a standard ITIL incident flow: detect, triage, contain, restore, verify, close, follow up.

## 1. Severity

| Severity | Definition | Example in this lab | Response target |
|---|---|---|---|
| SEV1 | Full outage, all members affected, no workaround | `ApiDown` firing; `/health` unreachable | Immediate; bridge opened; leadership notified |
| SEV2 | Major function broken for many members | `HighErrorRate`: `/accounts` returning 500 | 15 min to engage; hourly updates |
| SEV3 | Degraded but usable | `HighLatencyP95`: p95 > 1s; transactions slow | Same business day |
| SEV4 | Minor, cosmetic, or single user | One account returns 404 unexpectedly | Normal queue |

When in doubt, start higher and downgrade. Upgrading late costs more than downgrading early.

## 2. Detection

Signals, in the order to check them:

1. **Alerts** at http://localhost:9090/alerts: `ApiDown`, `HighErrorRate`, `HighLatencyP95`, `DependencyDown`.
2. **Grafana** at http://localhost:3000: the "ProductionWatch — Service Health" dashboard. Check throughput, 5xx rate, p95, scrape status and dependency status.
3. **User report** with a request ID. Every response carries `X-Request-ID`, and error bodies include `request_id`.

Open the incident record as soon as the impact is confirmed (console → *Open a new incident*, or `POST /incidents`). Record symptoms and initial impact.

## 3. Triage

Work from the outside in:

| Check | Command | Interpretation |
|---|---|---|
| Liveness | `curl -i localhost:8000/health` | Not 200 → process down; go to SEV1 path |
| Readiness | `curl -i localhost:8000/ready` | 503 → read `checks` to see which dependency failed |
| User-facing route | `curl -i localhost:8000/accounts` | 500 → app error; slow → latency |
| Error logs | `docker compose logs api --since 5m \| grep '"level": "ERROR"'` | Which `endpoint`s, which `status`, what `failure_mode` |
| Trace one request | `docker compose logs api \| grep <request_id>` | The exact log line for a reported error |
| Scope | Grafana → *5xx errors/sec by route* | One route or all? Started when? |
| Recent change | `curl -H "X-Demo-Token: $DEMO_TOKEN" localhost:8000/admin/demo/status` | In real life: deploy history or change calendar |

Add a `triage` timeline entry with what you found and set status to `investigating`.

**Escalation.** If triage shows the fault is outside the application, such as database, network or a vendor dependency, page the owning team with the evidence: request IDs, time window, graphs. Keep incident command yourself until they take it.

## 4. Containment and restoration

Restore service first; root cause can wait.

| Situation | Action in this lab | Real-world equivalent |
|---|---|---|
| Errors began after a change | `POST /admin/demo/reset` (console: *Reset to healthy*) | Roll back the deployment / toggle off the feature flag |
| Dependency down | Reset, or route around it | Fail over, enable degraded mode, engage vendor |
| Process unhealthy | `docker compose restart api` | Restart pod / recycle app pool |
| Bad data or state | Not simulated | Restore from backup under change control |

**Rollback.** Prefer the smallest reversible change. Note each action and its time as a `mitigation` event, and set status to `mitigated`.

## 5. Verification

Mark the incident resolved only once **all** of these hold for at least one or two minutes:

- [ ] `GET /ready` returns 200 with every check `ok`
- [ ] `GET /accounts` and `GET /accounts/1/transactions` return 200 at normal speed
- [ ] Grafana 5xx rate back at 0% and p95 back at baseline
- [ ] The alert that triggered the incident shows `inactive`
- [ ] `/ops/summary?window_seconds=60` shows `errors_5xx: 0`

Resolve with `POST /incidents/{incident_id}/resolve` and include *how* you verified. The API requires this field.

## 6. Close and follow up

Close with `POST /incidents/{incident_id}/close`. A `follow_up` action is required. Good follow-ups are specific and owned, for example:

- Add a pre-deploy smoke test for the failing route
- Tune an alert threshold or window that fired late or noisily
- Update this runbook where a step was missing or wrong
- Problem record for root-cause analysis if the cause is not yet understood

## Communication template

> **[SEV2] Accounts API errors — investigating** (HH:MM CT)
> Impact: members cannot load account summaries. Started ~HH:MM.
> Current action: rolling back the most recent change. Next update in 30 minutes or sooner.
