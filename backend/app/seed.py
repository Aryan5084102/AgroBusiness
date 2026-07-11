"""Development seed data. NEVER run automatically in production.

Creates one organization, its default roles/permissions, an owner, and the
standard demo users from the specification. Run with:

    python -m app.seed
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.database import get_engine, get_sessionmaker
from app.modules.organizations.service import OrganizationProvisioningService

DEMO_PASSWORD = "AgriFlow@123"  # documented development-only password

DEMO_USERS = [
    ("admin@agriflow.local", "Admin User", "administrator"),
    ("billing@agriflow.local", "Billing Operator", "billing_operator"),
    ("inventory@agriflow.local", "Inventory Manager", "inventory_manager"),
    ("accountant@agriflow.local", "Accountant", "accountant"),
    ("sales@agriflow.local", "Wholesale Salesperson", "wholesale_salesperson"),
    ("technician@agriflow.local", "Service Technician", "service_technician"),
    ("auditor@agriflow.local", "Auditor", "auditor"),
]


async def seed() -> None:
    settings = get_settings()
    if settings.is_production:
        raise RuntimeError("Refusing to seed demo data in production.")

    factory = get_sessionmaker()
    async with factory() as session:
        service = OrganizationProvisioningService(session)
        result = await service.provision(
            org_name="AgriFlow Demo Traders",
            owner_email="owner@agriflow.local",
            owner_password=DEMO_PASSWORD,
            owner_name="Business Owner",
        )
        for email, name, role_code in DEMO_USERS:
            await service.create_user(
                organization_id=result.organization.id,
                email=email,
                password=DEMO_PASSWORD,
                full_name=name,
                role_code=role_code,
                branch_id=result.branch.id,
            )
        await session.commit()
        print(f"Seeded org {result.organization.id} with {len(DEMO_USERS) + 1} users.")

    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(seed())
