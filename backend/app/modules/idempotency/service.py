"""Idempotency helper: look up a prior result or reserve a new key."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.idempotency.models import IdempotencyKey


class IdempotencyService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find(self, *, organization_id: uuid.UUID, key: str) -> IdempotencyKey | None:
        stmt = select(IdempotencyKey).where(
            IdempotencyKey.organization_id == organization_id,
            IdempotencyKey.key == key,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def record(
        self,
        *,
        organization_id: uuid.UUID,
        key: str,
        endpoint: str,
        entity_type: str,
        entity_id: uuid.UUID,
    ) -> None:
        self._session.add(
            IdempotencyKey(
                organization_id=organization_id,
                key=key,
                endpoint=endpoint,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        )
        await self._session.flush()
