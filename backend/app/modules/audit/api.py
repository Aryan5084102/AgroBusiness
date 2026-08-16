"""Audit-log endpoints (RBAC: ``audit.view``). Read-only by design."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import CurrentUser
from app.core.deps import db_session, require_permission
from app.modules.audit.models import AuditLog
from app.modules.users.models import User

router = APIRouter(tags=["audit"])


class AuditLogOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    action: str
    actor_user_id: uuid.UUID | None
    actor_name: str | None
    entity_type: str | None
    entity_id: str | None
    reason: str | None
    ip_address: str | None
    correlation_id: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None


class AuditLogPage(BaseModel):
    items: list[AuditLogOut]
    total: int
    limit: int
    offset: int
    actions: list[str]


@router.get("/logs", response_model=AuditLogPage)
async def list_logs(
    action: str | None = Query(default=None, max_length=80),
    actor_user_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_permission("audit.view")),
    session: AsyncSession = Depends(db_session),
) -> AuditLogPage:
    base = (
        select(AuditLog, User.full_name)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .where(AuditLog.organization_id == user.organization_id)
    )
    if action:
        base = base.where(AuditLog.action == action)
    if actor_user_id is not None:
        base = base.where(AuditLog.actor_user_id == actor_user_id)
    if date_from is not None:
        base = base.where(func.date(AuditLog.created_at) >= date_from)
    if date_to is not None:
        base = base.where(func.date(AuditLog.created_at) <= date_to)

    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    rows = await session.execute(
        base.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    )
    # Distinct actions power the filter dropdown without a second round trip.
    action_rows = await session.execute(
        select(AuditLog.action)
        .where(AuditLog.organization_id == user.organization_id)
        .distinct()
        .order_by(AuditLog.action)
    )
    return AuditLogPage(
        items=[
            AuditLogOut(
                id=log.id,
                created_at=log.created_at,
                action=log.action,
                actor_user_id=log.actor_user_id,
                actor_name=actor_name,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                reason=log.reason,
                ip_address=log.ip_address,
                correlation_id=log.correlation_id,
                before=log.before,
                after=log.after,
            )
            for log, actor_name in rows.all()
        ],
        total=int(total or 0),
        limit=limit,
        offset=offset,
        actions=list(action_rows.scalars().all()),
    )
