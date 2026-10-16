"""Academic structure: subjects, rooms, classes, class rosters, timetable entries and cameras."""

from datetime import time

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin


class Subject(TimestampMixin, Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Room(TimestampMixin, Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ClassGroup(TimestampMixin, Base):
    """A class (cohort) such as CSE 2nd year section A. Named ``ClassGroup`` because ``class`` is a Python
    keyword."""

    __tablename__ = "classes"
    __table_args__ = (
        CheckConstraint("year BETWEEN 1 AND 6", name="year_range"),
        UniqueConstraint("department_id", "year", "section", name="uq_class_department_year_section"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(10), nullable=False)
    room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ClassRosterEntry(TimestampMixin, Base):
    """Membership of a student in a class. The roster is the basis for absent candidates."""

    __tablename__ = "class_students"
    __table_args__ = (
        UniqueConstraint("class_id", "student_id", name="uq_class_student"),
        Index("ix_class_students_student_id", "student_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"), nullable=False)


class TimetableEntry(TimestampMixin, Base):
    """A weekly slot.

    ``kind`` is 'class' (needs class, subject and faculty), 'break' (class_id NULL means all classes) or
    'free' (a class-specific free period).
    """

    __tablename__ = "timetable_entries"
    __table_args__ = (
        CheckConstraint("kind IN ('class','break','free')", name="kind_valid"),
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="day_valid"),
        CheckConstraint("start_time < end_time", name="time_order"),
        CheckConstraint(
            "kind <> 'class' OR (class_id IS NOT NULL AND subject_id IS NOT NULL AND faculty_id IS NOT NULL)",
            name="class_fields_required",
        ),
        Index("ix_timetable_class_day", "class_id", "day_of_week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), default="class", nullable=False)
    # Monday = 0 ... Sunday = 6, in the institutional timezone.
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    period_label: Mapped[str] = mapped_column(String(40), nullable=False)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id", ondelete="RESTRICT"), nullable=True)
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=True
    )
    faculty_id: Mapped[int | None] = mapped_column(
        ForeignKey("faculty.id", ondelete="RESTRICT"), nullable=True
    )
    room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Camera(TimestampMixin, Base):
    """An authorised camera.

    ``stream_reference`` names where to read from: an environment variable that holds the stream URL, a device
    index, or a local file. Raw stream URLs with credentials are never stored in the database.
    """

    __tablename__ = "cameras"
    __table_args__ = (CheckConstraint("status IN ('unknown','online','offline')", name="status_valid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=True)
    stream_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(10), default="unknown", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
