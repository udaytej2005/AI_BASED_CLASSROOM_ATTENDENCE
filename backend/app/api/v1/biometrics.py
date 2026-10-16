"""Consent, face enrolment and biometric deletion for students.

Embeddings are never returned. The API reports only counts, the model name and dates.
Role summary:
- consent, enrolment upload, enrolment deletion: administrators.
- enrolment status: administrators, principals and faculty.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field, field_validator

from app.api.deps import DbSession, require_roles
from app.core.config import get_settings
from app.core.errors import AppError
from app.models.user import ROLE_ADMIN, ROLE_FACULTY, ROLE_PRINCIPAL, User
from app.services import enrollment
from app.services.enrollment import MAX_IMAGE_BYTES
from app.vision.backend import BackendUnavailable, get_backend

router = APIRouter(tags=["biometric enrolment"])

AdminUser = Annotated[User, Depends(require_roles(ROLE_ADMIN))]
StatusReader = Annotated[User, Depends(require_roles(ROLE_ADMIN, ROLE_PRINCIPAL, ROLE_FACULTY))]


class ConsentIn(BaseModel):
    confirmed: bool
    reference: str | None = Field(default=None, max_length=80)

    @field_validator("confirmed")
    @classmethod
    def _must_confirm(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Consent must be confirmed before a face can be enrolled.")
        return value


class ConsentOut(BaseModel):
    student_id: int
    scope: str
    reference: str | None
    recorded_at: datetime
    active: bool


class EnrollmentStatusOut(BaseModel):
    student_id: int
    consent_active: bool
    consent_recorded_at: datetime | None
    embedding_count: int
    last_enrolled_at: datetime | None
    model_name: str | None
    model_version: str | None


class ImageOutcomeOut(BaseModel):
    index: int
    accepted: bool
    reasons: list[str]
    face_px: int


class EnrollmentReportOut(BaseModel):
    student_id: int
    uploaded: int
    accepted: int
    rejected: int
    model_name: str
    model_version: str
    outcomes: list[ImageOutcomeOut]


class DeletedOut(BaseModel):
    embeddings_deleted: int


@router.post(
    "/students/{student_id}/consent", response_model=ConsentOut, status_code=201, summary="Record consent"
)
def record_consent(student_id: int, payload: ConsentIn, db: DbSession, admin: AdminUser) -> ConsentOut:
    consent = enrollment.record_consent(db, admin, student_id, payload.reference)
    return ConsentOut(
        student_id=consent.student_id,
        scope=consent.scope,
        reference=consent.reference,
        recorded_at=consent.recorded_at,
        active=True,
    )


@router.delete("/students/{student_id}/consent", response_model=DeletedOut, summary="Withdraw consent")
def withdraw_consent(student_id: int, db: DbSession, admin: AdminUser) -> DeletedOut:
    # Withdrawal deletes all of the student's embeddings in the same transaction.
    return DeletedOut(embeddings_deleted=enrollment.withdraw_consent(db, admin, student_id))


@router.get(
    "/students/{student_id}/enrollment",
    response_model=EnrollmentStatusOut,
    summary="Enrolment status (no biometric data)",
)
def enrollment_status(student_id: int, db: DbSession, _: StatusReader) -> EnrollmentStatusOut:
    return EnrollmentStatusOut.model_validate(enrollment.enrollment_status(db, student_id))


@router.post(
    "/students/{student_id}/enrollment",
    response_model=EnrollmentReportOut,
    status_code=201,
    summary="Enrol a student from 3-20 photographs (JPEG or PNG)",
)
def enroll_student(
    student_id: int,
    db: DbSession,
    admin: AdminUser,
    images: Annotated[list[UploadFile], File(description="One photo per file, one face per photo")],
) -> EnrollmentReportOut:
    settings = get_settings()
    if not images or len(images) > settings.enrollment_max_images:
        raise AppError(422, f"Upload between 1 and {settings.enrollment_max_images} images.")
    payloads: list[bytes] = []
    for upload in images:
        # Read at most one byte over the limit so that an oversized file is detected without loading it all.
        data = upload.file.read(MAX_IMAGE_BYTES + 1)
        payloads.append(data)
    try:
        backend = get_backend()
    except BackendUnavailable as exc:
        raise AppError(503, str(exc)) from exc
    report = enrollment.enroll(db, admin, student_id, payloads, backend, settings)
    return EnrollmentReportOut(
        student_id=report.student_id,
        uploaded=report.total,
        accepted=report.accepted,
        rejected=report.total - report.accepted,
        model_name=report.model_name,
        model_version=report.model_version,
        outcomes=[
            ImageOutcomeOut(index=o.index, accepted=o.accepted, reasons=list(o.reasons), face_px=o.face_px)
            for o in report.outcomes
        ],
    )


@router.delete(
    "/students/{student_id}/enrollment", response_model=DeletedOut, summary="Delete enrolment embeddings"
)
def delete_enrollment(student_id: int, db: DbSession, admin: AdminUser) -> DeletedOut:
    return DeletedOut(embeddings_deleted=enrollment.delete_enrollment(db, admin, student_id))
