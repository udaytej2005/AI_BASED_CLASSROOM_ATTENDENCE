"""Imports every model so that Base.metadata is complete (used by Alembic autogenerate)."""

from app.db.base import Base
from app.models.audit_log import AuditLog
from app.models.auth_session import AuthSession
from app.models.department import Department
from app.models.faculty import Faculty
from app.models.student import Student
from app.models.user import User

__all__ = ["AuditLog", "AuthSession", "Base", "Department", "Faculty", "Student", "User"]
