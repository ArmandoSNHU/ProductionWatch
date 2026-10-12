# Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `docker compose up` fails with "cannot connect to the Docker daemon" | Docker Desktop not running | Start Docker Desktop, wait for "Engine running", retry |
| Port already in use (8000, 8501, 9090, 3000) | Another process on that port | `netstat -ano \| findstr :8000` (Windows) or `lsof -i :8000`; stop it or change the host port in `docker-compose.yml` |
| Console says "API is DOWN" | `api` container not healthy yet or crashed | `docker compose ps`, then `docker compose logs api` |
| Console admin buttons return HTTP 401 | Console and API have different `DEMO_TOKEN` values | Set one value in `.env`, then `docker compose up -d --force-recreate api console` |
| Admin routes return 403 | `DEMO_MODE` is not `true` | Set `DEMO_MODE=true` in `.env` and recreate `api` |
| Admin routes return 503 "DEMO_TOKEN is not set" | Empty token | Set `DEMO_TOKEN` in `.env` |
| Grafana panels say "No data" | Prometheus not scraping yet, or time range too narrow | Open http://localhost:9090/targets: `productionwatch-api` should be `UP`. Wait 15–30s after startup |
| Grafana dashboard missing | Provisioning volume not mounted | Run from the repo root so `./grafana/...` paths resolve; `docker compose logs grafana` |
| Alerts never fire | Condition must hold for the `for:` window (15–30s) | Keep the failure mode active for at least a minute; `loadgen` provides the traffic |
| Error rate in console differs from Grafana | Different windows: console uses the in-process log buffer, Grafana uses `rate(...[1m])` | Expected; see ARCHITECTURE.md tradeoffs |
| Latency mode makes the console slow | Console calls the API, which is intentionally slow | Expected; reset the failure mode |
| Want a clean database | Data lives in the `pw-data` volume | `docker compose down -v` then `docker compose up --build` |
| Tests fail with import errors | Dev dependencies missing | `pip install -r requirements-dev.txt`, run `pytest -q` from the repo root |

Useful commands:

```bash
docker compose ps
docker compose logs -f api
docker compose logs api | grep '"level": "ERROR"'
curl -s localhost:8000/ready
curl -s "localhost:8000/ops/summary?window_seconds=60"
```
