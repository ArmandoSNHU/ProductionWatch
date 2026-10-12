"""Regenerates grafana/dashboards/productionwatch.json.

    python scripts/build_grafana_dashboard.py grafana/dashboards/productionwatch.json
"""
import json, sys
DS = {"type": "prometheus", "uid": "pw-prometheus"}
panels = []
def stat(title, expr, x, y, w=4, mappings=None, thresholds=None, unit=None, legend=None):
    p = {"type": "stat", "title": title, "datasource": DS, "gridPos": {"x": x, "y": y, "w": w, "h": 4},
         "targets": [{"refId": "A", "expr": expr, "datasource": DS, "instant": True, "range": False, **({"legendFormat": legend} if legend else {})}],
         "options": {"colorMode": "background", "graphMode": "none", "reduceOptions": {"calcs": ["lastNotNull"]}, "textMode": "value_and_name" if legend else "value"},
         "fieldConfig": {"defaults": {"mappings": mappings or [], "thresholds": thresholds or {"mode": "absolute", "steps": [{"color": "green", "value": None}]}, **({"unit": unit} if unit else {})}, "overrides": []}}
    panels.append(p)
def ts(title, targets, x, y, w=12, unit=None, thresholds=None, desc=""):
    panels.append({"type": "timeseries", "title": title, "description": desc, "datasource": DS, "gridPos": {"x": x, "y": y, "w": w, "h": 8},
        "targets": [{"refId": chr(65+i), "expr": e, "legendFormat": l, "datasource": DS} for i, (e, l) in enumerate(targets)],
        "fieldConfig": {"defaults": {"unit": unit or "short", "custom": {"lineWidth": 2, "fillOpacity": 10, "thresholdsStyle": {"mode": "line" if thresholds else "off"}},
                                     "thresholds": thresholds or {"mode": "absolute", "steps": [{"color": "green", "value": None}]}}, "overrides": []},
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}})
red_green = {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "green", "value": 1}]}
updown = [{"type": "value", "options": {"0": {"text": "DOWN", "color": "red"}, "1": {"text": "UP", "color": "green"}}}]
stat("API scrape status", 'up{job="productionwatch-api"}', 0, 0, mappings=updown, thresholds=red_green)
stat("ledger-service", 'pw_dependency_up{dependency="ledger-service"}', 4, 0, mappings=updown, thresholds=red_green)
stat("Active failure mode", 'max by (mode) (pw_demo_failure_mode) == 1', 8, 0, w=6, legend="{{mode}}",
     thresholds={"mode": "absolute", "steps": [{"color": "orange", "value": None}]})
stat("5xx error rate (1m)", 'sum(rate(pw_http_errors_total[1m])) / clamp_min(sum(rate(pw_http_requests_total[1m])), 0.001) * 100', 14, 0, unit="percent",
     thresholds={"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "orange", "value": 1}, {"color": "red", "value": 5}]})
stat("p95 latency (1m)", 'histogram_quantile(0.95, sum by (le) (rate(pw_http_request_duration_seconds_bucket[1m])))', 18, 0, w=3, unit="s",
     thresholds={"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "orange", "value": 0.5}, {"color": "red", "value": 1}]})
stat("Open incidents", 'pw_open_incidents', 21, 0, w=3,
     thresholds={"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "red", "value": 1}]})
ts("Throughput (requests/sec)", [('sum(rate(pw_http_requests_total[1m]))', "total"), ('sum by (status) (rate(pw_http_requests_total[1m]))', "HTTP {{status}}")], 0, 4, unit="reqps")
ts("5xx errors/sec by route", [('sum by (route, status) (rate(pw_http_errors_total[1m]))', "{{route}} {{status}}")], 12, 4, unit="reqps")
ts("Error rate %", [('sum(rate(pw_http_errors_total[1m])) / clamp_min(sum(rate(pw_http_requests_total[1m])), 0.001) * 100', "5xx %")], 0, 12, unit="percent",
   thresholds={"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "red", "value": 5}]}, desc="Alert threshold: 5% (prometheus/alert_rules.yml)")
ts("Latency p50 / p95 / p99", [('histogram_quantile(0.5, sum by (le) (rate(pw_http_request_duration_seconds_bucket[1m])))', "p50"),
    ('histogram_quantile(0.95, sum by (le) (rate(pw_http_request_duration_seconds_bucket[1m])))', "p95"),
    ('histogram_quantile(0.99, sum by (le) (rate(pw_http_request_duration_seconds_bucket[1m])))', "p99")], 12, 12, unit="s",
   thresholds={"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "red", "value": 1}]}, desc="Alert threshold: p95 > 1s")
ts("Requests/sec by route", [('sum by (route) (rate(pw_http_requests_total[1m]))', "{{route}}")], 0, 20, unit="reqps")
ts("Requests in progress", [('pw_http_requests_in_progress', "in progress")], 12, 20)
for i, p in enumerate(panels): p["id"] = i + 1
dash = {"uid": "productionwatch", "title": "ProductionWatch — Service Health", "tags": ["productionwatch"],
        "timezone": "browser", "schemaVersion": 39, "version": 1, "refresh": "5s",
        "time": {"from": "now-15m", "to": "now"}, "panels": panels, "editable": True}
json.dump(dash, open(sys.argv[1], "w"), indent=2)
