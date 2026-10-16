"""Authentication endpoints: sign in, sign out, current user, and password change."""

from fastapi import APIRouter, Request, Response

from app.api.deps import SESSION_COOKIE_NAME, CurrentUserAnyState, DbSession
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import hash_password, validate_password_policy, verify_password
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, UserOut
from app.services import audit
from app.services.auth import (
    authenticate,
    create_session,
    revoke_all_sessions_for_user,
    revoke_session,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
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


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,  # not readable from JavaScript
        secure=settings.app_env == "production",  # HTTPS only in production
        samesite="lax",  # blocks most cross-site form posts
        path="/",
    )


@router.post("/login", response_model=UserOut, summary="Sign in with email and password")
def login(payload: LoginRequest, response: Response, db: DbSession) -> UserOut:
    user = authenticate(db, payload.email, payload.password)
    token = create_session(db, user)
    _set_session_cookie(response, token)
    audit.record_audit(db, actor_user_id=user.id, action="auth.login", entity="user", entity_id=user.id)
    db.commit()
    return _user_out(user)


@router.post("/logout", summary="Sign out and revoke the current session")
def logout(request: Request, response: Response, db: DbSession, user: CurrentUserAnyState) -> dict[str, str]:
    revoke_session(db, request.cookies.get(SESSION_COOKIE_NAME))
    audit.record_audit(db, actor_user_id=user.id, action="auth.logout", entity="user", entity_id=user.id)
    db.commit()
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"status": "signed_out"}


@router.get("/me", response_model=UserOut, summary="The signed-in user")
def me(user: CurrentUserAnyState) -> UserOut:
    return _user_out(user)


@router.post("/change-password", response_model=UserOut, summary="Change the signed-in user's password")
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    db: DbSession,
    user: CurrentUserAnyState,
) -> UserOut:
    if not verify_password(user.password_hash, payload.current_password):
        raise AppError(400, "The current password is incorrect.")
    try:
        validate_password_policy(payload.new_password)
    except ValueError as exc:
        raise AppError(422, str(exc)) from exc
    if payload.new_password == payload.current_password:
        raise AppError(422, "The new password must be different from the current password.")

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    # Changing the password signs out every other session, including any session that may be compromised.
    revoke_all_sessions_for_user(db, user.id)
    token = create_session(db, user)
    audit.record_audit(
        db, actor_user_id=user.id, action="auth.password_changed", entity="user", entity_id=user.id
    )
    db.commit()
    _set_session_cookie(response, token)
    return _user_out(user)
