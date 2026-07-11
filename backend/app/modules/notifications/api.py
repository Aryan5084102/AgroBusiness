"""In-app notification endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import CurrentUser
from app.core.deps import db_session, get_current_user
from app.modules.notifications.service import NotificationService

router = APIRouter(tags=["notifications"])


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str | None
    is_read: bool
    created_at: datetime


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = Query(default=False),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> list[NotificationOut]:
    items = await NotificationService(session).list_for_user(
        organization_id=user.organization_id,
        user_id=user.user_id,
        unread_only=unread_only,
    )
    return [
        NotificationOut(
            id=n.id,
            type=n.type,
            title=n.title,
            body=n.body,
            is_read=n.is_read,
            created_at=n.created_at,
        )
        for n in items
    ]


@router.post("/{notification_id}/read", status_code=204, response_class=Response)
async def mark_read(
    notification_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> Response:
    await NotificationService(session).mark_read(
        organization_id=user.organization_id,
        user_id=user.user_id,
        notification_id=notification_id,
    )
    await session.commit()
    return Response(status_code=204)
