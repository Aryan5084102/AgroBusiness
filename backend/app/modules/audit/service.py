"""Audit logging service. Writes append-only audit records."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        action: str,
        organization_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        reason: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        self._session.add(
            AuditLog(
                action=action,
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                entity_type=entity_type,
                entity_id=entity_id,
                before=before,
                after=after,
                reason=reason,
                ip_address=ip_address,
                user_agent=user_agent,
                correlation_id=correlation_id,
            )
        )
        await self._session.flush()
