"""Biometric records. Embeddings are derived data (no images are stored) and are never returned by any API."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin


class BiometricConsent(TimestampMixin, Base):
    """Record that a student agreed to face enrollment for attendance. Withdrawing sets ``withdrawn_at``."""

    __tablename__ = "biometric_consents"
    __table_args__ = (Index("ix_consents_student", "student_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"), nullable=False)
    scope: Mapped[str] = mapped_column(String(80), nullable=False, default="face-enrollment-attendance")
    # A short reference to the paper or digital form held by the institution (never the form itself).
    reference: Mapped[str | None] = mapped_column(String(80), nullable=True)
    recorded_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )


class FaceEmbedding(TimestampMixin, Base):
    """One enrolment embedding (float32 vector stored as bytes) tied to a student and to the model that made
    it."""

    __tablename__ = "face_embeddings"
    __table_args__ = (Index("ix_face_embeddings_student", "student_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"), nullable=False)
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[str] = mapped_column(String(40), nullable=False)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    enrolled_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
