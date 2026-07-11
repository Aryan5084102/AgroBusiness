"""In-app notification service (create, list, mark read)."""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import Notification


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        organization_id: uuid.UUID,
        type: str,
        title: str,
        body: str | None = None,
        user_id: uuid.UUID | None = None,
    ) -> Notification:
        notification = Notification(
            organization_id=organization_id,
            user_id=user_id,
            type=type,
            title=title,
            body=body,
        )
        self._session.add(notification)
        await self._session.flush()
        return notification

    async def list_for_user(
        self, *, organization_id: uuid.UUID, user_id: uuid.UUID, unread_only: bool = False
    ) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(
                Notification.organization_id == organization_id,
                or_(Notification.user_id == user_id, Notification.user_id.is_(None)),
            )
            .order_by(Notification.created_at.desc())
        )
        if unread_only:
            stmt = stmt.where(Notification.is_read.is_(False))
        return list((await self._session.execute(stmt)).scalars().all())

    async def mark_read(
        self, *, organization_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> None:
        await self._session.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.organization_id == organization_id,
                or_(Notification.user_id == user_id, Notification.user_id.is_(None)),
            )
            .values(is_read=True)
        )
        await self._session.flush()
