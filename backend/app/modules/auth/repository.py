"""Data access for authentication (users, sessions, refresh tokens, permissions)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import RefreshToken, Session
from app.modules.users.models import (
    Permission,
    Role,
    RolePermission,
    User,
    UserBranch,
    UserRole,
)


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user_by_email(self, organization_id: uuid.UUID | None, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        if organization_id is not None:
            stmt = stmt.where(User.organization_id == organization_id)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_user_permissions(self, user_id: uuid.UUID) -> list[str]:
        stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .distinct()
        )
        result = await self._session.execute(stmt)
        return sorted(result.scalars().all())

    async def get_user_branch_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = select(UserBranch.branch_id).where(UserBranch.user_id == user_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create_session(self, session_obj: Session) -> None:
        self._session.add(session_obj)
        await self._session.flush()

    async def get_session(self, session_id: uuid.UUID) -> Session | None:
        return await self._session.get(Session, session_id)

    async def add_refresh_token(self, token: RefreshToken) -> None:
        self._session.add(token)
        await self._session.flush()

    async def get_refresh_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def revoke_session_tokens(self, session_id: uuid.UUID, now: object) -> None:
        from sqlalchemy import update

        await self._session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.session_id == session_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
