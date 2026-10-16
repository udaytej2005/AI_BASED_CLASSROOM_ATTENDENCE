import pytest
from pydantic import ValidationError

from app.core.config import DEV_ONLY_SECRET, Settings


def test_defaults_are_local_friendly(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    settings = Settings(_env_file=None)
    assert settings.timezone == "Asia/Kolkata"
    assert settings.app_env == "development"
    assert settings.cors_origins == ["http://localhost:5173"]


def test_cors_origins_parsed_from_comma_separated_env(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test ,")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_invalid_timezone_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, timezone="Mars/Olympus")


def test_production_refuses_default_secret():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            secret_key=DEV_ONLY_SECRET,
            database_url="postgresql+psycopg://u:realpw@db/x",
        )


def test_production_refuses_placeholder_database_password():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            secret_key="x" * 40,
            database_url="postgresql+psycopg://attendance:change-me@localhost/x",
        )


def test_production_accepts_strong_configuration():
    settings = Settings(
        _env_file=None,
        app_env="production",
        secret_key="k" * 40,
        database_url="postgresql+psycopg://u:realpw@db/x",
    )
    assert settings.app_env == "production"
