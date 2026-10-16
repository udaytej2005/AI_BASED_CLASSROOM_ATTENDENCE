"""Background recognition jobs: a live camera run or an uploaded video.

Each job runs in its own thread with its own database session, because request sessions close when the HTTP
call
returns. Job state is kept in memory, so the server must run as ONE process (see docs/face-recognition.md).
Camera sources are resolved on the server only:
- a device index (for example "0"), or
- the name of an environment variable whose value is the stream address.
Stream addresses are never stored in the database or returned by the API.
"""

from __future__ import annotations

import os
import re
import threading
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_session_factory
from app.models.session import AttendanceSession
from app.models.timetable import Camera
from app.services import recognition
from app.vision.backend import BackendUnavailable, get_backend

ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
DEVICE_INDEX_RE = re.compile(r"^\d{1,2}$")


class SourceError(AppError):
    pass


def resolve_camera_source(camera: Camera) -> int | str:
    """Turn a camera's stored reference into an OpenCV source. The result is never sent to a client."""
    reference = camera.stream_reference.strip()
    if DEVICE_INDEX_RE.match(reference):
        return int(reference)
    if ENV_NAME_RE.match(reference):
        value = os.environ.get(reference, "").strip()
        if not value:
            raise SourceError(422, "This camera has no stream configured on the server.")
        if DEVICE_INDEX_RE.match(value):
            return int(value)
        return value
    raise SourceError(422, "This camera's configured source is not valid.")


def _frames_from_capture(capture, fps_hint: float, should_stop) -> Iterator[tuple[np.ndarray, float]]:  # noqa: ANN001
    started = time.monotonic()
    index = 0
    while not should_stop():
        ok, frame = capture.read()
        if not ok or frame is None:
            return
        if fps_hint > 0:
            timestamp = index / fps_hint
        else:
            timestamp = time.monotonic() - started
        index += 1
        yield frame, timestamp


@dataclass
class Job:
    job_id: str
    session_id: int
    source: str  # "camera" or "video"
    state: str = "running"  # running, completed, stopped, failed
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    frames_read: int = 0
    frames_processed: int = 0
    faces_seen: int = 0
    recognitions: int = 0
    newly_present: list[int] = field(default_factory=list)
    error: str | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None


class JobRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}

    def active_for_session(self, session_id: int) -> Job | None:
        with self._lock:
            for job in self._jobs.values():
                if job.session_id == session_id and job.state == "running":
                    return job
        return None

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _add(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.job_id] = job

    def start(self, session_id: int, source: str, target, cleanup_path: Path | None = None) -> Job:  # noqa: ANN001
        if self.active_for_session(session_id) is not None:
            raise AppError(409, "A recognition run is already active for this session.")
        job = Job(job_id=uuid.uuid4().hex, session_id=session_id, source=source)
        self._add(job)
        thread = threading.Thread(
            target=_run_job,
            args=(job, target, cleanup_path),
            name=f"recognition-{job.job_id[:8]}",
            daemon=True,
        )
        job.thread = thread
        thread.start()
        return job


REGISTRY = JobRegistry()


def _run_job(job: Job, target, cleanup_path: Path | None) -> None:  # noqa: ANN001
    import cv2

    capture = None
    try:
        backend = get_backend()
        with get_session_factory()() as db:
            session = db.get(AttendanceSession, job.session_id)
            if session is None or session.status != "open":
                raise SourceError(409, "The session is no longer open.")
            capture = cv2.VideoCapture(target)
            if not capture.isOpened():
                raise SourceError(503, "The camera or video source could not be opened.")
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
            if job.source == "camera":
                fps = 0.0  # live: use the wall clock
            frames = _frames_from_capture(capture, fps, job.stop_event.is_set)
            summary = recognition.run_recognition(
                db,
                session,
                frames,
                backend,
                source=job.source,
                should_stop=job.stop_event.is_set,
            )
        job.frames_read = summary.frames_read
        job.frames_processed = summary.frames_processed
        job.faces_seen = summary.faces_seen
        job.recognitions = summary.recognitions
        job.newly_present = list(summary.newly_present)
        job.state = "stopped" if summary.stopped_early else "completed"
    except BackendUnavailable:
        job.state = "failed"
        job.error = "Face models are not installed on the server."
    except AppError as exc:
        job.state = "failed"
        job.error = exc.detail
    except Exception:  # never leak internals to clients; the detail goes to the server log only
        job.state = "failed"
        job.error = "Recognition stopped unexpectedly. See the server log."
        import logging

        logging.getLogger(__name__).exception("recognition job %s failed", job.job_id)
    finally:
        if capture is not None:
            capture.release()
        if cleanup_path is not None:
            try:
                cleanup_path.unlink(missing_ok=True)
            except OSError:
                pass
        job.finished_at = datetime.now(UTC)


def max_upload_bytes() -> int:
    return get_settings().max_video_upload_bytes
