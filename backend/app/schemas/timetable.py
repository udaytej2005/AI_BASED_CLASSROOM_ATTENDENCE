"""Request and response models for subjects, rooms, classes, rosters, timetable entries and cameras."""

from __future__ import annotations

import re
from datetime import time
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Kind = Literal["class", "break", "free"]

_CODE = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,23}$")
# A stream reference is never a raw URL (which may embed credentials). It is one of:
#   env:NAME      an environment variable on the server that holds the stream URL (e.g. env:CAMERA_ROOM_101)
#   device:N      a local capture device index (webcam)
#   file:PATH     a recorded video under the project's data/ directory (relative path, no '..')
_STREAM_REF = re.compile(r"^(env:[A-Z][A-Z0-9_]{2,63}|device:\d{1,2}|file:(?!.*\.\.)[A-Za-z0-9_./-]{1,200})$")


def _upper_code(value: str) -> str:
    code = value.strip().upper()
    if not _CODE.fullmatch(code):
        raise ValueError("Use 2-24 letters, digits or hyphens.")
    return code


def _stream_reference(value: str) -> str:
    value = value.strip()
    if value.lower().startswith(("rtsp://", "http://", "https://", "rtmp://")):
        raise ValueError(
            "Raw stream URLs are not stored (they can contain passwords). Put the URL in a server "
            "environment variable and enter env:NAME here."
        )
    if not _STREAM_REF.fullmatch(value):
        raise ValueError("Use env:NAME, device:N or file:relative/path.mp4")
    return value


class SubjectCreate(BaseModel):
    code: str = Field(min_length=2, max_length=24)
    name: str = Field(min_length=2, max_length=120)

    @field_validator("code")
    @classmethod
    def _code(cls, value: str) -> str:
        return _upper_code(value)


class SubjectOut(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool


class RoomCreate(BaseModel):
    code: str = Field(min_length=2, max_length=24)
    name: str = Field(min_length=2, max_length=120)
    capacity: int | None = Field(default=None, ge=1, le=1000)

    @field_validator("code")
    @classmethod
    def _code(cls, value: str) -> str:
        return _upper_code(value)


class RoomOut(BaseModel):
    id: int
    code: str
    name: str
    capacity: int | None
    is_active: bool


class ClassCreate(BaseModel):
    department_id: int = Field(ge=1)
    year: int = Field(ge=1, le=6)
    section: str = Field(min_length=1, max_length=10)
    room_id: int | None = Field(default=None, ge=1)

    @field_validator("section")
    @classmethod
    def _section(cls, value: str) -> str:
        return value.strip().upper()


class ClassOut(BaseModel):
    id: int
    name: str
    department_id: int
    department_code: str
    year: int
    section: str
    room_id: int | None
    room_code: str | None
    is_active: bool
    roster_size: int


class RosterChange(BaseModel):
    add: list[int] = Field(default_factory=list, max_length=500)
    remove: list[int] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def _not_empty(self) -> RosterChange:
        if not self.add and not self.remove:
            raise ValueError("Provide student ids to add or remove.")
        return self


class RosterMember(BaseModel):
    student_id: int
    student_code: str
    full_name: str
    status: str


class TimetableCreate(BaseModel):
    kind: Kind = "class"
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    period_label: str = Field(min_length=1, max_length=40)
    class_id: int | None = Field(default=None, ge=1)
    subject_id: int | None = Field(default=None, ge=1)
    faculty_id: int | None = Field(default=None, ge=1)
    room_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _validate(self) -> TimetableCreate:
        if self.start_time >= self.end_time:
            raise ValueError("The start time must be before the end time.")
        if self.kind == "class" and (
            self.class_id is None or self.subject_id is None or self.faculty_id is None
        ):
            raise ValueError("A class period needs a class, a subject and a faculty member.")
        if self.kind == "free" and self.class_id is None:
            raise ValueError("A free period belongs to one class.")
        if self.kind in ("break", "free"):
            # Breaks and free periods do not carry a subject or faculty member.
            self.subject_id = None
            self.faculty_id = None
        return self


class TimetableOut(BaseModel):
    id: int
    kind: str
    day_of_week: int
    day_name: str
    start_time: str
    end_time: str
    period_label: str
    class_id: int | None
    class_name: str | None
    subject_id: int | None
    subject_code: str | None
    subject_name: str | None
    faculty_id: int | None
    faculty_name: str | None
    room_id: int | None
    room_code: str | None
    is_active: bool


class ActivePeriodOut(BaseModel):
    status: Literal["class", "break", "free", "none"]
    timezone: str
    local_date: str
    local_time: str
    period: TimetableOut | None = None


class CameraCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    room_id: int | None = Field(default=None, ge=1)
    stream_reference: str = Field(min_length=3, max_length=255)

    @field_validator("stream_reference")
    @classmethod
    def _reference(cls, value: str) -> str:
        return _stream_reference(value)


class CameraUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    room_id: int | None = Field(default=None, ge=1)
    stream_reference: str | None = Field(default=None, min_length=3, max_length=255)
    is_active: bool | None = None

    @field_validator("stream_reference")
    @classmethod
    def _reference(cls, value: str | None) -> str | None:
        return None if value is None else _stream_reference(value)


class CameraOut(BaseModel):
    id: int
    name: str
    room_id: int | None
    room_code: str | None
    status: str
    is_active: bool
    # Shown only to administrators; other roles see that a camera exists, not where it reads from.
    stream_reference: str | None
