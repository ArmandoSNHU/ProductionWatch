"""Incident records: create, annotate the timeline, resolve and close.

Lifecycle: open -> investigating -> mitigated -> resolved -> closed.
Resolving requires the mitigation and how recovery was verified; closing
requires a post-incident follow-up action, so an incident cannot be closed
without capturing what will prevent a repeat.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.demo_controls import require_demo_token
from app.logging_utils import log_event
from app.metrics import OPEN_INCIDENTS
from app.models import Incident, IncidentEvent
from app.schemas import IncidentClose, IncidentCreate, IncidentEventCreate, IncidentOut, IncidentResolve


def get_db(request: Request):
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


router = APIRouter(prefix="/incidents", tags=["incidents"])


def refresh_open_incident_gauge(db: Session) -> None:
    count = db.scalar(select(func.count(Incident.id)).where(Incident.status != "closed")) or 0
    OPEN_INCIDENTS.set(count)


def _load(db: Session, incident_id: int) -> Incident:
    incident = db.scalar(
        select(Incident).options(selectinload(Incident.events)).where(Incident.id == incident_id)
    )
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found.")
    return incident


@router.get("", response_model=list[IncidentOut])
def list_incidents(db: Session = Depends(get_db)):
    return db.scalars(
        select(Incident).options(selectinload(Incident.events)).order_by(Incident.id.desc())
    ).all()


@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    return _load(db, incident_id)


@router.post("", response_model=IncidentOut, status_code=201, dependencies=[Depends(require_demo_token)])
def create_incident(body: IncidentCreate, request: Request, db: Session = Depends(get_db)):
    incident = Incident(**body.model_dump(), status="open")
    incident.events.append(IncidentEvent(phase="detection", note=f"Incident opened: {body.symptoms}"))
    db.add(incident)
    db.commit()
    refresh_open_incident_gauge(db)
    log_event(request.app.state.logger, logging.WARNING, "incident opened",
              incident_id=incident.id, severity=incident.severity, title=incident.title)
    return _load(db, incident.id)


@router.post("/{incident_id}/events", response_model=IncidentOut, dependencies=[Depends(require_demo_token)])
def add_event(incident_id: int, body: IncidentEventCreate, db: Session = Depends(get_db)):
    incident = _load(db, incident_id)
    if incident.status == "closed":
        raise HTTPException(status_code=409, detail="Incident is closed; reopen by creating a new incident.")
    incident.events.append(IncidentEvent(phase=body.phase, note=body.note))
    if body.status and body.status not in {"resolved", "closed"}:
        # resolved/closed have required fields, so they go through their own endpoints.
        incident.status = body.status
    db.commit()
    return _load(db, incident_id)


@router.post("/{incident_id}/resolve", response_model=IncidentOut, dependencies=[Depends(require_demo_token)])
def resolve_incident(incident_id: int, body: IncidentResolve, request: Request, db: Session = Depends(get_db)):
    incident = _load(db, incident_id)
    if incident.status in {"resolved", "closed"}:
        raise HTTPException(status_code=409, detail=f"Incident is already {incident.status}.")
    incident.status = "resolved"
    incident.mitigation = body.mitigation
    incident.resolution_verification = body.resolution_verification
    incident.resolved_at = datetime.now(timezone.utc)
    incident.events.append(IncidentEvent(phase="recovery", note=f"Resolved. Verified by: {body.resolution_verification}"))
    db.commit()
    log_event(request.app.state.logger, logging.INFO, "incident resolved", incident_id=incident_id)
    return _load(db, incident_id)


@router.post("/{incident_id}/close", response_model=IncidentOut, dependencies=[Depends(require_demo_token)])
def close_incident(incident_id: int, body: IncidentClose, request: Request, db: Session = Depends(get_db)):
    incident = _load(db, incident_id)
    if incident.status != "resolved":
        raise HTTPException(status_code=409, detail="Only resolved incidents can be closed.")
    incident.status = "closed"
    incident.follow_up = body.follow_up
    incident.closed_at = datetime.now(timezone.utc)
    incident.events.append(IncidentEvent(phase="follow_up", note=body.follow_up))
    db.commit()
    refresh_open_incident_gauge(db)
    log_event(request.app.state.logger, logging.INFO, "incident closed", incident_id=incident_id)
    return _load(db, incident_id)
