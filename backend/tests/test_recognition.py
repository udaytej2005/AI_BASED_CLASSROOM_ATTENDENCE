"""Recognition-to-attendance tests using synthetic videos (FFV1, lossless) and the fake backend.

No real person's image is used, and no accuracy is measured here.
"""

from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.attendance import AttendanceRecord
from app.models.audit_log import AuditLog
from app.models.session import AttendanceSession
from app.models.timetable import Camera, ClassRosterEntry
from app.models.user import ROLE_ADMIN, User
from app.schemas.sessions import SessionStart
from app.services import enrollment, recognition
from app.services import sessions as session_service
from app.services.live_runner import REGISTRY
from tests.conftest import login, make_user
from tests.fakes import FakeBackend, encode_png, make_photo
from tests.test_timetable_sessions import MONDAY_1015_IST, World
from tests.test_timetable_sessions import world as _world_fixture

world = _world_fixture  # re-export the Phase 3 fixture under the same name

IDENTITY_ENROLLED_ON_ROSTER = 101
IDENTITY_ROSTER_ABSENT = 102
IDENTITY_NOT_ON_ROSTER = 103
IDENTITY_STRANGER = 199


@pytest.fixture
def fast_settings(monkeypatch):
    """Recognise on every processed frame so a short synthetic video can meet the verification rule."""
    monkeypatch.setenv("FACE_RECOGNIZE_EVERY_FRAMES", "1")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def backend(monkeypatch) -> FakeBackend:
    fake = FakeBackend()
    import app.services.live_runner as runner

    monkeypatch.setattr(runner, "get_backend", lambda: fake)
    return fake


@pytest.fixture
def enrolled(db: Session, world: World, fast_settings, backend: FakeBackend) -> dict[str, int]:
    """Three enrolled students. Only the first two are on the class roster."""
    admin = make_user(db, email="admin.rec@example.test", role=ROLE_ADMIN)
    ids = {}
    for label, identity, on_roster in (
        ("on", IDENTITY_ENROLLED_ON_ROSTER, True),
        ("absent", IDENTITY_ROSTER_ABSENT, True),
        ("off", IDENTITY_NOT_ON_ROSTER, False),
    ):
        student_id = world.student_ids[len(ids)]
        ids[label] = student_id
        enrollment.record_consent(db, admin, student_id, None)
        photos = [encode_png(make_photo([{"identity": identity, "variant": v}])) for v in range(6)]
        enrollment.enroll(db, admin, student_id, photos, backend)
        if on_roster:
            db.add(ClassRosterEntry(class_id=world.class_id, student_id=student_id))
    db.commit()
    return ids


@pytest.fixture
def open_session(db: Session, world: World, enrolled) -> int:
    """Id of an open session for the world's Monday 10:15 period, with a camera assigned."""
    faculty = db.scalar(select(User).where(User.email == "faculty.a@example.test"))
    camera = Camera(
        name="CAM-R101",
        room_id=world.room_id,
        stream_reference="TEST_CAMERA_SOURCE",
        status="unknown",
        is_active=True,
    )
    db.add(camera)
    db.commit()
    started = session_service.start_session(
        db, faculty, world.class_id, SessionStart(camera_id=camera.id), now=MONDAY_1015_IST
    )
    session_id = started.id
    db.commit()
    return session_id


def _session(db: Session, session_id: int) -> AttendanceSession:
    session = db.get(AttendanceSession, session_id)
    assert session is not None
    return session


def _scene(variant: int) -> np.ndarray:
    """Frame with the roster student (slot 0), a stranger (slot 1) and the not-on-roster student (slot 2)."""
    return make_photo(
        [
            {"identity": IDENTITY_ENROLLED_ON_ROSTER, "variant": variant % 5},
            {"identity": IDENTITY_STRANGER, "variant": variant % 5},
            {"identity": IDENTITY_NOT_ON_ROSTER, "variant": variant % 5},
        ]
    )


def _write_video(path: Path, frames: int = 60, fps: float = 10.0) -> Path:
    """Lossless AVI, so the marker pixels survive the round trip through the decoder."""
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"FFV1"), fps, (640, 240))
    assert writer.isOpened()
    for index in range(frames):
        writer.write(_scene(index))
    writer.release()
    return path


