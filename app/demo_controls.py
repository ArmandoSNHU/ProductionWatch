"""Local-demo-only failure injection.

Nothing here touches the database destructively. Failure modes only change
how the account endpoints respond so the effect shows up in logs and metrics:

- latency            adds a fixed delay to account endpoints
- error              account endpoints return HTTP 500
- dependency_outage  the mock "ledger-service" is marked down, so /ready
                     fails and transaction lookups return HTTP 503

All routes require DEMO_MODE=true and the X-Demo-Token header.
"""
import hmac
import logging
import threading
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.logging_utils import log_event
from app.metrics import DEPENDENCY_UP, set_failure_mode_metric
from app.schemas import DemoStatus, FailureModeRequest

LEDGER_DEPENDENCY = "ledger-service"


class FailureState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.mode = "none"
        self.changed_at: datetime | None = None
        set_failure_mode_metric("none")
        DEPENDENCY_UP.labels(dependency=LEDGER_DEPENDENCY).set(1)

    def set(self, mode: str) -> None:
        with self._lock:
            self.mode = mode
            self.changed_at = datetime.now(timezone.utc)
        set_failure_mode_metric(mode)
        DEPENDENCY_UP.labels(dependency=LEDGER_DEPENDENCY).set(0 if mode == "dependency_outage" else 1)

    @property
    def dependency_up(self) -> bool:
        return self.mode != "dependency_outage"


def require_demo_token(request: Request, x_demo_token: str | None = Header(default=None)) -> None:
    expected = request.app.state.settings.demo_token
    if not expected:
        raise HTTPException(status_code=503, detail="Admin routes are disabled: DEMO_TOKEN is not set.")
    # compare_digest avoids leaking token length/prefix through response timing.
    if not x_demo_token or not hmac.compare_digest(x_demo_token, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid X-Demo-Token header.")


def require_demo_mode(request: Request) -> None:
    if not request.app.state.settings.demo_mode:
        raise HTTPException(status_code=403, detail="Failure injection requires DEMO_MODE=true.")


def apply_failure_mode(request: Request) -> None:
    """Dependency for account routes: applies whichever failure mode is active."""
    state: FailureState = request.app.state.failure
    if state.mode == "latency":
        time.sleep(request.app.state.settings.demo_latency_seconds)
    elif state.mode == "error":
        raise HTTPException(status_code=500, detail="Injected failure: simulated application error.")


def require_ledger(request: Request) -> None:
    """Dependency for routes that call the mock ledger service."""
    if not request.app.state.failure.dependency_up:
        raise HTTPException(
            status_code=503, detail=f"Dependency unavailable: {LEDGER_DEPENDENCY} is not responding."
        )


router = APIRouter(
    prefix="/admin/demo",
    tags=["demo controls"],
    dependencies=[Depends(require_demo_token), Depends(require_demo_mode)],
)


def _status(request: Request) -> DemoStatus:
    state: FailureState = request.app.state.failure
    return DemoStatus(
        demo_mode=request.app.state.settings.demo_mode,
        failure_mode=state.mode,
        changed_at=state.changed_at,
        dependency_up=state.dependency_up,
    )


@router.get("/status", response_model=DemoStatus)
def get_status(request: Request) -> DemoStatus:
    return _status(request)


@router.post("/failure", response_model=DemoStatus)
def set_failure(body: FailureModeRequest, request: Request) -> DemoStatus:
    previous = request.app.state.failure.mode
    request.app.state.failure.set(body.mode)
    log_event(
        request.app.state.logger, logging.WARNING, "demo failure mode changed",
        previous_mode=previous, failure_mode=body.mode,
        request_id=getattr(request.state, "request_id", None),
    )
    return _status(request)


@router.post("/reset", response_model=DemoStatus)
def reset(request: Request) -> DemoStatus:
    previous = request.app.state.failure.mode
    request.app.state.failure.set("none")
    log_event(
        request.app.state.logger, logging.INFO, "demo failure mode reset",
        previous_mode=previous, failure_mode="none",
        request_id=getattr(request.state, "request_id", None),
    )
    return _status(request)
