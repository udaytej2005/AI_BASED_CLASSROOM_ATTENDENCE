"""Recognition over a stream of frames, turning verified matches into ``present`` attendance rows.

Rules:
- Only faces that match an enrolled student with status ``recognized_candidate`` count, and only when the
match
  is a fresh recognition in this frame (carried-over readings do not add evidence).
- Only students on the session's class roster can be marked present. A match to anyone else is discarded.
- A student becomes present only after the temporal verifier confirms repeated, spread-out observations.
- Each student gets at most one row per session. The unique constraint enforces this as well.
- Frames are never written to disk. Rows hold scores, counts and offsets, never images or embeddings.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.attendance import AttendanceRecord
from app.models.session import AttendanceSession
from app.models.student import Student
from app.models.timetable import ClassRosterEntry
from app.services import audit
from app.services.enrollment import load_gallery_rows, quality_policy
from app.vision.backend import FaceBackend
from app.vision.matcher import Gallery
from app.vision.pipeline import FramePipeline
from app.vision.verification import TemporalVerifier


@dataclass
class RecognitionSummary:
    frames_read: int = 0
    frames_processed: int = 0
    faces_seen: int = 0
    recognitions: int = 0
    uncertain: int = 0
    unknown: int = 0
    low_quality: int = 0
    not_on_roster: int = 0
    newly_present: list[int] = field(default_factory=list)
    stopped_early: bool = False


def roster_student_ids(db: Session, class_id: int) -> set[int]:
    rows = db.scalars(
        select(ClassRosterEntry.student_id)
        .join(Student, Student.id == ClassRosterEntry.student_id)
        .where(ClassRosterEntry.class_id == class_id, Student.status == "active")
    ).all()
    return set(rows)


def already_present(db: Session, session_id: int) -> set[int]:
    return set(
        db.scalars(select(AttendanceRecord.student_id).where(AttendanceRecord.session_id == session_id)).all()
    )


def _record_present(
    db: Session,
    session: AttendanceSession,
    student_id: int,
    *,
    source: str,
    confidence: float,
    observations: int,
    offset: float,
) -> None:
    db.add(
        AttendanceRecord(
            session_id=session.id,
            student_id=student_id,
            status="present",
            source=source,
            confidence=round(float(confidence), 4),
            observations=observations,
            confirmed_offset_seconds=round(float(offset), 3),
            confirmed_at=datetime.now(UTC),
        )
    )
    audit.record_audit(
        db,
        actor_user_id=None,
        action="attendance.auto_present",
        entity="attendance_session",
        entity_id=session.id,
        details={"student_id": student_id, "source": source, "observations": observations},
    )
    db.commit()


def run_recognition(
    db: Session,
    session: AttendanceSession,
    frames: Iterable[tuple[np.ndarray, float]],
    backend: FaceBackend,
    *,
    source: str,
    settings: Settings | None = None,
    should_stop: Callable[[], bool] = lambda: False,
    gallery: Gallery | None = None,
) -> RecognitionSummary:
    """Run detection, quality gating, matching and verification over ``frames``.

    ``frames`` yields ``(bgr_image, timestamp_seconds)``. ``source`` is "camera" or "video" and is stored
    with each
    row. ``gallery`` can be supplied by tests. Otherwise it is built from enrolled students who are active.
    """
    settings = settings or get_settings()
    if source not in ("camera", "video"):
        raise ValueError("source must be 'camera' or 'video'")
    roster = roster_student_ids(db, session.class_id)
    if gallery is None:
        gallery = Gallery.from_rows(load_gallery_rows(db, dimension=128))
    pipeline = FramePipeline(
        backend,
        gallery,
        threshold=settings.face_match_threshold,
        margin=settings.face_match_margin,
        quality=quality_policy(settings),
        recognize_every=settings.face_recognize_every_frames,
    )
    verifier = TemporalVerifier(
        min_observations=settings.temporal_min_observations,
        min_span_seconds=settings.temporal_min_span_seconds,
        min_gap_seconds=settings.temporal_min_gap_seconds,
    )
    recorded = already_present(db, session.id)
    summary = RecognitionSummary()
    for frame_index, (frame, timestamp) in enumerate(frames):
        if should_stop():
            summary.stopped_early = True
            break
        summary.frames_read += 1
        if frame_index % settings.face_process_every_frames != 0:
            continue
        if summary.frames_processed >= settings.video_max_processed_frames:
            break
        summary.frames_processed += 1
        report = pipeline.process(frame, frame_index, timestamp)
        summary.faces_seen += report.face_count
        for reading in report.readings:
            if reading.status == "low_quality":
                summary.low_quality += 1
            if not reading.recognized_now:
                continue
            summary.recognitions += 1
            if reading.status == "uncertain":
                summary.uncertain += 1
                continue
            if reading.status == "unknown":
                summary.unknown += 1
                continue
            if reading.status != "recognized_candidate" or reading.student_id is None:
                continue
            if reading.student_id not in roster:
                summary.not_on_roster += 1
                continue
            confirmed = verifier.add(reading.student_id, timestamp, reading.score)
            if confirmed and reading.student_id not in recorded:
                evidence = next(e for e in verifier.evidence() if e.student_id == reading.student_id)
                _record_present(
                    db,
                    session,
                    reading.student_id,
                    source=source,
                    confidence=evidence.best_score,
                    observations=evidence.observations,
                    offset=timestamp,
                )
                recorded.add(reading.student_id)
                summary.newly_present.append(reading.student_id)
    return summary
