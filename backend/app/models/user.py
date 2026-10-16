from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin

# Role names are the single source of truth for authorisation. Keep in sync with the frontend.
ROLE_ADMIN = "admin"  # System administrator: users, academic setup, configuration
ROLE_PRINCIPAL = "principal"  # Institution overview (read-only management data)
ROLE_FACULTY = "faculty"  # Runs and reviews attendance (later phases)
ROLE_STUDENT = "student"  # Views own records only
ROLE_TECHNICAL = "technical"  # Read-only operational monitoring
ALL_ROLES = (ROLE_ADMIN, ROLE_PRINCIPAL, ROLE_FACULTY, ROLE_STUDENT, ROLE_TECHNICAL)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin','principal','faculty','student','technical')", name="role_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Records created by the demo seed are flagged so they are never mistaken for real people.
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
