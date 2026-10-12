# Five-Minute Interview Demo

Two ways to run it:

- **Live stack (preferred).** Run `docker compose up --build` at least two minutes before the interview so Grafana has a healthy baseline. Open four tabs: console (`:8501`), Grafana (`:3000`), Prometheus alerts (`:9090/alerts`), and a terminal.
- **No Docker available, or screen-share only.** Open https://armandosnhu.github.io/ProductionWatch/ and click through the guided walkthrough. It follows the same six steps below, with talking points on screen. Say up front that it's a browser simulation of the real stack.

Opening line (about 15s):

> "This is ProductionWatch, a lab I built to practice L2 application support end to end. It's a fake accounts API with real monitoring around it: Prometheus, Grafana, structured logs and an incident record. All the data is synthetic. I'll break it, find it, fix it and close it out the way I'd handle a real incident."

---

### 0:00–0:45 Baseline: what healthy looks like

- Grafana: throughput steady at about 2 req/s from `loadgen`, 5xx rate 0%, p95 in single-digit milliseconds, scrape status UP.
- Terminal: `curl -s localhost:8000/health` and `curl -s localhost:8000/ready`.

> "Before anything breaks I want to know what normal looks like. These are the golden signals: traffic, errors, latency and saturation. `/health` is liveness, meaning the process is up. `/ready` is readiness: can it actually serve traffic, including its dependencies? The difference matters in a minute."

### 0:45–1:15 Inject the failure

Console → *Failure injection* → `error` → *Apply failure mode*. Or:

```bash
curl -s -X POST localhost:8000/admin/demo/failure -H "X-Demo-Token: $DEMO_TOKEN" \
  -H "Content-Type: application/json" -d '{"mode":"error"}'
```

> "This simulates a bad change. It's gated behind a demo flag and a token, and it never touches data. It only changes how the account endpoints respond."

### 1:15–2:15 Detect and triage

- Grafana: error rate jumps and *5xx errors/sec by route* shows which routes. Prometheus `/alerts`: `HighErrorRate` goes **pending**, then **firing** after 30s.
- Console: open an incident at SEV2 with symptoms and impact.
- Terminal:

```bash
curl -i localhost:8000/accounts          # 500, note the request_id in the body
curl -s localhost:8000/health            # still 200
docker compose logs api --since 2m | grep '"level": "ERROR"' | head -3
docker compose logs api | grep <request_id>
```

> "The alert has a 30-second `for` window so one blip doesn't page anyone. SEV2 because a core member function is broken but the service is up. `/health` is still 200, so the process is alive and restarting won't help. The logs show every account route failing, and the database and dependency are healthy, so this is the application path, not infrastructure. The request ID lets me take a member's error report straight to the exact log line."

Add a *triage* timeline entry in the console and set status to `investigating`.

### 2:15–3:00 Mitigate: restore first

Console → *Reset to healthy* (or `POST /admin/demo/reset`). Add a *mitigation* timeline entry and set status to `mitigated`.

> "Restore service first, root cause second. In production this would be a rollback or a feature-flag toggle: the smallest reversible change, done under the emergency change process and noted on the timeline with a timestamp."

### 3:00–3:45 Verify recovery

- Grafana: 5xx rate back to 0%. Prometheus: alert back to inactive.
- `curl -s localhost:8000/ready` → 200; `curl -s "localhost:8000/ops/summary?window_seconds=30"` → `errors_5xx: 0`.
- Console → *Mark resolved* with mitigation and verification text.

> "I don't call it resolved because I clicked a button. I check the same signals that detected it. The API won't resolve without a verification note, by design."

### 3:45–4:30 Close with a follow-up

Console → *Close incident* with a follow-up, e.g. *"Add pre-deploy smoke test for /accounts; update runbook step 3."*

> "An incident isn't done until something changes so it doesn't happen again. The API rejects a close without a follow-up action. If the root cause isn't understood yet, the follow-up is opening a problem record."

### 4:30–5:00 Wrap up and connect it to the role

> "That's the whole cycle: detect, triage, mitigate, verify, close and follow up. I also built a dependency-outage mode that shows liveness and readiness disagreeing, and a latency mode that trips the p95 alert. The workflow matches what I've done in support: [personalize: ServiceNow tickets, API integration troubleshooting, diagnosing performance issues, building internal dashboards]. What I'd add next is Alertmanager routing into a ticketing tool, and trace IDs across more than one service."

---

## Likely follow-up questions

| Question | Short answer |
|---|---|
| Why is `/health` 200 during the outage? | Liveness answers "is the process alive?". A restart wouldn't fix an app or dependency fault. Readiness is the probe that should pull an instance out of a load balancer. |
| Why `route` and not `path` as the metric label? | Bounded cardinality. One series per account ID would blow up Prometheus. |
| Why exclude `/metrics` and admin calls from the metrics? | Scrapes and operator actions aren't member traffic, so counting them would distort the SLIs. |
| How would this look at enterprise scale? | Splunk/Dynatrace instead of the log buffer, Alertmanager → ServiceNow for paging and tickets, OpenShift/Kubernetes probes wired to `/health` and `/ready`, change records for the rollback. |
| What would you do if the rollback didn't fix it? | Escalate with evidence (request IDs, timeline, graphs) to the owning team or vendor. Keep incident command, keep updates on cadence, and consider failover or degraded mode. |
| What's the weakest part of this lab? | Failures are simulated in-process, there's a single instance, and the token isn't real auth. I documented these in ARCHITECTURE.md. |

## Honest positioning

- This is a personal learning lab I built with AI-assisted development. I can walk through every component and run it myself.
- I have not run production Kubernetes, Splunk or banking systems. The lab is how I practice those concepts, and I say so if asked.