def _frames(count: int = 60, fps: float = 10.0):
    return [(_scene(i), i / fps) for i in range(count)]


# --- service level ------------------------------------------------------------


def test_only_roster_students_with_verified_matches_are_marked_present(
    db: Session, open_session, enrolled, backend, fast_settings
):
    summary = recognition.run_recognition(db, _session(db, open_session), _frames(), backend, source="video")
    rows = db.scalars(select(AttendanceRecord).where(AttendanceRecord.session_id == open_session)).all()
    present_ids = {row.student_id for row in rows}
    assert present_ids == {enrolled["on"]}
    assert enrolled["absent"] not in present_ids  # on the roster but not in the video
    assert enrolled["off"] not in present_ids  # recognised but not on this class's roster
    assert summary.not_on_roster > 0
    assert summary.unknown > 0  # the stranger is never attributed to anyone
    row = rows[0]
    assert row.status == "present" and row.source == "video"
    assert row.observations >= 5 and row.confidence > 0.9


def test_one_frame_cannot_mark_anyone_present(db: Session, open_session, enrolled, backend, fast_settings):
    recognition.run_recognition(db, _session(db, open_session), _frames(count=1), backend, source="video")
    assert db.scalar(select(func.count()).select_from(AttendanceRecord)) == 0


def test_repeat_run_never_duplicates_a_student(db: Session, open_session, enrolled, backend, fast_settings):
    recognition.run_recognition(db, _session(db, open_session), _frames(), backend, source="video")
    second = recognition.run_recognition(db, _session(db, open_session), _frames(), backend, source="video")
    assert second.newly_present == []
    assert db.scalar(select(func.count()).select_from(AttendanceRecord)) == 1


def test_stop_request_is_honoured_before_any_frame_is_processed(
    db: Session, open_session, enrolled, backend, fast_settings
):
    summary = recognition.run_recognition(
        db, _session(db, open_session), _frames(), backend, source="video", should_stop=lambda: True
    )
    assert summary.stopped_early is True and summary.frames_processed == 0


def test_invalid_source_is_rejected(db: Session, open_session, backend):
    with pytest.raises(ValueError):
        recognition.run_recognition(db, _session(db, open_session), [], backend, source="upload")


def test_audit_entry_records_only_ids_and_counts(db: Session, open_session, enrolled, backend, fast_settings):
    recognition.run_recognition(db, _session(db, open_session), _frames(), backend, source="video")
    row = db.scalar(select(AuditLog).where(AuditLog.action == "attendance.auto_present"))
    assert row is not None and row.details is not None
    assert "embedding" not in row.details and "image" not in row.details


# --- API: upload and job lifecycle --------------------------------------------


