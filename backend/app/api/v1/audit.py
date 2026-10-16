"""Audit log viewer. Administrators only."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import DbSession, require_roles
from app.models.audit_log import AuditLog
from app.models.user import ROLE_ADMIN, User
from app.schemas.common import Page, PageParams
from app.services.common import paginate

router = APIRouter(prefix="/audit-logs", tags=["audit"])


class AuditLogOut(BaseModel):
    id: int
    actor_user_id: int | None
    action: str
    entity: str
    entity_id: str | None
    details: str | None
    created_at: str


def list_audit_logs(
    db: Session,
    *,
    params: PageParams,
    entity: str | None,
    action: str | None,
) -> Page[AuditLog]:
    statement = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    if entity:
        statement = statement.where(AuditLog.entity == entity)
    if action:
        statement = statement.where(AuditLog.action.startswith(action))
    return paginate(db, statement, params)


@router.get("", response_model=Page[AuditLogOut], summary="Browse the audit log")
def browse(
    db: DbSession,
    _admin: Annotated[User, Depends(require_roles(ROLE_ADMIN))],
    params: Annotated[PageParams, Depends()],
    entity: Annotated[str | None, Query(max_length=64)] = None,
    action: Annotated[str | None, Query(max_length=64)] = None,
) -> Page[AuditLogOut]:
    page = list_audit_logs(db, params=params, entity=entity, action=action)
    return Page[AuditLogOut].build(
        [
            AuditLogOut(
                id=row.id,
                actor_user_id=row.actor_user_id,
                action=row.action,
                entity=row.entity,
                entity_id=row.entity_id,
                details=row.details,
                created_at=row.created_at.isoformat(),
            )
            for row in page.items
        ],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )
