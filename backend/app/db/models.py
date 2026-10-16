"""SQLAlchemy models are registered here so Alembic can discover them.

Domain models (users, students, subjects, sessions, attendance, ...) are added in Phase 2 and later.
"""

from app.db.base import Base

__all__ = ["Base"]
