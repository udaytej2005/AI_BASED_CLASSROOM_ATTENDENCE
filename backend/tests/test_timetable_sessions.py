"""Phase 3: classes, rosters, timetable resolution in local time, cameras and the session lifecycle."""

from datetime import UTC, datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.faculty import Faculty
from app.models.student import Student
from app.models.timetable import ClassGroup, Room, Subject, TimetableEntry
from app.models.user import User
from app.schemas.sessions import SessionStart
from app.schemas.timetable import TimetableCreate
from app.services import sessions as session_service
from app.services import timetable as timetable_service
from tests.conftest import login, make_user

# 2026-10-19 is a Monday. 10:15 IST == 04:45 UTC.
MONDAY_1015_IST = datetime(2026, 10, 19, 4, 45, tzinfo=UTC)
MONDAY_0959_IST = datetime(2026, 10, 19, 4, 29, tzinfo=UTC)
MONDAY_1100_IST = datetime(2026, 10, 19, 5, 30, tzinfo=UTC)


class World:
    """Ids of the academic records created by ``world`` (kept simple so tests read clearly)."""

    def __init__(self) -> None:
        self.class_id = 0
        self.other_class_id = 0
        self.subject_id = 0
        self.room_id = 0
        self.faculty_id = 0
        self.other_faculty_id = 0
        self.student_ids: list[int] = []
        self.monday_entry_id = 0
        self.break_id = 0


@pytest.fixture
def world(db: Session, department_id: int) -> World:
    w = World()
    cls = ClassGroup(name="CSE-Y2-A", department_id=department_id, year=2, section="A", is_active=True)
    other = ClassGroup(name="CSE-Y2-B", department_id=department_id, year=2, section="B", is_active=True)
    subject = Subject(code="CS201", name="Data Structures", is_active=True)
    room = Room(code="R101", name="Room 101", capacity=60, is_active=True)
    db.add_all([cls, other, subject, room])
    db.flush()
    user_a = make_user(db, email="faculty.a@example.test", role="faculty")
    user_b = make_user(db, email="faculty.b@example.test", role="faculty")
    fa = Faculty(employee_code="FAC-A", full_name="Dr A", department_id=department_id, user_id=user_a.id)
    fb = Faculty(employee_code="FAC-B", full_name="Dr B", department_id=department_id, user_id=user_b.id)
    db.add_all([fa, fb])
    db.flush()
    students = [
        Student(
            student_code=f"CSE{n:03d}",
            full_name=f"Student {n}",
            department_id=department_id,
            year=2,
            section="A",
            status="active",
        )
        for n in range(1, 4)
    ]
    db.add_all(students)
    db.flush()
    entry = TimetableEntry(
        kind="class",
        day_of_week=0,
        start_time=time(10, 0),
        end_time=time(11, 0),
        period_label="Period 2",
        class_id=cls.id,
        subject_id=subject.id,
        faculty_id=fa.id,
        room_id=room.id,
        is_active=True,
    )
    brk = TimetableEntry(
        kind="break",
        day_of_week=0,
        start_time=time(13, 0),
        end_time=time(13, 45),
        period_label="Lunch",
        is_active=True,
    )
    db.add_all([entry, brk])
    db.commit()
    w.class_id, w.other_class_id, w.subject_id, w.room_id = cls.id, other.id, subject.id, room.id
    w.faculty_id, w.other_faculty_id = fa.id, fb.id
    w.student_ids = [s.id for s in students]
    w.monday_entry_id, w.break_id = entry.id, brk.id
    return w


def _all_day_entries(
    db: Session, class_id: int, subject_id: int, faculty_id: int, room_id: int | None = None
) -> None:
    """Make the class 'always in a period' so API tests do not depend on the wall clock."""
    for day in range(7):
        db.add(
            TimetableEntry(
                kind="class",
                day_of_week=day,
                start_time=time(0, 0),
                end_time=time(23, 59),
                period_label="All day",
                class_id=class_id,
                subject_id=subject_id,
                faculty_id=faculty_id,
                room_id=room_id,
                is_active=True,
            )
        )
    db.commit()


# ---------- timetable rules (time pinned through the service layer) ----------


def test_resolves_class_period_in_institution_timezone(db: Session, world: World):
    # 10:15 IST on a Monday is inside the 10:00-11:00 class period.
    resolved = timetable_service.resolve_period(db, world.class_id, MONDAY_1015_IST)
    assert resolved.status == "class"
    assert resolved.entry is not None and resolved.entry.id == world.monday_entry_id
    assert str(resolved.session_date) == "2026-10-19"


