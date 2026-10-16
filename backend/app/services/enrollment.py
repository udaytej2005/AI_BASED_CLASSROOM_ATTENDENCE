"""Consent, face enrolment and biometric deletion.

Rules:
- Enrolment needs an active consent record for the student.
- Only JPEG or PNG images are accepted, each at most ``MAX_IMAGE_BYTES`` and ``MAX_IMAGE_SIDE`` pixels.
- Each image must contain exactly one face that passes the quality gates. Other images are reported with
reasons.
- Enrolment is all-or-nothing: fewer than the configured minimum of accepted images stores nothing.
- Re-enrolment replaces the previous embeddings in one transaction.
- Raw images are decoded in memory and discarded. They are never written to disk or to the database.
- Audit records hold counts and reasons only, never images or vectors.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError, Conflict, NotFound
from app.models.biometric import BiometricConsent, FaceEmbedding
from app.models.student import Student
from app.models.user import User
from app.services import audit
from app.vision.backend import FaceBackend
from app.vision.quality import QualityPolicy, assess
from app.vision.types import Detection

MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_IMAGE_SIDE = 4000
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class ImageOutcome:
    index: int
    accepted: bool
    reasons: tuple[str, ...]
    face_px: int = 0


@dataclass(frozen=True)
class EnrollmentReport:
    student_id: int
    total: int
    accepted: int
    stored: int
    model_name: str
    model_version: str
    outcomes: tuple[ImageOutcome, ...]


def quality_policy(settings: Settings) -> QualityPolicy:
    return QualityPolicy(
        min_face_px=settings.quality_min_face_px,
        min_detector_score=settings.quality_min_detector_score,
        min_sharpness=settings.quality_min_sharpness,
        brightness_min=settings.quality_brightness_min,
        brightness_max=settings.quality_brightness_max,
        max_roll_ratio=settings.quality_max_roll_ratio,
    )


def active_consent(db: Session, student_id: int) -> BiometricConsent | None:
    return db.scalar(
        select(BiometricConsent)
        .where(BiometricConsent.student_id == student_id, BiometricConsent.withdrawn_at.is_(None))
        .order_by(BiometricConsent.id.desc())
    )


def _student(db: Session, student_id: int) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise NotFound("Student")
    return student


def record_consent(db: Session, actor: User, student_id: int, reference: str | None) -> BiometricConsent:
    student = _student(db, student_id)
    if student.status != "active":
        raise AppError(422, "Consent can be recorded only for an active student.")
    if active_consent(db, student_id) is not None:
        raise Conflict("Consent is already recorded for this student.")
    consent = BiometricConsent(
        student_id=student_id,
        scope="face-enrollment-attendance",
        reference=(reference or "").strip() or None,
        recorded_by_user_id=actor.id,
        recorded_at=datetime.now(UTC),
    )
    db.add(consent)
    db.flush()
    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="consent.recorded",
        entity="student",
        entity_id=student_id,
        details={"has_reference": consent.reference is not None},
    )
    db.commit()
    db.refresh(consent)
    return consent


def withdraw_consent(db: Session, actor: User, student_id: int) -> int:
    """Withdraw consent and delete every embedding for the student. Returns the number of embeddings
    deleted."""
    _student(db, student_id)
    consent = active_consent(db, student_id)
    if consent is None:
        raise Conflict("There is no active consent to withdraw.")
    consent.withdrawn_at = datetime.now(UTC)
    consent.withdrawn_by_user_id = actor.id
    deleted = _delete_embeddings(db, student_id)
    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="consent.withdrawn",
        entity="student",
        entity_id=student_id,
        details={"records_deleted": deleted},
    )
    db.commit()
    return deleted


def _delete_embeddings(db: Session, student_id: int) -> int:
    count = db.scalar(
        select(func.count()).select_from(FaceEmbedding).where(FaceEmbedding.student_id == student_id)
    )
    db.execute(
        delete(FaceEmbedding)
        .where(FaceEmbedding.student_id == student_id)
        .execution_options(synchronize_session=False)
    )
    return int(count or 0)


def delete_enrollment(db: Session, actor: User, student_id: int) -> int:
    """Delete the student's embeddings but keep consent (for example, before a fresh enrolment)."""
    _student(db, student_id)
    deleted = _delete_embeddings(db, student_id)
    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="enrollment.deleted",
        entity="student",
        entity_id=student_id,
        details={"records_deleted": deleted},
    )
    db.commit()
    return deleted


def enrollment_status(db: Session, student_id: int) -> dict[str, Any]:
    _student(db, student_id)
    rows = db.execute(
        select(
            func.count(FaceEmbedding.id),
            func.max(FaceEmbedding.created_at),
            func.max(FaceEmbedding.model_name),
            func.max(FaceEmbedding.model_version),
        ).where(FaceEmbedding.student_id == student_id)
    ).one()
    consent = active_consent(db, student_id)
    return {
        "student_id": student_id,
        "consent_active": consent is not None,
        "consent_recorded_at": consent.recorded_at if consent else None,
        "embedding_count": int(rows[0] or 0),
        "last_enrolled_at": rows[1],
        "model_name": rows[2],
        "model_version": rows[3],
    }


