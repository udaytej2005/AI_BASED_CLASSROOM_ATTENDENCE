"""Recognition runs for a session: a live camera run, an uploaded video, job status, and the recognised list.

Role summary:
- start a camera run, upload a video, stop a run: administrators and the faculty member assigned to the
session.
- read job status and the recognised list: administrators, principals and faculty.
The API never returns frames, embeddings, camera addresses or raw match scores for other students.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DbSession, require_roles
from app.core.config import get_settings
from app.core.errors import AppError, Conflict, Forbidden, NotFound
from app.models.attendance import AttendanceRecord
from app.models.session import AttendanceSession
from app.models.student import Student
from app.models.timetable import Camera
from app.models.user import ROLE_ADMIN, ROLE_FACULTY, ROLE_PRINCIPAL, User
from app.services import live_runner
from app.services.live_runner import REGISTRY, Job
from app.services.sessions import get_session, may_manage_session

router = APIRouter(tags=["recognition"])

ManageUser = Annotated[User, Depends(require_roles(ROLE_ADMIN, ROLE_FACULTY))]
ReadUser = Annotated[User, Depends(require_roles(ROLE_ADMIN, ROLE_PRINCIPAL, ROLE_FACULTY))]
CHUNK = 1024 * 1024


class JobOut(BaseModel):
    job_id: str
    session_id: int
    source: str
    state: str
    started_at: datetime
    finished_at: datetime | None
    frames_read: int
    frames_processed: int
    faces_seen: int
    recognitions: int
    newly_present_student_ids: list[int]
    error: str | None


class RecognisedOut(BaseModel):
    student_id: int
    student_code: str
    full_name: str
    status: str
    source: str
    confidence: float
    observations: int
    confirmed_offset_seconds: float


def _job_out(job: Job) -> JobOut:
    return JobOut(
        job_id=job.job_id,
        session_id=job.session_id,
        source=job.source,
        state=job.state,
        started_at=job.started_at,
        finished_at=job.finished_at,
        frames_read=job.frames_read,
        frames_processed=job.frames_processed,
        faces_seen=job.faces_seen,
        recognitions=job.recognitions,
        newly_present_student_ids=list(job.newly_present),
        error=job.error,
    )


def _open_session_for(db: DbSession, actor: User, session_id: int) -> AttendanceSession:
    session = get_session(db, session_id)
    if not may_manage_session(db, actor, session):
        raise Forbidden(
            "Only the assigned faculty member or an administrator can run recognition for this session."
        )
    if session.status != "open":
        raise Conflict(f"Session is {session.status}; recognition runs only for open sessions.")
    return session


@router.post(
    "/sessions/{session_id}/recognition/camera",
    response_model=JobOut,
    status_code=202,
    summary="Start a live recognition run on the session's camera",
)
def start_camera_run(session_id: int, db: DbSession, actor: ManageUser) -> JobOut:
    session = _open_session_for(db, actor, session_id)
    if session.camera_id is None:
        raise AppError(422, "This session has no camera assigned.")
    camera = db.get(Camera, session.camera_id)
    if camera is None or not camera.is_active:
        raise AppError(422, "The assigned camera is not active.")
    target = live_runner.resolve_camera_source(camera)
    job = REGISTRY.start(session.id, "camera", target)
    return _job_out(job)


@router.post(
    "/sessions/{session_id}/recognition/video",
    response_model=JobOut,
    status_code=202,
    summary="Process an uploaded recorded video (MP4, MOV, AVI or MKV)",
)
def upload_video(
    session_id: int,
    db: DbSession,
    actor: ManageUser,
    video: Annotated[UploadFile, File(description="One recorded video file")],
) -> JobOut:
    session = _open_session_for(db, actor, session_id)
    limit = get_settings().max_video_upload_bytes
    head = video.file.read(16)
    if not _looks_like_video(head):
        raise AppError(422, "Upload an MP4, MOV, AVI or MKV video.")
    suffix = Path(video.filename or "upload").suffix.lower()
    if suffix not in {".mp4", ".mov", ".avi", ".mkv"}:
        suffix = ".mp4"
    # The file lives in the system temp directory with owner-only permissions, and it is deleted when the job
    # ends.
    fd, name = tempfile.mkstemp(prefix="attendance-video-", suffix=suffix)
    path = Path(name)
    written = 0
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(head)
            written = len(head)
            while True:
                chunk = video.file.read(CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if written > limit:
                    raise AppError(413, "The video is larger than the configured upload limit.")
                handle.write(chunk)
        job = REGISTRY.start(session.id, "video", str(path), cleanup_path=path)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return _job_out(job)


def _looks_like_video(head: bytes) -> bool:
    if len(head) < 12:
        return False
    if head[4:8] == b"ftyp":  # MP4, MOV and similar ISO-BMFF containers
        return True
    if head[:4] == b"RIFF" and head[8:12] == b"AVI ":
        return True
    return head[:4] == b"\x1a\x45\xdf\xa3"  # Matroska / WebM


@router.get(
    "/sessions/{session_id}/recognition/jobs/{job_id}",
    response_model=JobOut,
    summary="Recognition job status",
)
def job_status(session_id: int, job_id: str, db: DbSession, actor: ReadUser) -> JobOut:
    session = get_session(db, session_id)
    if actor.role == ROLE_FACULTY and not may_manage_session(db, actor, session):
        raise Forbidden("Only the assigned faculty member can view this session's recognition jobs.")
    job = REGISTRY.get(job_id)
    if job is None or job.session_id != session_id:
        raise NotFound("Recognition job")
    return _job_out(job)


@router.post(
    "/sessions/{session_id}/recognition/jobs/{job_id}/stop",
    response_model=JobOut,
    summary="Ask a running recognition job to stop",
)
def stop_job(session_id: int, job_id: str, db: DbSession, actor: ManageUser) -> JobOut:
    session = get_session(db, session_id)
    if not may_manage_session(db, actor, session):
        raise Forbidden("Only the assigned faculty member or an administrator can stop this run.")
    job = REGISTRY.get(job_id)
    if job is None or job.session_id != session_id:
        raise NotFound("Recognition job")
    job.stop_event.set()
    return _job_out(job)


@router.get(
    "/sessions/{session_id}/recognized",
    response_model=list[RecognisedOut],
    summary="Students recorded as present by recognition (no biometric data)",
)
def recognised_students(session_id: int, db: DbSession, actor: ReadUser) -> list[RecognisedOut]:
    session = get_session(db, session_id)
    if actor.role == ROLE_FACULTY and not may_manage_session(db, actor, session):
        raise Forbidden("Only the assigned faculty member can view this session.")
    rows = db.execute(
        select(AttendanceRecord, Student)
        .join(Student, Student.id == AttendanceRecord.student_id)
        .where(AttendanceRecord.session_id == session_id)
        .order_by(Student.student_code)
    ).all()
    return [
        RecognisedOut(
            student_id=student.id,
            student_code=student.student_code,
            full_name=student.full_name,
            status=record.status,
            source=record.source,
            confidence=record.confidence,
            observations=record.observations,
            confirmed_offset_seconds=record.confirmed_offset_seconds,
        )
        for record, student in rows
    ]