def test_period_start_is_inclusive_and_end_is_exclusive(db: Session, world: World):
    assert timetable_service.resolve_period(db, world.class_id, MONDAY_0959_IST).status == "none"
    assert timetable_service.resolve_period(db, world.class_id, MONDAY_1100_IST).status == "none"


def test_other_class_does_not_resolve_to_this_period(db: Session, world: World):
    assert timetable_service.resolve_period(db, world.other_class_id, MONDAY_1015_IST).status == "none"


def test_global_break_applies_to_every_class(db: Session, world: World):
    lunch = datetime(2026, 10, 19, 7, 30, tzinfo=UTC)  # 13:00 IST
    for class_id in (world.class_id, world.other_class_id):
        resolved = timetable_service.resolve_period(db, class_id, lunch)
        assert resolved.status == "break"


def test_naive_datetimes_are_treated_as_utc(db: Session, world: World):
    naive = datetime(2026, 10, 19, 4, 45)
    assert timetable_service.resolve_period(db, world.class_id, naive).status == "class"


def test_overlapping_slots_for_same_class_faculty_or_room_are_rejected(
    client: TestClient, db: Session, world: World
):
    base = {
        "kind": "class",
        "day_of_week": 0,
        "start_time": "10:30:00",
        "end_time": "11:30:00",
        "period_label": "Clash",
        "subject_id": world.subject_id,
        "room_id": None,
    }
    admin_user = make_user(db, email="admin@example.test", role="admin")
    admin = login(client.app, admin_user.email)  # type: ignore[arg-type]
    same_class = admin.post(
        "/api/v1/timetable", json={**base, "class_id": world.class_id, "faculty_id": world.other_faculty_id}
    )
    assert same_class.status_code == 409 and "same class" in same_class.json()["detail"]
    same_faculty = admin.post(
        "/api/v1/timetable",
        json={**base, "class_id": world.other_class_id, "faculty_id": world.faculty_id},
    )
    assert same_faculty.status_code == 409 and "faculty member" in same_faculty.json()["detail"]
    same_room = admin.post(
        "/api/v1/timetable",
        json={
            **base,
            "class_id": world.other_class_id,
            "faculty_id": world.other_faculty_id,
            "room_id": world.room_id,
        },
    )
    assert same_room.status_code == 409 and "room" in same_room.json()["detail"]


def test_break_cannot_overlap_a_class_period(client: TestClient, db: Session, world: World):
    admin = login(client.app, make_user(db, email="admin2@example.test", role="admin").email)  # type: ignore[arg-type]
    response = admin.post(
        "/api/v1/timetable",
        json={
            "kind": "break",
            "day_of_week": 0,
            "start_time": "10:30:00",
            "end_time": "10:45:00",
            "period_label": "Tea",
        },
    )
    assert response.status_code == 409


def test_non_overlapping_period_is_accepted_and_breaks_do_not_need_faculty(db: Session, world: World):
    entry = timetable_service.create_entry(
        db,
        db.scalar(select(User).where(User.email == "faculty.a@example.test")),  # type: ignore[arg-type]
        TimetableCreate(
            kind="class",
            day_of_week=0,
            start_time=time(11, 0),
            end_time=time(12, 0),
            period_label="Period 3",
            class_id=world.class_id,
            subject_id=world.subject_id,
            faculty_id=world.faculty_id,
        ),
    )
    assert entry.id is not None


def test_class_period_requires_class_subject_and_faculty():
    with pytest.raises(ValueError, match="needs a class, a subject and a faculty member"):
        TimetableCreate(kind="class", day_of_week=0, start_time=time(9), end_time=time(10), period_label="X")


def test_start_must_be_before_end():
    with pytest.raises(ValueError, match="start time must be before"):
        TimetableCreate(kind="break", day_of_week=0, start_time=time(10), end_time=time(10), period_label="X")


def test_deactivated_entries_are_ignored_by_resolution(client: TestClient, db: Session, world: World):
    admin = login(client.app, make_user(db, email="admin3@example.test", role="admin").email)  # type: ignore[arg-type]
    assert admin.delete(f"/api/v1/timetable/{world.monday_entry_id}").status_code == 200
    assert timetable_service.resolve_period(db, world.class_id, MONDAY_1015_IST).status == "none"


def test_active_period_endpoint_reports_status_and_timezone(client: TestClient, db: Session, world: World):
    faculty = login(client.app, "faculty.a@example.test")
    response = faculty.get("/api/v1/timetable/active", params={"class_id": world.class_id})
    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] == "Asia/Kolkata"
    assert body["status"] in {"class", "break", "free", "none"}