def _decode(data: bytes) -> tuple[np.ndarray | None, str | None]:
    import cv2

    if len(data) > MAX_IMAGE_BYTES:
        return None, "file is larger than 3 MB"
    if not (data.startswith(JPEG_MAGIC) or data.startswith(PNG_MAGIC)):
        return None, "only JPEG or PNG images are accepted"
    frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return None, "image could not be decoded"
    if max(frame.shape[:2]) > MAX_IMAGE_SIDE:
        return None, f"image side is larger than {MAX_IMAGE_SIDE}px"
    return frame, None


def enroll(
    db: Session,
    actor: User,
    student_id: int,
    images: list[bytes],
    backend: FaceBackend,
    settings: Settings | None = None,
) -> EnrollmentReport:
    settings = settings or get_settings()
    student = _student(db, student_id)
    if student.status != "active":
        raise AppError(422, "Only active students can be enrolled.")
    if active_consent(db, student_id) is None:
        raise Conflict("Record the student's consent before enrolling their face.")
    if not images:
        raise AppError(422, "Upload at least one image.")

    policy = quality_policy(settings)
    vectors: list[np.ndarray] = []
    qualities: list[float] = []
    outcomes: list[ImageOutcome] = []
    for index, data in enumerate(images):
        frame, error = _decode(data)
        if frame is None:
            outcomes.append(ImageOutcome(index, False, (error or "unreadable image",)))
            continue
        faces: list[Detection] = backend.detector.detect(frame)
        if len(faces) != 1:
            reason = (
                "no face found" if not faces else f"{len(faces)} faces found; upload one person per image"
            )
            outcomes.append(ImageOutcome(index, False, (reason,)))
            continue
        face = faces[0]
        quality = assess(frame, face, policy)
        if not quality.passed:
            outcomes.append(ImageOutcome(index, False, quality.reasons, quality.face_px))
            continue
        vectors.append(backend.embedder.embed(frame, face))
        qualities.append(face.score)
        outcomes.append(ImageOutcome(index, True, (), quality.face_px))

    accepted = len(vectors)
    if accepted < settings.enrollment_min_accepted_images:
        raise AppError(
            422,
            f"Only {accepted} of {len(images)} images passed the checks; at least "
            f"{settings.enrollment_min_accepted_images} are needed. Nothing was saved.",
        )

    _delete_embeddings(db, student_id)
    for vector, quality_score in zip(vectors, qualities, strict=True):
        db.add(
            FaceEmbedding(
                student_id=student_id,
                embedding=vector.astype(np.float32).tobytes(),
                dimension=int(vector.shape[0]),
                model_name=backend.model_name,
                model_version=backend.model_version,
                quality_score=float(quality_score),
                enrolled_by_user_id=actor.id,
            )
        )
    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="enrollment.completed",
        entity="student",
        entity_id=student_id,
        details={
            "uploaded": len(images),
            "accepted": accepted,
            "rejected": len(images) - accepted,
            "model": f"{backend.model_name}:{backend.model_version}",
        },
    )
    db.commit()
    return EnrollmentReport(
        student_id=student_id,
        total=len(images),
        accepted=accepted,
        stored=accepted,
        model_name=backend.model_name,
        model_version=backend.model_version,
        outcomes=tuple(outcomes),
    )


def load_gallery_rows(db: Session, dimension: int = 128) -> list[tuple[int, np.ndarray]]:
    """Embeddings of active students, for matching. Used inside the server; never returned by an API."""
    rows = db.execute(
        select(FaceEmbedding.student_id, FaceEmbedding.embedding, FaceEmbedding.dimension)
        .join(Student, Student.id == FaceEmbedding.student_id)
        .where(Student.status == "active")
    ).all()
    result: list[tuple[int, np.ndarray]] = []
    for student_id, blob, dim in rows:
        if dim != dimension:
            continue  # embeddings made by a different model are ignored until re-enrolled
        result.append((student_id, np.frombuffer(blob, dtype=np.float32).copy()))
    return result


def purge_expired(db: Session, now: datetime | None = None, retention_days: int | None = None) -> int:
    """Delete embeddings older than the retention period. Returns the number deleted."""
    days = retention_days or get_settings().biometric_retention_days
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    limit = current - timedelta(days=days)
    expired = db.scalar(
        select(func.count()).select_from(FaceEmbedding).where(FaceEmbedding.created_at < limit)
    )
    db.execute(
        delete(FaceEmbedding)
        .where(FaceEmbedding.created_at < limit)
        .execution_options(synchronize_session=False)
    )
    audit.record_audit(
        db,
        actor_user_id=None,
        action="biometrics.retention_purge",
        entity="face_embedding",
        entity_id=None,
        details={"deleted": int(expired or 0), "retention_days": days},
    )
    db.commit()
    return int(expired or 0)
