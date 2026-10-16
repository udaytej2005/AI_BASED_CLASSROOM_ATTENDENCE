"""Application configuration loaded from environment variables (and an optional .env file).

Every setting has a safe default for local development. Secrets are never given
real default values in code; see .env.example for the documented placeholders.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "0.1.0"
DEV_ONLY_SECRET = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Smart Classroom Attendance API"
    app_version: str = APP_VERSION
    app_env: Literal["development", "test", "production"] = "development"

    # PostgreSQL is the intended database. A SQLite URL is accepted only as a documented fallback.
    database_url: str = "postgresql+psycopg://attendance:change-me@localhost:5432/attendance"

    # Institutional timezone used to interpret timetable times and render timestamps.
    timezone: str = "Asia/Kolkata"

    # Comma-separated list of browser origins allowed to call the API (CORS).
    cors_origins_raw: str = Field(default="http://localhost:5173", validation_alias="CORS_ORIGINS")

    # Used to sign session tokens in later phases. Must be replaced in production.
    secret_key: str = DEV_ONLY_SECRET

    # Login sessions: lifetime and brute-force protection.
    session_ttl_minutes: int = Field(default=480, ge=5, le=60 * 24)
    login_max_failed_attempts: int = Field(default=5, ge=3, le=20)
    login_lockout_minutes: int = Field(default=15, ge=1, le=24 * 60)

    # Maximum accepted size of a request body in bytes (protects against oversized uploads).
    max_request_bytes: int = Field(default=10 * 1024 * 1024, gt=0)

    @property
    def cors_origins(self) -> list[str]:
        """Parsed list of allowed origins from the comma-separated CORS_ORIGINS setting."""
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown IANA timezone: {value!r}") from exc
        return value

    @model_validator(mode="after")
    def _production_safety(self) -> Settings:
        if self.app_env == "production":
            if self.secret_key == DEV_ONLY_SECRET or len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY must be set to a random value of at least 32 characters in production."
                )
            if "change-me" in self.database_url:
                raise ValueError("DATABASE_URL still contains the placeholder password in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
