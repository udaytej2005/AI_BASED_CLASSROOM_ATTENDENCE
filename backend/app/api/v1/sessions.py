"""Attendance sessions: start, list, read, finalise and cancel.

Role summary:
- start / finalise / cancel: administrators, and the faculty member assigned to the period.
- read: administrators, principals and faculty.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, require_roles
from app.models.user import ROLE_ADMIN, ROLE_FACULTY, ROLE_PRINCIPAL, User
from app.schemas.sessions import SessionCancel, SessionOut, SessionStart
from app.services import sessions

router = APIRouter(tags=["attendance sessions"])

StartUser = Annotated[User, Depends(require_roles(ROLE_ADMIN, ROLE_FACULTY))]
ReadUser = Annotated[User, Depends(require_roles(ROLE_ADMIN, ROLE_PRINCIPAL, ROLE_FACULTY))]


@router.post(
    "/classes/{class_id}/sessions", response_model=SessionOut, status_code=201, summary="Start a session"
)
def start_session(
    class_id: int,
    db: DbSession,
    actor: StartUser,
    payload: SessionStart | None = None,
) -> SessionOut:
    return sessions.start_session(db, actor, class_id, payload or SessionStart())


@router.get("/sessions", response_model=list[SessionOut], summary="List attendance sessions")
def list_sessions(
    db: DbSession,
    _: ReadUser,
    class_id: Annotated[int | None, Query(ge=1)] = None,
    status: Annotated[str | None, Query(pattern="^(open|finalized|cancelled)$")] = None,
    on_date: date | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[SessionOut]:
    return sessions.list_sessions(db, class_id=class_id, status=status, on_date=on_date, limit=limit)


@router.get("/sessions/{session_id}", response_model=SessionOut, summary="Get one session")
def get_session(session_id: int, db: DbSession, _: ReadUser) -> SessionOut:
    return sessions.session_out(db, sessions.get_session(db, session_id))


@router.post("/sessions/{session_id}/finalize", response_model=SessionOut, summary="Finish a session")
def finalize_session(session_id: int, db: DbSession, actor: StartUser) -> SessionOut:
    return sessions.finalize_session(db, actor, session_id)


@router.post("/sessions/{session_id}/cancel", response_model=SessionOut, summary="Cancel an open session")
def cancel_session(session_id: int, payload: SessionCancel, db: DbSession, actor: StartUser) -> SessionOut:
    return sessions.cancel_session(db, actor, session_id, payload.reason)
