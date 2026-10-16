"""Shared test fixtures.

- The schema is built with the real Alembic migrations (not create_all), so tests also exercise migrations.
- Tests run on SQLite by default. Set TEST_DATABASE_URL to run the same tests against PostgreSQL.
- Every test starts with empty tables.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from alembic import command
from alembic.config import Config
from app.core import config as app_config
from app.core.security import hash_password
from app.db import session as db_session
from app.db.base import Base
from app.models.user import User

os.environ.setdefault("APP_ENV", "test")

PASSWORD = "Correct-Horse-Battery-1"  # meets policy; used by every fixture account


def _reset_caches() -> None:
    app_config.get_settings.cache_clear()
    db_session.get_engine.cache_clear()
    db_session.get_session_factory.cache_clear()


@pytest.fixture(scope="session")
def test_database_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    return f"sqlite:///{tmp_path_factory.mktemp('db') / 'test.db'}"


@pytest.fixture(scope="session", autouse=True)
def migrated_database(test_database_url: str) -> Iterator[None]:
    previous_url = os.environ.get("DATABASE_URL")
    previous_env = os.environ.get("APP_ENV")
    os.environ["DATABASE_URL"] = test_database_url
    os.environ["APP_ENV"] = "test"
    _reset_caches()
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield
    _reset_caches()
    for key, value in (("DATABASE_URL", previous_url), ("APP_ENV", previous_env)):
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture(autouse=True)
def clean_tables(migrated_database: None) -> Iterator[None]:
    """Empty every table before each test (children first, so foreign keys are respected)."""
    with db_session.get_session_factory()() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    yield


@pytest.fixture
def app(migrated_database: None) -> FastAPI:
    from app.main import create_app

    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db() -> Iterator[Session]:
    session = db_session.get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def make_user(
    db: Session,
    *,
    email: str,
    role: str,
    full_name: str | None = None,
    password: str = PASSWORD,
    must_change_password: bool = False,
    is_active: bool = True,
) -> User:
    user = User(
        email=email,
        full_name=full_name or email.split("@")[0].replace(".", " ").title(),
        role=role,
        password_hash=hash_password(password),
        must_change_password=must_change_password,
        is_active=is_active,
        is_synthetic=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(app: FastAPI, email: str, password: str = PASSWORD) -> TestClient:
    """Return a new client that is signed in as the given user (each client keeps its own cookie jar)."""
    test_client = TestClient(app)
    response = test_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return test_client


@pytest.fixture
def department_id(db: Session) -> int:
    from app.models.department import Department

    department = Department(code="CSE", name="Computer Science and Engineering", is_active=True)
    db.add(department)
    db.commit()
    return department.id