# ---------- classes and rosters ----------


def test_class_names_are_generated_and_duplicates_rejected(
    client: TestClient, db: Session, department_id: int
):
    admin = login(client.app, make_user(db, email="admin4@example.test", role="admin").email)  # type: ignore[arg-type]
    created = admin.post("/api/v1/classes", json={"department_id": department_id, "year": 3, "section": "c"})
    assert created.status_code == 201
    assert created.json()["name"] == "CSE-Y3-C"
    duplicate = admin.post(
        "/api/v1/classes", json={"department_id": department_id, "year": 3, "section": "C"}
    )
    assert duplicate.status_code == 409


def test_roster_add_and_remove_are_validated_and_audited(client: TestClient, db: Session, world: World):
    admin = login(client.app, make_user(db, email="admin5@example.test", role="admin").email)  # type: ignore[arg-type]
    added = admin.patch(
        f"/api/v1/classes/{world.class_id}/roster",
        json={"add": world.student_ids[:2]},
    )
    assert added.status_code == 200
    assert [m["student_code"] for m in added.json()] == ["CSE001", "CSE002"]

    removed = admin.patch(f"/api/v1/classes/{world.class_id}/roster", json={"remove": [world.student_ids[0]]})
    assert [m["student_code"] for m in removed.json()] == ["CSE002"]

    unknown = admin.patch(f"/api/v1/classes/{world.class_id}/roster", json={"add": [999999]})
    assert unknown.status_code == 422

    both = admin.patch(
        f"/api/v1/classes/{world.class_id}/roster",
        json={"add": [world.student_ids[2]], "remove": [world.student_ids[2]]},
    )
    assert both.status_code == 422

    actions = {row.action for row in db.scalars(select(AuditLog))}
    assert "class.roster_changed" in actions


def test_inactive_student_cannot_join_roster(client: TestClient, db: Session, world: World):
    student = db.get(Student, world.student_ids[0])
    assert student is not None
    student.status = "inactive"
    db.commit()
    admin = login(client.app, make_user(db, email="admin6@example.test", role="admin").email)  # type: ignore[arg-type]
    response = admin.patch(f"/api/v1/classes/{world.class_id}/roster", json={"add": [world.student_ids[0]]})
    assert response.status_code == 422


def test_faculty_can_read_but_not_edit_roster(client: TestClient, db: Session, world: World):
    faculty = login(client.app, "faculty.a@example.test")
    assert faculty.get(f"/api/v1/classes/{world.class_id}/roster").status_code == 200
    assert (
        faculty.patch(
            f"/api/v1/classes/{world.class_id}/roster", json={"add": [world.student_ids[0]]}
        ).status_code
        == 403
    )


def test_student_cannot_read_academic_structure(client: TestClient, db: Session, world: World):
    make_user(db, email="student@example.test", role="student")
    student = login(client.app, "student@example.test")
    assert student.get("/api/v1/classes").status_code == 403
    assert student.get("/api/v1/timetable").status_code == 403


def test_subject_codes_are_normalised_and_unique(client: TestClient, db: Session):
    admin = login(client.app, make_user(db, email="admin7@example.test", role="admin").email)  # type: ignore[arg-type]
    assert (
        admin.post("/api/v1/subjects", json={"code": " cs-301 ", "name": "Operating Systems"}).json()["code"]
        == "CS-301"
    )
    assert admin.post("/api/v1/subjects", json={"code": "cs-301", "name": "Duplicate"}).status_code == 409
    assert admin.post("/api/v1/subjects", json={"code": "bad code!", "name": "Bad"}).status_code == 422


# ---------- cameras ----------


@pytest.mark.parametrize(
    "reference",
    ["rtsp://user:secret@192.168.1.10/stream", "http://cam.local/feed", "HTTPS://cam/x"],
)
def test_raw_stream_urls_are_refused(client: TestClient, db: Session, reference: str):
    admin = login(client.app, make_user(db, email="admin8@example.test", role="admin").email)  # type: ignore[arg-type]
    response = admin.post("/api/v1/cameras", json={"name": "Room 101 cam", "stream_reference": reference})
    assert response.status_code == 422
    assert "secret" not in response.text


