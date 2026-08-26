"""The demo logins converge on an already-seeded database.

``seed()`` skips a database that already holds an organization, so a demo that
was deployed before the roles collapsed to three kept serving the old staff
accounts: the login page offered ``counter@``/``store@`` while the database
still held ``billing@``/``inventory@``, and both buttons returned 401.
``_reconcile_demo_users`` is what closes that gap on every boot.
"""

from __future__ import annotations

import uuid

import pytest
from app.core.database import get_sessionmaker
from app.core.security import hash_password, verify_password
from app.modules.organizations.service import OrganizationProvisioningService
from app.modules.users.models import Role, User, UserRole
from app.seed import DEMO_PASSWORD, ORG_NAME, OWNER_EMAIL, _reconcile_demo_users
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def _role_codes(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    stmt = (
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    return sorted((await session.execute(stmt)).scalars().all())


async def _user(session: AsyncSession, email: str) -> User | None:
    return (await session.execute(select(User).where(User.email == email))).scalars().first()


@pytest.fixture
async def legacy_demo_org(db_ready: None) -> None:
    """A database in the shape the live demo was left in by migration c9f1a70b34d2.

    The role rows were renamed in place, so the staff users still work — under
    the emails the login page has since stopped offering.
    """
    factory = get_sessionmaker()
    async with factory() as session:
        provisioning = OrganizationProvisioningService(session)
        result = await provisioning.provision(
            org_name=ORG_NAME,
            owner_email=OWNER_EMAIL,
            owner_password=DEMO_PASSWORD,
            owner_name="Business Owner",
        )
        await provisioning.create_user(
            organization_id=result.organization.id,
            email="billing@agriflow.local",
            password=DEMO_PASSWORD,
            full_name="Billing Operator",
            role_code="counter_sales",
            branch_id=result.branch.id,
        )
        # A user of one of the five retired roles: still active, no role left.
        session.add(
            User(
                organization_id=result.organization.id,
                email="admin@agriflow.local",
                full_name="Admin User",
                hashed_password=hash_password(DEMO_PASSWORD),
            )
        )
        await session.commit()


async def test_legacy_account_is_renamed_not_duplicated(legacy_demo_org: None) -> None:
    factory = get_sessionmaker()
    async with factory() as session:
        legacy = await _user(session, "billing@agriflow.local")
        assert legacy is not None
        legacy_id = legacy.id

        await _reconcile_demo_users(session)

    async with factory() as session:
        counter = await _user(session, "counter@agriflow.local")
        assert counter is not None
        # Same row: the seeded invoices and audit entries still point at it.
        assert counter.id == legacy_id
        assert counter.full_name == "Counter Staff"
        assert counter.is_active
        assert await _role_codes(session, counter.id) == ["counter_sales"]
        assert await _user(session, "billing@agriflow.local") is None


async def test_missing_account_is_created_with_a_working_password(
    legacy_demo_org: None,
) -> None:
    factory = get_sessionmaker()
    async with factory() as session:
        assert await _user(session, "store@agriflow.local") is None
        await _reconcile_demo_users(session)

    async with factory() as session:
        store = await _user(session, "store@agriflow.local")
        assert store is not None
        assert verify_password(DEMO_PASSWORD, store.hashed_password)
        assert await _role_codes(session, store.id) == ["store_inventory"]


async def test_retired_demo_account_is_deactivated(legacy_demo_org: None) -> None:
    factory = get_sessionmaker()
    async with factory() as session:
        await _reconcile_demo_users(session)

    async with factory() as session:
        admin = await _user(session, "admin@agriflow.local")
        assert admin is not None  # kept: seeded history references it
        assert not admin.is_active


async def test_locked_or_stale_account_is_restored(legacy_demo_org: None) -> None:
    factory = get_sessionmaker()
    async with factory() as session:
        legacy = await _user(session, "billing@agriflow.local")
        assert legacy is not None
        legacy.hashed_password = hash_password("something-else")
        legacy.is_active = False
        legacy.failed_login_count = 5
        owner_role_id = await session.scalar(select(Role.id).where(Role.code == "owner"))
        session.add(UserRole(user_id=legacy.id, role_id=owner_role_id))
        await session.commit()

        await _reconcile_demo_users(session)

    async with factory() as session:
        counter = await _user(session, "counter@agriflow.local")
        assert counter is not None
        assert counter.is_active
        assert counter.failed_login_count == 0
        assert counter.locked_until is None
        assert verify_password(DEMO_PASSWORD, counter.hashed_password)
        # Exactly the role the login page advertises — the stray owner grant goes.
        assert await _role_codes(session, counter.id) == ["counter_sales"]


async def test_second_run_changes_nothing(legacy_demo_org: None) -> None:
    factory = get_sessionmaker()
    async with factory() as session:
        assert await _reconcile_demo_users(session) != []
        # SEED_ON_START runs this on every container boot; it must settle.
        assert await _reconcile_demo_users(session) == []
