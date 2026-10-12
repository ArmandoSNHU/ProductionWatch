"""Prometheus metrics. Names here are the ones the Grafana dashboard queries."""
from prometheus_client import Counter, Gauge, Histogram

REQUESTS_TOTAL = Counter(
    "pw_http_requests_total",
    "HTTP requests handled, labeled by route template and status code.",
    ["method", "route", "status"],
)
REQUEST_LATENCY = Histogram(
    "pw_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 1.5, 2.5, 5.0),
)
REQUESTS_IN_PROGRESS = Gauge(
    "pw_http_requests_in_progress", "HTTP requests currently being handled."
)
ERRORS_TOTAL = Counter(
    "pw_http_errors_total",
    "HTTP responses with a 5xx status code.",
    ["route", "status"],
)
FAILURE_MODE = Gauge(
    "pw_demo_failure_mode",
    "1 for the currently active demo failure mode, 0 otherwise.",
    ["mode"],
)
DEPENDENCY_UP = Gauge(
    "pw_dependency_up", "1 if the dependency is reachable, 0 if not.", ["dependency"]
)
OPEN_INCIDENTS = Gauge("pw_open_incidents", "Incidents not yet closed.")

FAILURE_MODES = ("none", "latency", "error", "dependency_outage")


def set_failure_mode_metric(active: str) -> None:
    for mode in FAILURE_MODES:
        FAILURE_MODE.labels(mode=mode).set(1 if mode == active else 0)
