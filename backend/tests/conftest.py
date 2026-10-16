import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

# Tests always run against an isolated SQLite file unless TEST_DATABASE_URL is provided.
os.environ.setdefault("APP_ENV", "test")


@pytest.fixture(scope="session")
def test_database_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    return f"sqlite:///{tmp_path_factory.mktemp('db') / 'test.db'}"


@pytest.fixture
def client(test_database_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    from app.core import config
    from app.db import session as db_session

    monkeypatch.setenv("DATABASE_URL", test_database_url)
    config.get_settings.cache_clear()
    db_session.get_engine.cache_clear()
    db_session.get_session_factory.cache_clear()

    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client

    config.get_settings.cache_clear()
    db_session.get_engine.cache_clear()
    db_session.get_session_factory.cache_clear()
