"""Subjects, rooms, classes, rosters, timetable and cameras.

Role summary:
- read academic structure (subjects, rooms, classes, timetable, active period): administrators, principals,
faculty.
- write academic structure and rosters: administrators.
- cameras: administrators and technical operators read status. Only administrators see stream
  references and write.
"""

from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import DbSession, require_roles
from app.models.timetable import TimetableEntry
from app.models.user import ROLE_ADMIN, ROLE_FACULTY, ROLE_PRINCIPAL, ROLE_TECHNICAL, User
from app.schemas.timetable import (
    ActivePeriodOut,
    CameraCreate,
    CameraOut,
    CameraUpdate,
    ClassCreate,
    ClassOut,
    RoomCreate,
    RoomOut,
    RosterChange,
    RosterMember,
    SubjectCreate,
    SubjectOut,
    TimetableCreate,
    TimetableOut,
)
from app.services import structure, timetable
from app.services.timetable import local_datetime, resolve_period

router = APIRouter(tags=["academic structure"])

AdminUser = Annotated[User, Depends(require_roles(ROLE_ADMIN))]
StaffUser = Annotated[User, Depends(require_roles(ROLE_ADMIN, ROLE_PRINCIPAL, ROLE_FACULTY))]
CameraReader = Annotated[User, Depends(require_roles(ROLE_ADMIN, ROLE_TECHNICAL))]


def _timetable_out(db: Session, entry: TimetableEntry) -> TimetableOut:
    return TimetableOut.model_validate(timetable.describe_entry(db, entry))


# ---------- subjects and rooms ----------


@router.get("/subjects", response_model=list[SubjectOut], summary="List subjects")
def list_subjects(db: DbSession, _: StaffUser) -> list[SubjectOut]:
    return structure.list_subjects(db)


@router.post("/subjects", response_model=SubjectOut, status_code=201, summary="Create a subject")
def create_subject(payload: SubjectCreate, db: DbSession, admin: AdminUser) -> SubjectOut:
    return structure.create_subject(db, admin, payload)


@router.get("/rooms", response_model=list[RoomOut], summary="List rooms")
def list_rooms(db: DbSession, _: StaffUser) -> list[RoomOut]:
    return structure.list_rooms(db)


@router.post("/rooms", response_model=RoomOut, status_code=201, summary="Create a room")
def create_room(payload: RoomCreate, db: DbSession, admin: AdminUser) -> RoomOut:
    return structure.create_room(db, admin, payload)


# ---------- classes and rosters ----------


@router.get("/classes", response_model=list[ClassOut], summary="List classes")
def list_classes(db: DbSession, _: StaffUser) -> list[ClassOut]:
    return structure.list_classes(db)


@router.post("/classes", response_model=ClassOut, status_code=201, summary="Create a class")
def create_class(payload: ClassCreate, db: DbSession, admin: AdminUser) -> ClassOut:
    return structure.create_class(db, admin, payload)


@router.get("/classes/{class_id}", response_model=ClassOut, summary="Get one class")
def get_class(class_id: int, db: DbSession, _: StaffUser) -> ClassOut:
    return structure.get_class(db, class_id)


@router.get("/classes/{class_id}/roster", response_model=list[RosterMember], summary="The class roster")
def get_roster(class_id: int, db: DbSession, _: StaffUser) -> list[RosterMember]:
    return structure.list_roster(db, class_id)


@router.patch(
    "/classes/{class_id}/roster", response_model=list[RosterMember], summary="Add or remove students"
)
def change_roster(
    class_id: int, payload: RosterChange, db: DbSession, admin: AdminUser
) -> list[RosterMember]:
    return structure.change_roster(db, admin, class_id, payload)


# ---------- timetable ----------


@router.get("/timetable", response_model=list[TimetableOut], summary="List timetable entries")
def list_timetable(
    db: DbSession,
    _: StaffUser,
    class_id: Annotated[int | None, Query(ge=1)] = None,
    day_of_week: Annotated[int | None, Query(ge=0, le=6)] = None,
    include_inactive: bool = False,
) -> list[TimetableOut]:
    entries = timetable.list_entries(
        db, class_id=class_id, day_of_week=day_of_week, include_inactive=include_inactive
    )
    return [_timetable_out(db, e) for e in entries]


@router.get(
    "/timetable/active", response_model=ActivePeriodOut, summary="The period active right now for a class"
)
def active_period(db: DbSession, _: StaffUser, class_id: Annotated[int, Query(ge=1)]) -> ActivePeriodOut:
    structure.get_class(db, class_id)  # raises 404 for unknown classes
    local = local_datetime()
    resolved = resolve_period(db, class_id)
    return ActivePeriodOut(
        status=cast(Literal["class", "break", "free", "none"], resolved.status),
        timezone=timetable.institution_zone().key,
        local_date=local.date().isoformat(),
        local_time=local.strftime("%H:%M"),
        period=_timetable_out(db, resolved.entry) if resolved.entry is not None else None,
    )


@router.post("/timetable", response_model=TimetableOut, status_code=201, summary="Add a timetable entry")
def create_timetable(payload: TimetableCreate, db: DbSession, admin: AdminUser) -> TimetableOut:
    entry = timetable.create_entry(db, admin, payload)
    return _timetable_out(db, entry)


@router.delete("/timetable/{entry_id}", response_model=TimetableOut, summary="Deactivate a timetable entry")
def deactivate_timetable(entry_id: int, db: DbSession, admin: AdminUser) -> TimetableOut:
    # Entries are deactivated, not deleted, because sessions and attendance refer to them.
    entry = timetable.deactivate_entry(db, admin, entry_id)
    return _timetable_out(db, entry)


# ---------- cameras ----------


@router.get("/cameras", response_model=list[CameraOut], summary="List authorised cameras")
def list_cameras(db: DbSession, viewer: CameraReader) -> list[CameraOut]:
    return structure.list_cameras(db, viewer)


@router.post("/cameras", response_model=CameraOut, status_code=201, summary="Register an authorised camera")
def create_camera(payload: CameraCreate, db: DbSession, admin: AdminUser) -> CameraOut:
    return structure.create_camera(db, admin, payload)


@router.patch("/cameras/{camera_id}", response_model=CameraOut, summary="Update a camera")
def update_camera(camera_id: int, payload: CameraUpdate, db: DbSession, admin: AdminUser) -> CameraOut:
    return structure.update_camera(db, admin, camera_id, payload)
