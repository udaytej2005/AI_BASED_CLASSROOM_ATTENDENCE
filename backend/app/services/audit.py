"""Writes audit records. Callers pass only non-sensitive identifiers and field names, never secrets."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

FORBIDDEN_KEY_FRAGMENTS = ("password", "token", "secret", "embedding", "image")


def record_audit(
    db: Session,
    *,
    actor_user_id: int | None,
    action: str,
    entity: str,
    entity_id: int | str | None,
    details: dict[str, Any] | None = None,
) -> None:
    safe_details: str | None = None
    if details:
        for key in details:
            if any(fragment in key.lower() for fragment in FORBIDDEN_KEY_FRAGMENTS):
                raise ValueError(f"Audit details must not contain sensitive field '{key}'.")
        safe_details = json.dumps(details, default=str, sort_keys=True)
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity=entity,
            entity_id=None if entity_id is None else str(entity_id),
            details=safe_details,
        )
    )
