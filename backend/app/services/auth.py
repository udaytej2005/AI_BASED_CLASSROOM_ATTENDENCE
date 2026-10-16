"""Login, logout and session validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    generate_session_token,
    hash_session_token,
    spend_dummy_verification,
    verify_password,
)
from app.models.auth_session import AuthSession
from app.models.base import utcnow
from app.models.user import User


def _aware(value: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC. PostgreSQL already returns aware values."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def authenticate(db: Session, email: str, password: str) -> User:
    """Return the user for valid credentials. Otherwise raise AppError with a generic message."""
    settings = get_settings()
    normalized = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized))

    if user is None:
        spend_dummy_verification(password)
        raise AppError(401, "Email or password is incorrect.")

    now = utcnow()
    if user.locked_until is not None and _aware(user.locked_until) > now:
        raise AppError(429, "Too many failed sign-in attempts. Wait a few minutes and try again.")

    if not user.is_active:
        # Same message as a wrong password, so inactive accounts are not revealed.
        spend_dummy_verification(password)
        raise AppError(401, "Email or password is incorrect.")

    if not verify_password(user.password_hash, password):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.login_max_failed_attempts:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
            user.failed_login_count = 0
        db.commit()
        raise AppError(401, "Email or password is incorrect.")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    db.commit()
    return user


def create_session(db: Session, user: User) -> str:
    """Create a server-side session and return the raw token (sent once, in a cookie)."""
    settings = get_settings()
    token = generate_session_token()
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=utcnow() + timedelta(minutes=settings.session_ttl_minutes),
        )
    )
    db.commit()
    return token


def get_user_for_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    session_row = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_session_token(token)))
    if session_row is None or session_row.revoked_at is not None:
        return None
    if _aware(session_row.expires_at) <= utcnow():
        return None
    user = db.get(User, session_row.user_id)
    if user is None or not user.is_active:
        return None
    return user


def revoke_session(db: Session, token: str | None) -> None:
    if not token:
        return
    db.execute(
        update(AuthSession)
        .where(AuthSession.token_hash == hash_session_token(token), AuthSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    db.commit()


def revoke_all_sessions_for_user(db: Session, user_id: int) -> None:
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
