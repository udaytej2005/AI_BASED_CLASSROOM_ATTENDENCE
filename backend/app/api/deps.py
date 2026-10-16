"""FastAPI dependencies: database session, current user and role-based authorisation.

Authorisation is enforced here on the server. Hiding a button in the frontend is never sufficient.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import AppError, Forbidden
from app.db.session import get_db
from app.models.user import User
from app.services.auth import get_user_for_token

SESSION_COOKIE_NAME = "sca_session"

DbSession = Annotated[Session, Depends(get_db)]


def _user_from_request(request: Request, db: Session) -> User:
    user = get_user_for_token(db, request.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        raise AppError(401, "Sign in is required.")
    return user


def get_current_user(request: Request, db: DbSession) -> User:
    """The signed-in user. Refuses access while a forced password change is pending."""
    user = _user_from_request(request, db)
    if user.must_change_password:
        raise AppError(403, "You must change your password before continuing.")
    return user


def get_current_user_any_state(request: Request, db: DbSession) -> User:
    """Signed-in user even if a password change is pending. Only for the auth endpoints."""
    return _user_from_request(request, db)


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserAnyState = Annotated[User, Depends(get_current_user_any_state)]


def require_roles(*roles: str) -> Callable[[CurrentUser], User]:
    allowed = set(roles)

    def checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise Forbidden()
        return user

    return checker
