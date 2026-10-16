"""Authentication: sign-in, sessions, lockout, forced password change and request-origin checks."""

from datetime import timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_session_token
from app.models.auth_session import AuthSession
from app.models.base import utcnow
from app.models.user import User
from tests.conftest import PASSWORD, login, make_user

LOGIN = "/api/v1/auth/login"


def test_login_sets_hardened_session_cookie_and_returns_user(app: FastAPI, db: Session):
    make_user(db, email="admin@example.test", role="admin")
    client = TestClient(app)

    response = client.post(LOGIN, json={"email": "Admin@Example.Test", "password": PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "admin@example.test"
    assert body["role"] == "admin"
    assert PASSWORD not in response.text
    assert "password_hash" not in body
    set_cookie = response.headers["set-cookie"].lower()
    assert "sca_session=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "secure" not in set_cookie  # only enforced in production


def test_session_token_is_stored_only_as_hash(app: FastAPI, db: Session):
    user = make_user(db, email="hash.check@example.test", role="faculty")
    client = login(app, user.email)
    token = client.cookies.get("sca_session")

    stored = db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)).all()
    assert len(stored) == 1
    assert stored[0].token_hash == hash_session_token(token)
    assert token not in stored[0].token_hash


def test_wrong_password_unknown_email_and_inactive_account_give_the_same_message(app: FastAPI, db: Session):
    make_user(db, email="real@example.test", role="faculty")
    make_user(db, email="inactive@example.test", role="faculty", is_active=False)
    client = TestClient(app)

    wrong = client.post(LOGIN, json={"email": "real@example.test", "password": "nope-nope-nope"})
    unknown = client.post(LOGIN, json={"email": "nobody@example.test", "password": "nope-nope-nope"})
    inactive = client.post(LOGIN, json={"email": "inactive@example.test", "password": PASSWORD})

    for response in (wrong, unknown, inactive):
        assert response.status_code == 401
        assert response.json() == {"detail": "Email or password is incorrect."}


def test_invalid_email_format_is_rejected_by_validation(client: TestClient):
    response = client.post(LOGIN, json={"email": "not-an-email", "password": "x"})
    assert response.status_code == 422


def test_account_locks_after_repeated_failures_and_correct_password_is_refused_until_expiry(
    app: FastAPI, db: Session
):
    make_user(db, email="locked@example.test", role="faculty")
    client = TestClient(app)

    for _ in range(5):  # login_max_failed_attempts defaults to 5
        assert (
            client.post(LOGIN, json={"email": "locked@example.test", "password": "wrong-wrong-1"}).status_code
            == 401
        )

    locked = client.post(LOGIN, json={"email": "locked@example.test", "password": PASSWORD})
    assert locked.status_code == 429

    # After the lockout window has passed, the correct password works again.
    user = db.scalar(select(User).where(User.email == "locked@example.test"))
    user.locked_until = utcnow() - timedelta(seconds=1)
    db.commit()
    assert client.post(LOGIN, json={"email": "locked@example.test", "password": PASSWORD}).status_code == 200


def test_successful_login_resets_failure_counter(app: FastAPI, db: Session):
    make_user(db, email="resets@example.test", role="faculty")
    client = TestClient(app)
    for _ in range(3):
        client.post(LOGIN, json={"email": "resets@example.test", "password": "wrong-wrong-1"})
    assert client.post(LOGIN, json={"email": "resets@example.test", "password": PASSWORD}).status_code == 200
    db.expire_all()
    user = db.scalar(select(User).where(User.email == "resets@example.test"))
    assert user.failed_login_count == 0


def test_me_requires_a_session_and_logout_revokes_it(app: FastAPI, db: Session):
    make_user(db, email="logout@example.test", role="student")
    client = login(app, "logout@example.test")
    assert client.get("/api/v1/auth/me").status_code == 200

    assert client.post("/api/v1/auth/logout").status_code == 200

    # The old cookie value must no longer work, even if it were copied before logout.
    replay = TestClient(app)
    replay.cookies.set("sca_session", "stolen-or-old-token-value")
    assert replay.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401


def test_expired_session_is_rejected(app: FastAPI, db: Session):
    user = make_user(db, email="expired@example.test", role="student")
    client = login(app, user.email)
    for session_row in db.scalars(select(AuthSession)).all():
        session_row.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_deactivated_user_loses_access_immediately(app: FastAPI, db: Session):
    user = make_user(db, email="gone@example.test", role="faculty")
    client = login(app, user.email)
    user.is_active = False
    db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_forced_password_change_blocks_everything_except_password_endpoints(app: FastAPI, db: Session):
    make_user(db, email="new.user@example.test", role="student", must_change_password=True)
    client = login(app, "new.user@example.test")

    assert client.get("/api/v1/auth/me").json()["must_change_password"] is True
    assert client.get("/api/v1/students/me").status_code == 403
    assert client.get("/api/v1/departments").status_code == 403


def test_change_password_clears_flag_revokes_other_sessions_and_issues_new_cookie(app: FastAPI, db: Session):
    user = make_user(db, email="change.me@example.test", role="student", must_change_password=True)
    old_client = login(app, user.email)
    old_token = old_client.cookies.get("sca_session")

    response = old_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "Brand-New-Passphrase-2"},
    )

    assert response.status_code == 200
    assert response.json()["must_change_password"] is False
    assert old_client.get("/api/v1/departments").status_code == 200  # new cookie works
    stale = TestClient(app)
    stale.cookies.set("sca_session", old_token)
    assert stale.get("/api/v1/auth/me").status_code == 401  # old session was revoked
    assert (
        TestClient(app)
        .post(LOGIN, json={"email": user.email, "password": "Brand-New-Passphrase-2"})
        .status_code
        == 200
    )


def test_change_password_rejects_wrong_current_password_and_weak_new_password(app: FastAPI, db: Session):
    user = make_user(db, email="weak.change@example.test", role="faculty")
    client = login(app, user.email)

    wrong_current = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "not-the-password", "new_password": "Brand-New-Passphrase-2"},
    )
    assert wrong_current.status_code == 400

    too_short = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "short1"},
    )
    assert too_short.status_code == 422

    same_password = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": PASSWORD, "new_password": PASSWORD},
    )
    assert same_password.status_code == 422


def test_cross_site_state_changing_request_is_rejected(app: FastAPI, db: Session):
    make_user(db, email="csrf@example.test", role="admin")
    client = login(app, "csrf@example.test")

    evil = client.post(
        "/api/v1/departments",
        json={"code": "XX", "name": "Evil Dept"},
        headers={"Origin": "https://evil.example"},
    )
    assert evil.status_code == 403

    same_host = client.post(
        "/api/v1/departments",
        json={"code": "OK1", "name": "Allowed Dept"},
        headers={"Origin": "http://testserver"},
    )
    assert same_host.status_code == 201


def test_unauthenticated_requests_are_refused(client: TestClient):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/students").status_code == 401
    assert client.get("/api/v1/users").status_code == 401
