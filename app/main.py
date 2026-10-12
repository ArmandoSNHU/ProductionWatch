"""ProductionWatch API: a synthetic accounts service built to be observed.

Run locally:  uvicorn app.main:app --reload
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import demo_controls, incident_routes
from app.config import Settings
from app.database import Base, build_engine, build_session_factory
from app.demo_controls import FailureState, apply_failure_mode, require_demo_token, require_ledger
from app.incident_routes import get_db, refresh_open_incident_gauge
from app.logging_utils import RecentLogBuffer, configure_logging, log_event
from app.middleware import ObservabilityMiddleware
from app.models import Account, Transaction
from app.schemas import AccountOut, TransactionOut
from app.seed import seed_database

VERSION = "1.0.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    log_buffer = RecentLogBuffer()
    logger = configure_logging(settings.log_level, log_buffer)
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        Base.metadata.create_all(engine)
        with session_factory() as session:
            created = seed_database(session) if settings.seed_on_startup else 0
            refresh_open_incident_gauge(session)
        log_event(logger, logging.INFO, "service started", version=VERSION,
                  demo_mode=settings.demo_mode, seeded_accounts=created)
        yield
        engine.dispose()

    app = FastAPI(
        title="ProductionWatch API",
        version=VERSION,
        description="Synthetic accounts API for a local reliability and incident-response lab. "
        "All data is fake.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.logger = logger
    app.state.log_buffer = log_buffer
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.failure = FailureState()
    app.state.started_at = datetime.now(timezone.utc)

    app.add_middleware(ObservabilityMiddleware)
    app.include_router(demo_controls.router)
    app.include_router(incident_routes.router)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        # Include the request id in error bodies so a user-reported error can
        # be traced straight to the matching log line.
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "request_id": getattr(request.state, "request_id", None)},
        )

    @app.get("/health", tags=["probes"])
    def health():
        """Liveness: the process is up and answering. Does not check dependencies."""
        uptime = (datetime.now(timezone.utc) - app.state.started_at).total_seconds()
        return {"status": "ok", "service": "productionwatch-api", "version": VERSION,
                "uptime_seconds": round(uptime, 1)}

    @app.get("/ready", tags=["probes"])
    def ready(request: Request):
        """Readiness: can this instance actually serve traffic right now?"""
        checks = {}
        try:
            with app.state.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as exc:  # report rather than crash, so the probe stays useful
            checks["database"] = f"error: {type(exc).__name__}"
        ledger_ok = request.app.state.failure.dependency_up
        checks[demo_controls.LEDGER_DEPENDENCY] = "ok" if ledger_ok else "unavailable"
        is_ready = all(value == "ok" for value in checks.values())
        return JSONResponse(status_code=200 if is_ready else 503,
                            content={"status": "ready" if is_ready else "not_ready", "checks": checks})

    @app.get("/accounts", response_model=list[AccountOut], tags=["accounts"],
             dependencies=[Depends(apply_failure_mode)])
    def list_accounts(db: Session = Depends(get_db)):
        return db.scalars(select(Account).order_by(Account.id)).all()

    @app.get("/accounts/{account_id}", response_model=AccountOut, tags=["accounts"],
             dependencies=[Depends(apply_failure_mode)])
    def get_account(account_id: int, db: Session = Depends(get_db)):
        account = db.get(Account, account_id)
        if account is None:
            raise HTTPException(status_code=404, detail=f"Account {account_id} not found.")
        return account

    @app.get("/accounts/{account_id}/transactions", response_model=list[TransactionOut],
             tags=["accounts"], dependencies=[Depends(apply_failure_mode), Depends(require_ledger)])
    def list_transactions(account_id: int, limit: int = Query(default=20, ge=1, le=100),
                          db: Session = Depends(get_db)):
        if db.get(Account, account_id) is None:
            raise HTTPException(status_code=404, detail=f"Account {account_id} not found.")
        return db.scalars(
            select(Transaction).where(Transaction.account_id == account_id)
            .order_by(Transaction.posted_at.desc()).limit(limit)
        ).all()

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/ops/logs", tags=["operations"], dependencies=[Depends(require_demo_token)])
    def recent_logs(limit: int = Query(default=50, ge=1, le=500), level: str | None = None):
        """Most recent structured log entries (newest first) for the operator console."""
        entries = app.state.log_buffer.recent(500)
        if level:
            entries = [e for e in entries if e.get("level") == level.upper()]
        return entries[:limit]

    @app.get("/ops/summary", tags=["operations"])
    def summary(window_seconds: int = Query(default=300, ge=10, le=3600)):
        """Request count, error rate and p95 latency over a recent window, from the log buffer."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        requests = [
            e for e in app.state.log_buffer.snapshot()
            if e.get("message") == "request completed"
            and datetime.fromisoformat(e["timestamp"]) >= cutoff
        ]
        durations = sorted(e["duration_ms"] for e in requests)
        errors = sum(1 for e in requests if e["status"] >= 500)
        p95 = durations[max(0, int(len(durations) * 0.95) - 1)] if durations else 0.0
        return {
            "window_seconds": window_seconds,
            "requests": len(requests),
            "errors_5xx": errors,
            "error_rate_pct": round(100 * errors / len(requests), 2) if requests else 0.0,
            "p95_latency_ms": p95,
            "failure_mode": app.state.failure.mode,
            "dependency_up": app.state.failure.dependency_up,
        }

    return app


app = create_app()
