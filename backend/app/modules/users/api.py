"""User management endpoints. Every query is scoped to the caller's org."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas.types import Email
from app.core.context import CurrentUser
from app.core.deps import db_session, require_permission
from app.modules.organizations.service import OrganizationProvisioningService
from app.modules.users.models import User

router = APIRouter(tags=["users"])


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_owner: bool
    is_active: bool


class CreateUserRequest(BaseModel):
    email: Email
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1)
    role_code: str
    branch_id: uuid.UUID | None = None


@router.get("", response_model=list[UserOut])
async def list_users(
    user: CurrentUser = Depends(require_permission("user.manage")),
    session: AsyncSession = Depends(db_session),
) -> list[UserOut]:
    # Tenant isolation: filter by the org from the verified token, never a param.
    result = await session.execute(select(User).where(User.organization_id == user.organization_id))
    return [
        UserOut(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            is_owner=u.is_owner,
            is_active=u.is_active,
        )
        for u in result.scalars().all()
    ]


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    payload: CreateUserRequest,
    user: CurrentUser = Depends(require_permission("user.manage")),
    session: AsyncSession = Depends(db_session),
) -> UserOut:
    service = OrganizationProvisioningService(session)
    created = await service.create_user(
        organization_id=user.organization_id,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        role_code=payload.role_code,
        branch_id=payload.branch_id,
    )
    await session.commit()
    return UserOut(
        id=created.id,
        email=created.email,
        full_name=created.full_name,
        is_owner=created.is_owner,
        is_active=created.is_active,
    )
