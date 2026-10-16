"""Attendance-session lifecycle: start (only inside an active class period), finalise, cancel.

Rules enforced here, not in the UI:
- Only administrators and the faculty member assigned to the period may start, finalise or cancel a session.
- A session can start only while its timetable period is active in the institutional timezone.
- One session per timetable period per date. A second start returns the existing session's id.
- A finalised or cancelled session is never reopened. Corrections are made to attendance rows (Phase 5), not
here.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, Conflict, Forbidden, NotFound
from app.models.faculty import Faculty
from app.models.session import AttendanceSession
from app.models.timetable import Camera, ClassGroup, Subject, TimetableEntry
from app.models.user import ROLE_ADMIN, ROLE_FACULTY, User
from app.schemas.sessions import SessionOut, SessionStart, SessionStatus
from app.services import audit
from app.services.timetable import resolve_period


def _as_utc(moment: datetime | None) -> datetime:
    current = moment or datetime.now(UTC)
    return current.replace(tzinfo=UTC) if current.tzinfo is None else current.astimezone(UTC)


def session_out(db: Session, session: AttendanceSession) -> SessionOut:
    cls = db.get(ClassGroup, session.class_id)
    subject = db.get(Subject, session.subject_id)
    faculty = db.get(Faculty, session.faculty_id)
    return SessionOut(
        id=session.id,
        class_id=session.class_id,
        class_name=cls.name if cls else "",
        subject_id=session.subject_id,
        subject_code=subject.code if subject else "",
        subject_name=subject.name if subject else "",
        faculty_id=session.faculty_id,
        faculty_name=faculty.full_name if faculty else "",
        timetable_entry_id=session.timetable_entry_id,
        camera_id=session.camera_id,
        session_date=session.session_date,
        period_label=session.period_label,
        status=cast(SessionStatus, session.status),  # the database check constraint limits the values
        started_at=session.started_at,
        ended_at=session.ended_at,
        note=session.note,
    )


def _faculty_profile(db: Session, user: User) -> Faculty | None:
    return db.scalar(select(Faculty).where(Faculty.user_id == user.id))


def _may_manage(db: Session, user: User, session: AttendanceSession) -> bool:
    if user.role == ROLE_ADMIN:
        return True
    if user.role == ROLE_FACULTY:
        profile = _faculty_profile(db, user)
        return profile is not None and profile.id == session.faculty_id
    return False


def get_session(db: Session, session_id: int) -> AttendanceSession:
    session = db.get(AttendanceSession, session_id)
    if session is None:
        raise NotFound("Session")
    return session


def start_session(
    db: Session, actor: User, class_id: int, data: SessionStart, now: datetime | None = None
) -> SessionOut:
    cls = db.get(ClassGroup, class_id)
    if cls is None or not cls.is_active:
        raise NotFound("Class")

    profile = _faculty_profile(db, actor) if actor.role == ROLE_FACULTY else None
    if actor.role == ROLE_FACULTY and profile is None:
        raise Forbidden("Your account is not linked to a faculty profile.")

    moment = _as_utc(now)
    resolved = resolve_period(db, class_id, moment)
    if data.timetable_entry_id is not None:
        entry = db.get(TimetableEntry, data.timetable_entry_id)
        if entry is None or entry.class_id != class_id or entry.kind != "class":
            raise AppError(422, "That timetable entry is not a class period for this class.")
        if resolved.entry is None or resolved.entry.id != entry.id:
            raise Conflict("That period is not active right now.")
    else:
        if resolved.status != "class" or resolved.entry is None:
            if resolved.status == "none":
                raise Conflict(
                    f"No class is scheduled for this class at {resolved.local_time.strftime('%H:%M')}."
                )
            raise Conflict(
                f"It is currently a {resolved.status} period for this class. Nothing can be started."
            )
        entry = resolved.entry

    if profile is not None and entry.faculty_id != profile.id:
        raise Forbidden("This period is assigned to another faculty member.")

    existing = db.scalar(
        select(AttendanceSession).where(
            AttendanceSession.timetable_entry_id == entry.id,
            AttendanceSession.session_date == resolved.session_date,
        )
    )
    if existing is not None:
        raise Conflict(
            f"A session for this period already exists (session {existing.id}, {existing.status})."
        )

    if data.camera_id is not None:
        camera = db.get(Camera, data.camera_id)
        if camera is None or not camera.is_active:
            raise AppError(422, "Camera is unknown or inactive.")
        if camera.room_id is not None and entry.room_id is not None and camera.room_id != entry.room_id:
            raise AppError(422, "This camera is mapped to a different room from the timetable entry.")

    session = AttendanceSession(
        class_id=class_id,
        subject_id=entry.subject_id,
        faculty_id=entry.faculty_id,
        timetable_entry_id=entry.id,
        camera_id=data.camera_id,
        session_date=resolved.session_date,
        period_label=entry.period_label,
        status="open",
        started_at=moment,
        started_by_user_id=actor.id,
    )
    db.add(session)
    try:
        db.flush()
    except IntegrityError as exc:  # two requests raced for the same period
        db.rollback()
        raise Conflict("A session for this period was just started by someone else.") from exc
    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="session.started",
        entity="attendance_session",
        entity_id=session.id,
        details={"class_id": class_id, "timetable_entry_id": entry.id, "date": str(resolved.session_date)},
    )
    db.commit()
    db.refresh(session)
    return session_out(db, session)


def finalize_session(db: Session, actor: User, session_id: int, now: datetime | None = None) -> SessionOut:
    session = get_session(db, session_id)
    if not _may_manage(db, actor, session):
        raise Forbidden("Only the assigned faculty member or an administrator can finish this session.")
    if session.status != "open":
        raise Conflict(f"Session is already {session.status}.")
    session.status = "finalized"
    session.ended_at = _as_utc(now)
    session.ended_by_user_id = actor.id
    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="session.finalized",
        entity="attendance_session",
        entity_id=session.id,
    )
    db.commit()
    db.refresh(session)
    return session_out(db, session)


def cancel_session(
    db: Session, actor: User, session_id: int, reason: str, now: datetime | None = None
) -> SessionOut:
    session = get_session(db, session_id)
    if not _may_manage(db, actor, session):
        raise Forbidden("Only the assigned faculty member or an administrator can cancel this session.")
    if session.status != "open":
        raise Conflict(f"Session is already {session.status}.")
    session.status = "cancelled"
    session.ended_at = _as_utc(now)
    session.ended_by_user_id = actor.id
    session.note = reason.strip()
    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="session.cancelled",
        entity="attendance_session",
        entity_id=session.id,
    )
    db.commit()
    db.refresh(session)
    return session_out(db, session)


def list_sessions(
    db: Session,
    *,
    class_id: int | None = None,
    status: str | None = None,
    on_date: date | None = None,
    limit: int = 100,
) -> list[SessionOut]:
    statement = select(AttendanceSession).order_by(
        AttendanceSession.session_date.desc(), AttendanceSession.id.desc()
    )
    if class_id is not None:
        statement = statement.where(AttendanceSession.class_id == class_id)
    if status is not None:
        statement = statement.where(AttendanceSession.status == status)
    if on_date is not None:
        statement = statement.where(AttendanceSession.session_date == on_date)
    rows = db.scalars(statement.limit(limit)).all()
    return [session_out(db, s) for s in rows]


def current_session_for_class(db: Session, class_id: int) -> AttendanceSession | None:
    """The open session for the class (if any). Used by the live dashboard."""
    return db.scalar(
        select(AttendanceSession)
        .where(AttendanceSession.class_id == class_id, AttendanceSession.status == "open")
        .order_by(AttendanceSession.id.desc())
    )