def _wait_for_job(client: TestClient, session_id: int, job_id: str, timeout: float = 60.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/api/v1/sessions/{session_id}/recognition/jobs/{job_id}").json()
        if body["state"] != "running":
            return body
        time.sleep(0.1)
    raise AssertionError("recognition job did not finish in time")


def test_video_upload_runs_job_and_lists_present_students(
    app: FastAPI, db: Session, world: World, open_session, enrolled, backend, fast_settings, tmp_path
):
    faculty_client = login(app, "faculty.a@example.test")
    video = _write_video(tmp_path / "class.avi")
    db.close()  # release the setup transaction before the background job writes
    with video.open("rb") as handle:
        response = faculty_client.post(
            f"/api/v1/sessions/{open_session}/recognition/video",
            files={"video": ("class.avi", handle, "video/x-msvideo")},
        )
    assert response.status_code == 202, response.text
    job = _wait_for_job(faculty_client, open_session, response.json()["job_id"])
    assert job["state"] == "completed", job
    assert job["newly_present_student_ids"] == [enrolled["on"]]
    assert job["frames_read"] == 60

    recognised = faculty_client.get(f"/api/v1/sessions/{open_session}/recognized").json()
    assert [row["student_id"] for row in recognised] == [enrolled["on"]]
    assert set(recognised[0]) == {
        "student_id",
        "student_code",
        "full_name",
        "status",
        "source",
        "confidence",
        "observations",
        "confirmed_offset_seconds",
    }
    text = response.text + str(recognised)
    assert "embedding" not in text and "base64" not in text and "path" not in text.lower()


def test_uploaded_video_is_deleted_after_the_job(
    app: FastAPI, open_session, enrolled, backend, fast_settings, tmp_path, monkeypatch
):
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    client = login(app, "faculty.a@example.test")
    video = _write_video(tmp_path / "source.avi")
    with video.open("rb") as handle:
        response = client.post(
            f"/api/v1/sessions/{open_session}/recognition/video",
            files={"video": ("source.avi", handle, "video/x-msvideo")},
        )
    assert response.status_code == 202
    _wait_for_job(client, open_session, response.json()["job_id"])
    leftovers = list(tmp_path.glob("attendance-video-*"))
    assert leftovers == []


def test_non_video_upload_is_refused(app: FastAPI, open_session, enrolled, backend):
    client = login(app, "faculty.a@example.test")
    response = client.post(
        f"/api/v1/sessions/{open_session}/recognition/video",
        files={"video": ("notes.avi", b"this is definitely not a video file", "video/x-msvideo")},
    )
    assert response.status_code == 422


def test_other_faculty_cannot_run_recognition(app: FastAPI, open_session, enrolled, backend):
    other = login(app, "faculty.b@example.test")
    response = other.post(f"/api/v1/sessions/{open_session}/recognition/camera")
    assert response.status_code == 403
    upload = other.post(
        f"/api/v1/sessions/{open_session}/recognition/video",
        files={"video": ("x.avi", b"RIFF0000AVI LIST", "video/x-msvideo")},
    )
    assert upload.status_code == 403


def test_student_role_cannot_start_runs(app: FastAPI, db: Session, open_session, enrolled):
    student = make_user(db, email="student.rec@example.test", role="student")
    client = login(app, student.email)
    assert client.post(f"/api/v1/sessions/{open_session}/recognition/camera").status_code == 403


def test_recognition_refused_for_finalized_session(app: FastAPI, db: Session, open_session, enrolled):
    _session(db, open_session).status = "finalized"
    db.commit()
    client = login(app, "faculty.a@example.test")
    response = client.post(f"/api/v1/sessions/{open_session}/recognition/camera")
    assert response.status_code == 409


def test_camera_run_uses_server_side_source_and_never_returns_it(
    app: FastAPI, db: Session, open_session, enrolled, backend, fast_settings, tmp_path, monkeypatch
):
    video = _write_video(tmp_path / "camera-feed.avi")
    monkeypatch.setenv("TEST_CAMERA_SOURCE", str(video))
    client = login(app, "faculty.a@example.test")
    response = client.post(f"/api/v1/sessions/{open_session}/recognition/camera")
    assert response.status_code == 202, response.text
    job = _wait_for_job(client, open_session, response.json()["job_id"])
    assert job["state"] in {"completed", "stopped"}
    assert str(video) not in response.text and str(video) not in str(job)


def test_camera_without_configured_source_is_refused(
    app: FastAPI, open_session, enrolled, backend, monkeypatch
):
    monkeypatch.delenv("TEST_CAMERA_SOURCE", raising=False)
    client = login(app, "faculty.a@example.test")
    response = client.post(f"/api/v1/sessions/{open_session}/recognition/camera")
    assert response.status_code == 422
    assert "no stream configured" in response.json()["detail"]


def test_job_from_another_session_is_not_visible(
    app: FastAPI, open_session, enrolled, backend, fast_settings
):
    client = login(app, "faculty.a@example.test")
    assert client.get(f"/api/v1/sessions/{open_session + 999}/recognition/jobs/unknown").status_code == 404


def test_registry_refuses_second_active_run_for_same_session(backend):
    from app.core.errors import AppError
    from app.services.live_runner import Job

    registry = REGISTRY
    fake_job = Job(job_id="fake-running", session_id=424242, source="video", state="running")
    registry._add(fake_job)  # noqa: SLF001  (test-only: simulate an active run)
    try:
        with pytest.raises(AppError) as info:
            registry.start(424242, "video", "/nonexistent")
        assert info.value.status_code == 409
    finally:
        fake_job.state = "stopped"
