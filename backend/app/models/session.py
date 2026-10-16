"""Attendance sessions: one live or finalised run per timetable period.

Phase 4 adds automatic ``present`` rows (see attendance.py). Absent rows and corrections come in Phase 5.
"""

from datetime import date, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin


class AttendanceSession(TimestampMixin, Base):
    __tablename__ = "attendance_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('open','finalized','cancelled')", name="status_valid"),
        # One session per timetable period and date. Ad-hoc sessions (NULL entry) are not constrained here.
        Index(
            "uq_session_period_per_day",
            "timetable_entry_id",
            "session_date",
            unique=True,
        ),
        Index("ix_sessions_class_date", "class_id", "session_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculty.id", ondelete="RESTRICT"), nullable=False)
    timetable_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("timetable_entries.id", ondelete="RESTRICT"), nullable=True
    )
    camera_id: Mapped[int | None] = mapped_column(
        ForeignKey("cameras.id", ondelete="RESTRICT"), nullable=True
    )
    session_date: Mapped[date] = mapped_column(nullable=False)
    period_label: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="open", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    ended_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
