"""User account management (administrators only; enforced by the API layer)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, Conflict, NotFound
from app.core.security import hash_password, validate_password_policy
from app.models.user import ROLE_ADMIN, User
from app.schemas.common import Page, PageParams
from app.schemas.users import PasswordResetRequest, UserCreate, UserUpdate
from app.services import audit
from app.services.auth import revoke_all_sessions_for_user
from app.services.common import paginate


def _active_admin_count(db: Session) -> int:
    return (
        db.scalar(
            select(func.count()).select_from(User).where(User.role == ROLE_ADMIN, User.is_active.is_(True))
        )
        or 0
    )


def _validate_password_or_422(password: str) -> None:
    try:
        validate_password_policy(password)
    except ValueError as exc:
        raise AppError(422, str(exc)) from exc


def list_users(
    db: Session,
    *,
    params: PageParams,
    q: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> Page[User]:
    statement = select(User).order_by(User.full_name, User.id)
    if q:
        pattern = f"%{q.strip().lower()}%"
        statement = statement.where(
            func.lower(User.email).like(pattern) | func.lower(User.full_name).like(pattern)
        )
    if role:
        statement = statement.where(User.role == role)
    if is_active is not None:
        statement = statement.where(User.is_active.is_(is_active))
    return paginate(db, statement, params)


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("User")
    return user


def create_user(db: Session, actor: User, data: UserCreate) -> User:
    _validate_password_or_422(data.initial_password)
    user = User(
        email=data.email,
        full_name=data.full_name,
        role=data.role,
        password_hash=hash_password(data.initial_password),
        # The administrator knows the initial password, so the new user must replace it at first sign-in.
        must_change_password=True,
        is_active=True,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("An account with this email already exists.") from exc
    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="user.created",
        entity="user",
        entity_id=user.id,
        details={"role": user.role, "email": user.email},
    )
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, actor: User, user_id: int, data: UserUpdate) -> User:
    user = get_user(db, user_id)
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return user

    if user.id == actor.id and (
        ("role" in changes and changes["role"] != ROLE_ADMIN) or changes.get("is_active") is False
    ):
        raise AppError(422, "You cannot remove your own administrator access or deactivate your own account.")

    removes_admin = (
        user.role == ROLE_ADMIN
        and user.is_active
        and (changes.get("role", ROLE_ADMIN) != ROLE_ADMIN or changes.get("is_active") is False)
    )
    if removes_admin and _active_admin_count(db) <= 1:
        raise AppError(422, "The system must keep at least one active administrator.")

    before = {"role": user.role, "is_active": user.is_active}
    for field, value in changes.items():
        setattr(user, field, value)

    if changes.get("is_active") is False:
        revoke_all_sessions_for_user(db, user.id)

    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="user.updated",
        entity="user",
        entity_id=user.id,
        details={"before": before, "changed_fields": sorted(changes.keys())},
    )
    db.commit()
    db.refresh(user)
    return user


def reset_password(db: Session, actor: User, user_id: int, data: PasswordResetRequest) -> User:
    user = get_user(db, user_id)
    _validate_password_or_422(data.new_password)
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = True
    user.failed_login_count = 0
    user.locked_until = None
    revoke_all_sessions_for_user(db, user.id)
    audit.record_audit(
        db,
        actor_user_id=actor.id,
        action="user.password_reset",
        entity="user",
        entity_id=user.id,
    )
    db.commit()
    db.refresh(user)
    return user
