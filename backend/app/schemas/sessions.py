"""Attendance session request and response models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

SessionStatus = Literal["open", "finalized", "cancelled"]


class SessionStart(BaseModel):
    """Start a session. If ``timetable_entry_id`` is omitted the period active right now is used."""

    timetable_entry_id: int | None = Field(default=None, ge=1)
    camera_id: int | None = Field(default=None, ge=1)


class SessionCancel(BaseModel):
    reason: str = Field(min_length=3, max_length=200)


class SessionOut(BaseModel):
    id: int
    class_id: int
    class_name: str
    subject_id: int
    subject_code: str
    subject_name: str
    faculty_id: int
    faculty_name: str
    timetable_entry_id: int | None
    camera_id: int | None
    session_date: date
    period_label: str
    status: SessionStatus
    started_at: datetime
    ended_at: datetime | None
    note: str | None
