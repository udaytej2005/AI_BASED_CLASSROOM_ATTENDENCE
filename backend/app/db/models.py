"""Imports every model so that Base.metadata is complete (used by Alembic autogenerate)."""

from app.db.base import Base
from app.models.attendance import AttendanceRecord
from app.models.audit_log import AuditLog
from app.models.auth_session import AuthSession
from app.models.biometric import BiometricConsent, FaceEmbedding
from app.models.department import Department
from app.models.faculty import Faculty
from app.models.session import AttendanceSession
from app.models.student import Student
from app.models.timetable import Camera, ClassGroup, ClassRosterEntry, Room, Subject, TimetableEntry
from app.models.user import User

__all__ = [
    "AttendanceSession",
    "AttendanceRecord",
    "AuditLog",
    "BiometricConsent",
    "FaceEmbedding",
    "AuthSession",
    "Base",
    "Camera",
    "ClassGroup",
    "ClassRosterEntry",
    "Department",
    "Faculty",
    "Room",
    "Student",
    "Subject",
    "TimetableEntry",
    "User",
]