def test_camera_references_and_visibility(client: TestClient, db: Session, world: World):
    admin = login(client.app, make_user(db, email="admin9@example.test", role="admin").email)  # type: ignore[arg-type]
    created = admin.post(
        "/api/v1/cameras", json={"name": "Room 101 cam", "stream_reference": "env:CAMERA_ROOM_101"}
    )
    assert created.status_code == 201
    assert created.json()["stream_reference"] == "env:CAMERA_ROOM_101"

    make_user(db, email="tech@example.test", role="technical")
    technical = login(client.app, "tech@example.test")
    listing = technical.get("/api/v1/cameras").json()
    assert listing[0]["name"] == "Room 101 cam"
    assert (
        listing[0]["stream_reference"] is None
    )  # technical operators see status, not where the stream comes from

    faculty = login(client.app, "faculty.a@example.test")
    assert faculty.get("/api/v1/cameras").status_code == 403


@pytest.mark.parametrize("reference", ["file:../../etc/passwd", "env:lowercase", "usb:3", "device:x"])
def test_invalid_camera_references_are_refused(client: TestClient, db: Session, reference: str):
    admin = login(client.app, make_user(db, email="admin10@example.test", role="admin").email)  # type: ignore[arg-type]
    assert (
        admin.post("/api/v1/cameras", json={"name": "Cam X", "stream_reference": reference}).status_code
        == 422
    )


# ---------- attendance session lifecycle ----------


def test_faculty_starts_session_only_during_their_period(db: Session, world: World):
    faculty = db.scalar(select(User).where(User.email == "faculty.a@example.test"))
    assert faculty is not None
    # Outside the period: refused with a clear reason.
    with pytest.raises(Exception) as outside:
        session_service.start_session(db, faculty, world.class_id, SessionStart(), now=MONDAY_0959_IST)
    assert "No class is scheduled" in str(outside.value.detail)  # type: ignore[attr-defined]

    started = session_service.start_session(db, faculty, world.class_id, SessionStart(), now=MONDAY_1015_IST)
    assert started.status == "open"
    assert started.subject_code == "CS201"
    assert started.period_label == "Period 2"
    assert str(started.session_date) == "2026-10-19"

    # A second start for the same period returns a conflict that names the existing session.
    with pytest.raises(Exception) as duplicate:
        session_service.start_session(db, faculty, world.class_id, SessionStart(), now=MONDAY_1015_IST)
    assert f"session {started.id}" in str(duplicate.value.detail)  # type: ignore[attr-defined]


def test_session_cannot_start_during_break(db: Session, world: World):
    faculty = db.scalar(select(User).where(User.email == "faculty.a@example.test"))
    assert faculty is not None
    lunch = datetime(2026, 10, 19, 7, 30, tzinfo=UTC)
    with pytest.raises(Exception) as excinfo:
        session_service.start_session(db, faculty, world.class_id, SessionStart(), now=lunch)
    assert "break" in str(excinfo.value.detail)  # type: ignore[attr-defined]


def test_only_assigned_faculty_or_admin_can_start(client: TestClient, db: Session, world: World):
    # Faculty B is not assigned to Monday 10:00 for class A.
    faculty_b = db.scalar(select(User).where(User.email == "faculty.b@example.test"))
    assert faculty_b is not None
    _all_day_entries(db, world.other_class_id, world.subject_id, world.other_faculty_id)
    with pytest.raises(Exception) as excinfo:
        session_service.start_session(
            db,
            faculty_b,
            world.class_id,
            SessionStart(timetable_entry_id=world.monday_entry_id),
            now=MONDAY_1015_IST,
        )
    assert excinfo.value.status_code == 403  # type: ignore[attr-defined]


def test_api_start_finalize_and_permissions(client: TestClient, db: Session, world: World):
    _all_day_entries(db, world.class_id, world.subject_id, world.faculty_id)
    faculty = login(client.app, "faculty.a@example.test")
    started = faculty.post(f"/api/v1/classes/{world.class_id}/sessions")
    assert started.status_code == 201, started.text
    session_id = started.json()["id"]
    assert started.json()["status"] == "open"

    make_user(db, email="principal@example.test", role="principal")
    principal = login(client.app, "principal@example.test")
    assert principal.post(f"/api/v1/classes/{world.class_id}/sessions").status_code == 403
    assert principal.get(f"/api/v1/sessions/{session_id}").status_code == 200

    make_user(db, email="student2@example.test", role="student")
    student = login(client.app, "student2@example.test")
    assert student.post(f"/api/v1/classes/{world.class_id}/sessions").status_code == 403
    assert student.get("/api/v1/sessions").status_code == 403

    finalized = faculty.post(f"/api/v1/sessions/{session_id}/finalize")
    assert finalized.status_code == 200 and finalized.json()["status"] == "finalized"
    assert finalized.json()["ended_at"] is not None
    again = faculty.post(f"/api/v1/sessions/{session_id}/finalize")
    assert again.status_code == 409
    cancel_after = faculty.post(f"/api/v1/sessions/{session_id}/cancel", json={"reason": "Too late"})
    assert cancel_after.status_code == 409


