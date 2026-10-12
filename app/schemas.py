"""Request and response models."""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["SEV1", "SEV2", "SEV3", "SEV4"]
IncidentStatus = Literal["open", "investigating", "mitigated", "resolved", "closed"]
Phase = Literal["detection", "triage", "mitigation", "recovery", "follow_up"]
FailureMode = Literal["none", "latency", "error", "dependency_outage"]


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    holder_alias: str
    account_type: str
    balance: Decimal
    status: str


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    posted_at: datetime
    description: str
    category: str
    amount: Decimal


class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    severity: Severity
    symptoms: str = Field(min_length=3)
    impact: str = Field(min_length=3)


class IncidentEventCreate(BaseModel):
    phase: Phase
    note: str = Field(min_length=3)
    status: IncidentStatus | None = None


class IncidentResolve(BaseModel):
    mitigation: str = Field(min_length=3)
    resolution_verification: str = Field(min_length=3)


class IncidentClose(BaseModel):
    follow_up: str = Field(min_length=3, description="Post-incident improvement action")


class IncidentEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phase: str
    note: str
    created_at: datetime


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    severity: str
    status: str
    symptoms: str
    impact: str
    mitigation: str
    resolution_verification: str
    follow_up: str
    created_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None
    events: list[IncidentEventOut] = []


class FailureModeRequest(BaseModel):
    mode: FailureMode


class DemoStatus(BaseModel):
    demo_mode: bool
    failure_mode: FailureMode
    changed_at: datetime | None
    dependency_up: bool
