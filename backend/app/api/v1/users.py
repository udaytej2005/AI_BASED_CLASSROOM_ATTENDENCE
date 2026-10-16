"""User account management. Administrators only."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, require_roles
from app.models.user import ROLE_ADMIN, User
from app.schemas.auth import UserOut
from app.schemas.common import Page, PageParams
from app.schemas.users import PasswordResetRequest, UserCreate, UserUpdate
from app.services import users as users_service

router = APIRouter(prefix="/users", tags=["users"])

AdminUser = Annotated[User, Depends(require_roles(ROLE_ADMIN))]


def _out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        is_synthetic=user.is_synthetic,
        last_login_at=user.last_login_at,
    )


@router.get("", response_model=Page[UserOut], summary="List user accounts")
def list_users(
    db: DbSession,
    admin: AdminUser,
    params: Annotated[PageParams, Depends()],
    q: Annotated[str | None, Query(max_length=120)] = None,
    role: Annotated[str | None, Query(pattern="^(admin|principal|faculty|student|technical)$")] = None,
    is_active: bool | None = None,
) -> Page[UserOut]:
    page = users_service.list_users(db, params=params, q=q, role=role, is_active=is_active)
    return Page[UserOut].build(
        [_out(u) for u in page.items], total=page.total, page=page.page, page_size=page.page_size
    )


@router.post("", response_model=UserOut, status_code=201, summary="Create a user account")
def create_user(payload: UserCreate, db: DbSession, admin: AdminUser) -> UserOut:
    return _out(users_service.create_user(db, admin, payload))


@router.get("/{user_id}", response_model=UserOut, summary="Get one user account")
def get_user(user_id: int, db: DbSession, admin: AdminUser) -> UserOut:
    return _out(users_service.get_user(db, user_id))


@router.patch("/{user_id}", response_model=UserOut, summary="Update role, name or active status")
def update_user(user_id: int, payload: UserUpdate, db: DbSession, admin: AdminUser) -> UserOut:
    return _out(users_service.update_user(db, admin, user_id, payload))


@router.post("/{user_id}/reset-password", response_model=UserOut, summary="Set a temporary password")
def reset_password(user_id: int, payload: PasswordResetRequest, db: DbSession, admin: AdminUser) -> UserOut:
    return _out(users_service.reset_password(db, admin, user_id, payload))
