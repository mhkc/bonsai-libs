"""Audit log Pydantic models used across Bonsai services."""
from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventSeverity(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warning"
    ERROR = "error"


class SourceType(str, Enum):
    USR = "user"
    SYS = "system"


class Actor(BaseModel):
    type: SourceType = Field(..., description="Type of actor (user or system)")
    id: str = Field(..., description="Unique identifier of the actor")


class Subject(BaseModel):
    type: SourceType = Field(..., description="Type of subject (user or system)")
    id: str = Field(..., description="Unique identifier of the subject")


class EventCreate(BaseModel):
    source_service: str
    event_type: str
    occurred_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    severity: EventSeverity = EventSeverity.INFO
    actor: Actor
    subject: Subject
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventOut(EventCreate):
    id: str


class PaginatedEventsOut(BaseModel):
    items: list[EventOut]
    total: int
    limit: int
    skip: int
    has_more: bool
