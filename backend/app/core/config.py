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
    # Largest accepted recorded-video upload (video is processed on the server and never stored).
    max_video_upload_bytes: int = Field(default=100 * 1024 * 1024, gt=0)

    # ---- Face recognition (Phase 4). Model files are NOT in Git; see docs/face-recognition.md. ----
    # Relative paths are resolved against the repository root.
    face_detector_model_path: str = "models/face_detection_yunet_2023mar.onnx"
    face_recognizer_model_path: str = "models/face_recognition_sface_2021dec.onnx"
    # Cosine similarity needed to call a live face a registered student. 0.363 is the default used by OpenCV's
    # SFace demo; it must be re-checked on this institution's own test set before any claim is made.
    face_match_threshold: float = Field(default=0.363, ge=0.0, le=1.0)
    # Best match must beat the second-best student by this much, or the result is 'uncertain'.
    face_match_margin: float = Field(default=0.05, ge=0.0, le=1.0)
    face_recognize_every_frames: int = Field(default=10, ge=1, le=600)
    face_process_every_frames: int = Field(default=3, ge=1, le=120)

    # Enrollment quality gates (per image).
    enrollment_min_accepted_images: int = Field(default=5, ge=3, le=20)
    enrollment_max_images: int = Field(default=20, ge=5, le=50)
    quality_min_face_px: int = Field(default=80, ge=32, le=1000)
    quality_min_detector_score: float = Field(default=0.85, ge=0.0, le=1.0)
    quality_min_sharpness: float = Field(default=60.0, ge=0.0)
    quality_brightness_min: int = Field(default=50, ge=0, le=255)
    quality_brightness_max: int = Field(default=215, ge=0, le=255)
    quality_max_roll_ratio: float = Field(default=0.35, ge=0.0, le=2.0)

    # Temporal verification: a student is Present only after repeated, spread-out observations.
    temporal_min_observations: int = Field(default=5, ge=2, le=100)
    temporal_min_span_seconds: float = Field(default=2.0, ge=0.0, le=3600.0)
    temporal_min_gap_seconds: float = Field(default=0.4, ge=0.0, le=60.0)

    # Biometric retention: embeddings older than this are deleted by `python -m app.cli purge-biometrics`.
    biometric_retention_days: int = Field(default=365, ge=1, le=3650)
    # Safety cap for offline video processing.
    video_max_processed_frames: int = Field(default=20_000, ge=10, le=500_000)

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
