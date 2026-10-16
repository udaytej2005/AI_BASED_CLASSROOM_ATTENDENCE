"""Helpers shared by services."""

from __future__ import annotations

from typing import TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.schemas.common import Page, PageParams

T = TypeVar("T")


def paginate(db: Session, statement: Select[tuple[T]], params: PageParams) -> Page[T]:
    """Run a SELECT with LIMIT/OFFSET and report the total number of matching rows."""
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    rows = db.scalars(statement.limit(params.page_size).offset(params.offset)).all()
    return Page.build(list(rows), total=total, page=params.page, page_size=params.page_size)
