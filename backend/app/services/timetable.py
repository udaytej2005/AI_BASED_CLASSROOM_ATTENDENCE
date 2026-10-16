"""Timetable rules: conflict checks and resolution of the active period in the institutional timezone.

All "what is happening now" questions take an explicit ``now`` so that tests (and the attendance engine) can
pin
time. Times in the timetable are wall-clock times in ``settings.timezone``; they are never stored as UTC.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, Conflict, NotFound
from app.models.department import Department
from app.models.faculty import Faculty
from app.models.session import AttendanceSession
from app.models.timetable import ClassGroup, Room, Subject, TimetableEntry
from app.models.user import User
from app.schemas.timetable import TimetableCreate
from app.services import audit

DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def institution_zone() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def local_datetime(now: datetime | None = None) -> datetime:
    """``now`` (UTC if naive is assumed UTC) converted to the institutional timezone."""
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.astimezone(institution_zone())


@dataclass(frozen=True)
class ResolvedPeriod:
    """Outcome of asking "what is scheduled for this class right now?"."""

    status: str  # 'class' | 'break' | 'free' | 'none'
    entry: TimetableEntry | None
    session_date: date
    local_time: time


def resolve_period(db: Session, class_id: int, now: datetime | None = None) -> ResolvedPeriod:
    local = local_datetime(now)
    today = local.date()
    moment = local.time().replace(microsecond=0)
    base = [
        TimetableEntry.day_of_week == local.weekday(),
        TimetableEntry.is_active.is_(True),
        TimetableEntry.start_time <= moment,
        TimetableEntry.end_time > moment,
    ]
    # A class period for this class wins.
    entry = db.scalar(
        select(TimetableEntry).where(
            TimetableEntry.kind == "class", TimetableEntry.class_id == class_id, *base
        )
    )
    if entry is not None:
        return ResolvedPeriod("class", entry, today, moment)
    # Otherwise a break (for all classes) or a class-specific free period.
    other = db.scalar(
        select(TimetableEntry).where(
            TimetableEntry.kind.in_(("break", "free")),
            (TimetableEntry.class_id.is_(None)) | (TimetableEntry.class_id == class_id),
            *base,
        )
    )
    if other is not None:
        return ResolvedPeriod(other.kind, other, today, moment)
    return ResolvedPeriod("none", None, today, moment)


def _overlaps(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    return a_start < b_end and b_start < a_end


def check_no_conflict(
    db: Session,
    *,
    kind: str,
    day_of_week: int,
    start: time,
    end: time,
    class_id: int | None,
    faculty_id: int | None,
    room_id: int | None,
    exclude_id: int | None = None,
) -> None:
    """Reject overlapping slots that share a class, a faculty member or a room on the same weekday.

    A global break (class_id NULL) conflicts with every class on that day. A class-specific free period
    conflicts with that class only.
    """
    statement = select(TimetableEntry).where(
        TimetableEntry.day_of_week == day_of_week,
        TimetableEntry.is_active.is_(True),
    )
    if exclude_id is not None:
        statement = statement.where(TimetableEntry.id != exclude_id)
    for other in db.scalars(statement):
        if not _overlaps(start, end, other.start_time, other.end_time):
            continue
        same_class = class_id is None or other.class_id is None or other.class_id == class_id
        same_faculty = faculty_id is not None and other.faculty_id == faculty_id
        same_room = room_id is not None and other.room_id == room_id
        if kind == "break" or other.kind == "break":
            # A break blocks all classes. Two breaks may not overlap either.
            if class_id is None or other.class_id is None or same_class:
                raise Conflict(
                    f"This time overlaps the {other.period_label} entry for the same class or all classes."
                )
            continue
        if same_class or same_faculty or same_room:
            reason = "class" if same_class else ("faculty member" if same_faculty else "room")
            raise Conflict(f"This time overlaps {other.period_label} for the same {reason}.")


def _load_refs(db: Session, data: TimetableCreate) -> None:
    if data.class_id is not None and db.get(ClassGroup, data.class_id) is None:
        raise NotFound("Class")
    if data.subject_id is not None and db.get(Subject, data.subject_id) is None:
        raise NotFound("Subject")
    if data.faculty_id is not None:
        member = db.get(Faculty, data.faculty_id)
        if member is None or member.status != "active":
            raise AppError(422, "Faculty member is unknown or inactive.")
    if data.room_id is not None:
        room = db.get(Room, data.room_id)
        if room is None or not room.is_active:
            raise AppError(422, "Room is unknown or inactive.")


def create_entry(db: Session, actor: User, data: TimetableCreate) -> TimetableEntry:
    _load_refs(db, data)
    check_no_conflict(
        db,
        kind=data.kind,
        day_of_week=data.day_of_week,
        start=data.start_time,
        end=data.end_time,
        class_id=data.class_id,
        faculty_id=data.faculty_id,
        room_id=data.room_id,
    )
    entry = TimetableEntry(**data.model_dump())
    db.add(entry)
    db.flush()
    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="timetable.created",
        entity="timetable_entry",
        entity_id=entry.id,
        details={"kind": entry.kind, "day_of_week": entry.day_of_week, "class_id": entry.class_id},
    )
    db.commit()
    db.refresh(entry)
    return entry


def deactivate_entry(db: Session, actor: User, entry_id: int) -> TimetableEntry:
    entry = db.get(TimetableEntry, entry_id)
    if entry is None:
        raise NotFound("Timetable entry")
    if entry.is_active:
        entry.is_active = False
        audit.record_audit(
            db,
            actor_user_id=actor.id,
            action="timetable.deactivated",
            entity="timetable_entry",
            entity_id=entry.id,
        )
        db.commit()
        db.refresh(entry)
    return entry


def list_entries(
    db: Session,
    *,
    class_id: int | None = None,
    day_of_week: int | None = None,
    include_inactive: bool = False,
) -> list[TimetableEntry]:
    statement = select(TimetableEntry).order_by(
        TimetableEntry.day_of_week, TimetableEntry.start_time, TimetableEntry.id
    )
    if class_id is not None:
        statement = statement.where(
            (TimetableEntry.class_id == class_id) | (TimetableEntry.class_id.is_(None))
        )
    if day_of_week is not None:
        statement = statement.where(TimetableEntry.day_of_week == day_of_week)
    if not include_inactive:
        statement = statement.where(TimetableEntry.is_active.is_(True))
    return list(db.scalars(statement))


def describe_entry(db: Session, entry: TimetableEntry) -> dict[str, object]:
    """Human-readable names for an entry (used by responses; never exposes internal secrets)."""
    cls = db.get(ClassGroup, entry.class_id) if entry.class_id else None
    subject = db.get(Subject, entry.subject_id) if entry.subject_id else None
    faculty = db.get(Faculty, entry.faculty_id) if entry.faculty_id else None
    room = db.get(Room, entry.room_id) if entry.room_id else None
    return {
        "id": entry.id,
        "kind": entry.kind,
        "day_of_week": entry.day_of_week,
        "day_name": DAY_NAMES[entry.day_of_week],
        "start_time": entry.start_time.strftime("%H:%M"),
        "end_time": entry.end_time.strftime("%H:%M"),
        "period_label": entry.period_label,
        "class_id": entry.class_id,
        "class_name": cls.name if cls else None,
        "subject_id": entry.subject_id,
        "subject_code": subject.code if subject else None,
        "subject_name": subject.name if subject else None,
        "faculty_id": entry.faculty_id,
        "faculty_name": faculty.full_name if faculty else None,
        "room_id": entry.room_id,
        "room_code": room.code if room else None,
        "is_active": entry.is_active,
    }


def session_exists_for(db: Session, entry_id: int, session_date: date) -> AttendanceSession | None:
    return db.scalar(
        select(AttendanceSession).where(
            AttendanceSession.timetable_entry_id == entry_id,
            AttendanceSession.session_date == session_date,
        )
    )


def department_code(db: Session, department_id: int) -> str:
    department = db.get(Department, department_id)
    return department.code if department else ""
