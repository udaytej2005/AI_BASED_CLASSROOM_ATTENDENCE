from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin


class Student(TimestampMixin, Base):
    """Student profile. Historical attendance will reference students, so students are deactivated, not
    deleted."""

    __tablename__ = "students"
    __table_args__ = (
        CheckConstraint("status IN ('active','inactive')", name="status_valid"),
        CheckConstraint("year BETWEEN 1 AND 6", name="year_range"),
        Index("ix_students_department_id", "department_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Roll number / student ID, normalised to upper case (e.g. CSE001).
    student_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(10), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="active", nullable=False)
    # Optional login account for the student dashboard. One account per student.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), unique=True, nullable=True
    )
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
