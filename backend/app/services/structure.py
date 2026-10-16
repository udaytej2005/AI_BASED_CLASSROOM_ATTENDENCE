"""Subjects, rooms, classes, class rosters and cameras."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, Conflict, NotFound
from app.models.department import Department
from app.models.student import Student
from app.models.timetable import Camera, ClassGroup, ClassRosterEntry, Room, Subject
from app.models.user import User
from app.schemas.timetable import (
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
)
from app.services import audit


def _flush_or_conflict(db: Session, message: str) -> None:
    """Flush pending inserts so that unique-key races become a 409 rather than a 500."""
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict(message) from exc


def _commit_or_conflict(db: Session, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict(message) from exc


# ---------- subjects ----------


def subject_out(subject: Subject) -> SubjectOut:
    return SubjectOut(id=subject.id, code=subject.code, name=subject.name, is_active=subject.is_active)


def list_subjects(db: Session) -> list[SubjectOut]:
    return [subject_out(s) for s in db.scalars(select(Subject).order_by(Subject.code))]


def create_subject(db: Session, actor: User, data: SubjectCreate) -> SubjectOut:
    if db.scalar(select(Subject.id).where(Subject.code == data.code)) is not None:
        raise Conflict("A subject with this code already exists.")
    subject = Subject(code=data.code, name=data.name.strip(), is_active=True)
    db.add(subject)
    _flush_or_conflict(db, "A subject with this code already exists.")
    audit.record_audit(
        db, actor_user_id=actor.id, action="subject.created", entity="subject", entity_id=subject.id
    )
    _commit_or_conflict(db, "A subject with this code already exists.")
    db.refresh(subject)
    return subject_out(subject)


# ---------- rooms ----------


def room_out(room: Room) -> RoomOut:
    return RoomOut(
        id=room.id, code=room.code, name=room.name, capacity=room.capacity, is_active=room.is_active
    )


def list_rooms(db: Session) -> list[RoomOut]:
    return [room_out(r) for r in db.scalars(select(Room).order_by(Room.code))]


def create_room(db: Session, actor: User, data: RoomCreate) -> RoomOut:
    if db.scalar(select(Room.id).where(Room.code == data.code)) is not None:
        raise Conflict("A room with this code already exists.")
    room = Room(code=data.code, name=data.name.strip(), capacity=data.capacity, is_active=True)
    db.add(room)
    _flush_or_conflict(db, "A room with this code already exists.")
    audit.record_audit(db, actor_user_id=actor.id, action="room.created", entity="room", entity_id=room.id)
    _commit_or_conflict(db, "A room with this code already exists.")
    db.refresh(room)
    return room_out(room)


# ---------- classes ----------


def _roster_size(db: Session, class_id: int) -> int:
    return (
        db.scalar(
            select(func.count()).select_from(ClassRosterEntry).where(ClassRosterEntry.class_id == class_id)
        )
        or 0
    )


def _class_out(db: Session, cls: ClassGroup) -> ClassOut:
    department = db.get(Department, cls.department_id)
    room = db.get(Room, cls.room_id) if cls.room_id else None
    return ClassOut(
        id=cls.id,
        name=cls.name,
        department_id=cls.department_id,
        department_code=department.code if department else "",
        year=cls.year,
        section=cls.section,
        room_id=cls.room_id,
        room_code=room.code if room else None,
        is_active=cls.is_active,
        roster_size=_roster_size(db, cls.id),
    )


def list_classes(db: Session) -> list[ClassOut]:
    return [_class_out(db, c) for c in db.scalars(select(ClassGroup).order_by(ClassGroup.name))]


def get_class(db: Session, class_id: int) -> ClassOut:
    cls = db.get(ClassGroup, class_id)
    if cls is None:
        raise NotFound("Class")
    return _class_out(db, cls)


def create_class(db: Session, actor: User, data: ClassCreate) -> ClassOut:
    department = db.get(Department, data.department_id)
    if department is None or not department.is_active:
        raise AppError(422, "Department is unknown or inactive.")
    if data.room_id is not None:
        room = db.get(Room, data.room_id)
        if room is None or not room.is_active:
            raise AppError(422, "Room is unknown or inactive.")
    name = f"{department.code}-Y{data.year}-{data.section}"
    duplicate = db.scalar(
        select(ClassGroup.id).where(
            ClassGroup.department_id == data.department_id,
            ClassGroup.year == data.year,
            ClassGroup.section == data.section,
        )
    )
    if duplicate is not None:
        raise Conflict("A class with this department, year and section already exists.")
    cls = ClassGroup(
        name=name,
        department_id=data.department_id,
        year=data.year,
        section=data.section,
        room_id=data.room_id,
        is_active=True,
    )
    db.add(cls)
    _flush_or_conflict(db, "A class with this department, year and section already exists.")
    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="class.created",
        entity="class",
        entity_id=cls.id,
        details={"name": name},
    )
    _commit_or_conflict(db, "A class with this department, year and section already exists.")
    db.refresh(cls)
    return _class_out(db, cls)


def list_roster(db: Session, class_id: int) -> list[RosterMember]:
    if db.get(ClassGroup, class_id) is None:
        raise NotFound("Class")
    rows = db.execute(
        select(Student)
        .join(ClassRosterEntry, ClassRosterEntry.student_id == Student.id)
        .where(ClassRosterEntry.class_id == class_id)
        .order_by(Student.student_code)
    ).scalars()
    return [
        RosterMember(student_id=s.id, student_code=s.student_code, full_name=s.full_name, status=s.status)
        for s in rows
    ]


def change_roster(db: Session, actor: User, class_id: int, data: RosterChange) -> list[RosterMember]:
    cls = db.get(ClassGroup, class_id)
    if cls is None:
        raise NotFound("Class")
    wanted_add = sorted(set(data.add))
    wanted_remove = sorted(set(data.remove))
    if set(wanted_add) & set(wanted_remove):
        raise AppError(422, "A student cannot be added and removed in the same request.")

    if wanted_add:
        found = set(
            db.scalars(select(Student.id).where(Student.id.in_(wanted_add), Student.status == "active"))
        )
        missing = set(wanted_add) - found
        if missing:
            raise AppError(422, f"Unknown or inactive student id(s): {sorted(missing)}.")
        already = set(
            db.scalars(
                select(ClassRosterEntry.student_id).where(
                    ClassRosterEntry.class_id == class_id, ClassRosterEntry.student_id.in_(wanted_add)
                )
            )
        )
        for student_id in sorted(found - already):
            db.add(ClassRosterEntry(class_id=class_id, student_id=student_id))

    if wanted_remove:
        db.execute(
            delete(ClassRosterEntry).where(
                ClassRosterEntry.class_id == class_id, ClassRosterEntry.student_id.in_(wanted_remove)
            )
        )

    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="class.roster_changed",
        entity="class",
        entity_id=class_id,
        details={"added": len(wanted_add), "removed": len(wanted_remove)},
    )
    _commit_or_conflict(db, "The roster could not be saved. Try again.")
    return list_roster(db, class_id)


# ---------- cameras ----------


def _camera_out(db: Session, camera: Camera, viewer: User) -> CameraOut:
    room = db.get(Room, camera.room_id) if camera.room_id else None
    return CameraOut(
        id=camera.id,
        name=camera.name,
        room_id=camera.room_id,
        room_code=room.code if room else None,
        status=camera.status,
        is_active=camera.is_active,
        stream_reference=camera.stream_reference if viewer.role == "admin" else None,
    )


def list_cameras(db: Session, viewer: User) -> list[CameraOut]:
    return [_camera_out(db, c, viewer) for c in db.scalars(select(Camera).order_by(Camera.name))]


def create_camera(db: Session, actor: User, data: CameraCreate) -> CameraOut:
    if data.room_id is not None and db.get(Room, data.room_id) is None:
        raise AppError(422, "Room is unknown.")
    camera = Camera(name=data.name.strip(), room_id=data.room_id, stream_reference=data.stream_reference)
    db.add(camera)
    _flush_or_conflict(db, "A camera with this name already exists.")
    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="camera.created",
        entity="camera",
        entity_id=camera.id,
        details={"room_id": data.room_id},  # the stream reference itself is deliberately not logged
    )
    _commit_or_conflict(db, "A camera with this name already exists.")
    db.refresh(camera)
    return _camera_out(db, camera, actor)


def update_camera(db: Session, actor: User, camera_id: int, data: CameraUpdate) -> CameraOut:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise NotFound("Camera")
    changes = data.model_dump(exclude_unset=True)
    if "room_id" in changes and changes["room_id"] is not None and db.get(Room, changes["room_id"]) is None:
        raise AppError(422, "Room is unknown.")
    for field in ("name", "stream_reference", "is_active"):
        if field in changes and changes[field] is not None:
            setattr(
                camera, field, changes[field].strip() if isinstance(changes[field], str) else changes[field]
            )
    if "room_id" in changes:
        camera.room_id = changes["room_id"]
    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="camera.updated",
        entity="camera",
        entity_id=camera.id,
        details={"changed_fields": sorted(k for k in changes if k != "stream_reference")},
    )
    _commit_or_conflict(db, "A camera with this name already exists.")
    db.refresh(camera)
    return _camera_out(db, camera, actor)


def set_camera_status(db: Session, camera_id: int, status: str) -> None:
    """Called by the camera worker. Status values are 'unknown', 'online' or 'offline'."""
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise NotFound("Camera")
    camera.status = status
    db.commit()
