"""Health endpoints. These are public and must never expose secrets or connection strings."""

from datetime import UTC, datetime

from fastapi import APIRouter

from app.core.config import get_settings
from app.db.session import check_database

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="Liveness and basic application information")
def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.app_env,
        "timezone": settings.timezone,
        "server_time_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }


@router.get("/database", summary="Database connectivity check")
def database_health() -> dict[str, str]:
    connected = check_database()
    return {
        "status": "ok" if connected else "unavailable",
        "database": "connected" if connected else "unreachable",
    }