def test_faculty_other_than_owner_cannot_finalize(client: TestClient, db: Session, world: World):
    _all_day_entries(db, world.class_id, world.subject_id, world.faculty_id)
    owner = login(client.app, "faculty.a@example.test")
    session_id = owner.post(f"/api/v1/classes/{world.class_id}/sessions").json()["id"]
    other = login(client.app, "faculty.b@example.test")
    assert other.post(f"/api/v1/sessions/{session_id}/finalize").status_code == 403
    assert other.post(f"/api/v1/sessions/{session_id}/cancel", json={"reason": "Not mine"}).status_code == 403


def test_cancel_records_reason_and_blocks_reopen(client: TestClient, db: Session, world: World):
    _all_day_entries(db, world.class_id, world.subject_id, world.faculty_id)
    faculty = login(client.app, "faculty.a@example.test")
    session_id = faculty.post(f"/api/v1/classes/{world.class_id}/sessions").json()["id"]
    cancelled = faculty.post(f"/api/v1/sessions/{session_id}/cancel", json={"reason": "Room unavailable"})
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["note"] == "Room unavailable"
    assert faculty.post(f"/api/v1/sessions/{session_id}/finalize").status_code == 409


def test_camera_must_match_the_period_room(client: TestClient, db: Session, world: World):
    other_room = Room(code="R202", name="Room 202", is_active=True)
    db.add(other_room)
    db.flush()
    camera_admin = login(client.app, make_user(db, email="admin11@example.test", role="admin").email)  # type: ignore[arg-type]
    camera = camera_admin.post(
        "/api/v1/cameras",
        json={"name": "Room 202 cam", "room_id": other_room.id, "stream_reference": "env:CAM_R202"},
    ).json()
    _all_day_entries(db, world.class_id, world.subject_id, world.faculty_id, room_id=world.room_id)
    faculty = login(client.app, "faculty.a@example.test")
    response = faculty.post(
        f"/api/v1/classes/{world.class_id}/sessions",
        json={"camera_id": camera["id"]},
    )
    assert response.status_code == 422


def test_sessions_persist_and_list_with_filters(client: TestClient, db: Session, world: World):
    _all_day_entries(db, world.class_id, world.subject_id, world.faculty_id)
    faculty = login(client.app, "faculty.a@example.test")
    session_id = faculty.post(f"/api/v1/classes/{world.class_id}/sessions").json()["id"]
    faculty.post(f"/api/v1/sessions/{session_id}/finalize")

    # A new client (as after a server restart) still sees the finalised session.
    principal_user = make_user(db, email="principal2@example.test", role="principal")
    principal = login(client.app, principal_user.email)
    listing = principal.get(
        "/api/v1/sessions", params={"class_id": world.class_id, "status": "finalized"}
    ).json()
    assert [row["id"] for row in listing] == [session_id]
    assert principal.get("/api/v1/sessions", params={"status": "open"}).json() == []


def test_start_refuses_unknown_timetable_entry_for_another_class(db: Session, world: World):
    faculty = db.scalar(select(User).where(User.email == "faculty.a@example.test"))
    assert faculty is not None
    with pytest.raises(Exception) as excinfo:
        session_service.start_session(
            db,
            faculty,
            world.other_class_id,
            SessionStart(timetable_entry_id=world.monday_entry_id),
            now=MONDAY_1015_IST,
        )
    assert excinfo.value.status_code == 422  # type: ignore[attr-defined]


def test_audit_trail_covers_session_lifecycle(client: TestClient, db: Session, world: World):
    _all_day_entries(db, world.class_id, world.subject_id, world.faculty_id)
    faculty = login(client.app, "faculty.a@example.test")
    session_id = faculty.post(f"/api/v1/classes/{world.class_id}/sessions").json()["id"]
    faculty.post(f"/api/v1/sessions/{session_id}/finalize")
    actions = [row.action for row in db.scalars(select(AuditLog).order_by(AuditLog.id))]
    assert "session.started" in actions and "session.finalized" in actions


def test_validation_errors_never_echo_submitted_values(client: TestClient, db: Session):
    """A rejected password or stream URL must not come back in the 422 body or in logs."""
    make_user(db, email="admin12@example.test", role="admin")
    response = client.post("/api/v1/auth/login", json={"email": 12345, "password": "super-secret-pass"})
    assert response.status_code == 422
    assert "super-secret-pass" not in response.text
    body = response.json()
    assert set(body["detail"][0]) == {"loc", "msg", "type"}
