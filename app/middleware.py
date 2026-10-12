"""Request ID, timing, structured access logs and Prometheus metrics."""
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.logging_utils import log_event
from app.metrics import ERRORS_TOTAL, REQUEST_LATENCY, REQUESTS_IN_PROGRESS, REQUESTS_TOTAL

# Scrapes and console polling would otherwise drown out real traffic in the SLIs.
NOT_LOGGED = {"/metrics", "/ops/summary", "/ops/logs"}
# Operator actions are logged for audit but kept out of the member-facing SLIs.
OPERATOR_PREFIXES = ("/admin/",)


def _route_template(request: Request) -> str:
    # Use the route pattern (/accounts/{account_id}) rather than the raw path
    # so metrics do not get one label per account id.
    route = request.scope.get("route")
    return getattr(route, "path", None) or "unmatched"


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        path = request.url.path
        silent = path in NOT_LOGGED
        operator = path.startswith(OPERATOR_PREFIXES)
        excluded = silent or operator
        logger = request.app.state.logger

        if not excluded:
            REQUESTS_IN_PROGRESS.inc()
        started = time.perf_counter()
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as exc:
            status = 500
            log_event(logger, logging.ERROR, "unhandled exception", request_id=request_id,
                      method=request.method, path=request.url.path, error_type=type(exc).__name__)
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "request_id": request_id},
            )
        finally:
            duration = time.perf_counter() - started
            if not excluded:
                REQUESTS_IN_PROGRESS.dec()

        response.headers["X-Request-ID"] = request_id
        if silent:
            return response

        route = _route_template(request)
        if operator:
            log_event(logger, logging.INFO, "operator action", request_id=request_id,
                      method=request.method, endpoint=route, status=status)
            return response

        REQUESTS_TOTAL.labels(method=request.method, route=route, status=str(status)).inc()
        REQUEST_LATENCY.labels(method=request.method, route=route).observe(duration)
        if status >= 500:
            ERRORS_TOTAL.labels(route=route, status=str(status)).inc()

        level = logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
        log_event(
            logger, level, "request completed",
            request_id=request_id, method=request.method, endpoint=route,
            path=request.url.path, status=status, duration_ms=round(duration * 1000, 1),
            failure_mode=request.app.state.failure.mode,
        )
        return response
