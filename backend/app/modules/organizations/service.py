"""Organization provisioning: create org, seed permissions/roles, create owner.

Used by the demo seed and by tests. In production, organization onboarding is an
owner-only flow; this service centralises the invariant that every org is created
with the full permission catalogue and default roles.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import DEFAULT_ROLES, PERMISSIONS
from app.core.security import hash_password
from app.modules.organizations.models import Branch, Organization
from app.modules.users.models import (
    Permission,
    Role,
    RolePermission,
    User,
    UserBranch,
    UserRole,
)


@dataclass
class ProvisionResult:
    organization: Organization
    owner: User
    branch: Branch
    roles: dict[str, Role]


class OrganizationProvisioningService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_permissions(self) -> dict[str, Permission]:
        """Idempotently ensure the global permission catalogue exists."""
        existing = {
            p.code: p for p in (await self._session.execute(select(Permission))).scalars().all()
        }
        for pdef in PERMISSIONS:
            if pdef.code not in existing:
                perm = Permission(
                    code=pdef.code, category=pdef.category, description=pdef.description
                )
                self._session.add(perm)
                existing[pdef.code] = perm
        await self._session.flush()
        return existing

    async def provision(
        self,
        *,
        org_name: str,
        owner_email: str,
        owner_password: str,
        owner_name: str,
        branch_name: str = "Main Branch",
        branch_code: str = "MAIN",
    ) -> ProvisionResult:
        permissions = await self.ensure_permissions()

        org = Organization(name=org_name)
        self._session.add(org)
        await self._session.flush()

        branch = Branch(organization_id=org.id, name=branch_name, code=branch_code)
        self._session.add(branch)
        await self._session.flush()

        roles: dict[str, Role] = {}
        for code, spec in DEFAULT_ROLES.items():
            role = Role(
                organization_id=org.id,
                name=spec["name"],
                code=code,
                is_system=True,
            )
            self._session.add(role)
            await self._session.flush()
            for perm_code in spec["permissions"]:
                self._session.add(
                    RolePermission(role_id=role.id, permission_id=permissions[perm_code].id)
                )
            roles[code] = role
        await self._session.flush()

        owner = User(
            organization_id=org.id,
            email=owner_email,
            full_name=owner_name,
            hashed_password=hash_password(owner_password),
            is_owner=True,
        )
        self._session.add(owner)
        await self._session.flush()

        self._session.add(UserRole(user_id=owner.id, role_id=roles["owner"].id))
        self._session.add(UserBranch(user_id=owner.id, branch_id=branch.id))
        await self._session.flush()

        return ProvisionResult(organization=org, owner=owner, branch=branch, roles=roles)

    async def create_user(
        self,
        *,
        organization_id: uuid.UUID,
        email: str,
        password: str,
        full_name: str,
        role_code: str,
        branch_id: uuid.UUID | None,
    ) -> User:
        role = (
            (
                await self._session.execute(
                    select(Role).where(
                        Role.organization_id == organization_id, Role.code == role_code
                    )
                )
            )
            .scalars()
            .first()
        )
        if role is None:
            raise ValueError(f"Unknown role: {role_code}")

        user = User(
            organization_id=organization_id,
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
        )
        self._session.add(user)
        await self._session.flush()
        self._session.add(UserRole(user_id=user.id, role_id=role.id))
        if branch_id is not None:
            self._session.add(UserBranch(user_id=user.id, branch_id=branch_id))
        await self._session.flush()
        return user
