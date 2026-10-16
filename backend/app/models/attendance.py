"""Attendance rows. Phase 4 writes only ``present`` rows, and only after temporal verification.

Absent rows and manual corrections come in Phase 5. A row never records raw images or biometric data.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin


class AttendanceRecord(TimestampMixin, Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_attendance_session_student"),
        CheckConstraint("status IN ('present')", name="status_valid"),
        CheckConstraint("source IN ('camera','video')", name="source_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="RESTRICT"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="present")
    source: Mapped[str] = mapped_column(String(12), nullable=False)
    # Best cosine similarity seen for the student during the run. It is a score, not a probability.
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    observations: Mapped[int] = mapped_column(Integer, nullable=False)
    # Seconds from the start of the video (or of the camera run) when the verification was met.
    confirmed_offset_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
