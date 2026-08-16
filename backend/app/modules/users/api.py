"""User & role management endpoints. Every query is scoped to the caller's org."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas.types import Email
from app.core.context import CurrentUser
from app.core.deps import db_session, require_permission
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.security import hash_password
from app.modules.organizations.service import OrganizationProvisioningService
from app.modules.users.models import Permission, Role, RolePermission, User, UserRole

router = APIRouter(tags=["users"])


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_owner: bool
    is_active: bool
    role_code: str | None
    role_name: str | None
    last_login_at: datetime | None


class RoleOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_system: bool
    permissions: list[str]
    user_count: int


class CreateUserRequest(BaseModel):
    email: Email
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1)
    role_code: str
    branch_id: uuid.UUID | None = None


class UpdateUserRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1)
    is_active: bool | None = None
    role_code: str | None = None
    password: str | None = Field(default=None, min_length=8)


async def _roles_by_user(
    session: AsyncSession, organization_id: uuid.UUID
) -> dict[uuid.UUID, Role]:
    """First role per user — the product assigns exactly one role per user today."""
    rows = await session.execute(
        select(UserRole.user_id, Role)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.organization_id == organization_id)
    )
    mapping: dict[uuid.UUID, Role] = {}
    for user_id, role in rows.all():
        mapping.setdefault(user_id, role)
    return mapping


def _to_out(user: User, role: Role | None) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_owner=user.is_owner,
        is_active=user.is_active,
        role_code=role.code if role else ("owner" if user.is_owner else None),
        role_name=role.name if role else ("Owner" if user.is_owner else None),
        last_login_at=user.last_login_at,
    )


@router.get("", response_model=list[UserOut])
async def list_users(
    user: CurrentUser = Depends(require_permission("user.manage")),
    session: AsyncSession = Depends(db_session),
) -> list[UserOut]:
    # Tenant isolation: filter by the org from the verified token, never a param.
    result = await session.execute(
        select(User).where(User.organization_id == user.organization_id).order_by(User.full_name)
    )
    roles = await _roles_by_user(session, user.organization_id)
    return [_to_out(u, roles.get(u.id)) for u in result.scalars().all()]


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(
    user: CurrentUser = Depends(require_permission("user.manage")),
    session: AsyncSession = Depends(db_session),
) -> list[RoleOut]:
    """Roles with their permission codes — powers the role picker and RBAC matrix."""
    roles = list(
        (
            await session.execute(
                select(Role).where(Role.organization_id == user.organization_id).order_by(Role.name)
            )
        )
        .scalars()
        .all()
    )
    perm_rows = await session.execute(
        select(RolePermission.role_id, Permission.code)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(RolePermission.role_id.in_([r.id for r in roles]))
    )
    by_role: dict[uuid.UUID, list[str]] = {}
    for role_id, code in perm_rows.all():
        by_role.setdefault(role_id, []).append(code)

    count_rows = await session.execute(
        select(UserRole.role_id).where(UserRole.role_id.in_([r.id for r in roles]))
    )
    counts: dict[uuid.UUID, int] = {}
    for (role_id,) in count_rows.all():
        counts[role_id] = counts.get(role_id, 0) + 1

    return [
        RoleOut(
            id=r.id,
            code=r.code,
            name=r.name,
            description=r.description,
            is_system=r.is_system,
            permissions=sorted(by_role.get(r.id, [])),
            user_count=counts.get(r.id, 0),
        )
        for r in roles
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
    roles = await _roles_by_user(session, user.organization_id)
    return _to_out(created, roles.get(created.id))


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    payload: UpdateUserRequest,
    user: CurrentUser = Depends(require_permission("user.manage")),
    session: AsyncSession = Depends(db_session),
) -> UserOut:
    """Rename, deactivate, re-role or reset the password of a colleague."""
    target = await session.get(User, user_id)
    if target is None or target.organization_id != user.organization_id:
        raise NotFoundError("Unknown user.")
    if target.is_owner and payload.is_active is False:
        raise BusinessRuleError("The owner account cannot be deactivated.", code="owner_protected")
    if target.id == user.user_id and payload.is_active is False:
        raise BusinessRuleError("You cannot deactivate your own account.", code="self_lockout")

    if payload.full_name is not None:
        target.full_name = payload.full_name
    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.password is not None:
        target.hashed_password = hash_password(payload.password)
    if payload.role_code is not None:
        role = (
            (
                await session.execute(
                    select(Role).where(
                        Role.organization_id == user.organization_id,
                        Role.code == payload.role_code,
                    )
                )
            )
            .scalars()
            .first()
        )
        if role is None:
            raise NotFoundError(f"Unknown role: {payload.role_code}")
        await session.execute(delete(UserRole).where(UserRole.user_id == target.id))
        session.add(UserRole(user_id=target.id, role_id=role.id))

    await session.commit()
    roles = await _roles_by_user(session, user.organization_id)
    return _to_out(target, roles.get(target.id))
