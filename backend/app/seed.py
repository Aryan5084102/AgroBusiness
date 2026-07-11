"""Development seed data. NEVER run automatically in production.

Creates one organization, its default roles/permissions, an owner, the standard
demo users, plus demo business data (warehouse, products, opening stock,
customers and suppliers) so the UI is immediately usable. Run with:

    python -m app.seed
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

from app.core.config import get_settings
from app.core.database import get_engine, get_sessionmaker
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductCategoryKind,
    Unit,
)
from app.modules.customers.models import Customer, CustomerType
from app.modules.inventory.service import InventoryService
from app.modules.organizations.models import Warehouse
from app.modules.organizations.service import OrganizationProvisioningService
from app.modules.suppliers.models import Supplier

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

# (name, sku, kind, retail, wholesale, mrp, gst%, opening stock, tracks_batches)
DEMO_PRODUCTS = [
    (
        "Hybrid Maize Seed 1kg",
        "SEED-MZ-1",
        ProductCategoryKind.SEED,
        "480",
        "430",
        "500",
        "5",
        "120",
        True,
    ),
    (
        "Paddy Seed 5kg",
        "SEED-PD-5",
        ProductCategoryKind.SEED,
        "1100",
        "990",
        "1200",
        "5",
        "80",
        True,
    ),
    (
        "Urea 50kg Bag",
        "FERT-UREA-50",
        ProductCategoryKind.FERTILIZER,
        "300",
        "270",
        "300",
        "5",
        "200",
        True,
    ),
    (
        "DAP 50kg Bag",
        "FERT-DAP-50",
        ProductCategoryKind.FERTILIZER,
        "1350",
        "1290",
        "1400",
        "5",
        "150",
        True,
    ),
    (
        "Neem Oil 500ml",
        "PEST-NEEM-500",
        ProductCategoryKind.PESTICIDE,
        "220",
        "195",
        "250",
        "18",
        "60",
        True,
    ),
    (
        "Glyphosate 1L",
        "HERB-GLY-1",
        ProductCategoryKind.HERBICIDE,
        "560",
        "520",
        "600",
        "18",
        "45",
        True,
    ),
    (
        "Copper Fungicide 1kg",
        "FUNG-CU-1",
        ProductCategoryKind.FUNGICIDE,
        "340",
        "300",
        "360",
        "18",
        "40",
        True,
    ),
    (
        "Knapsack Sprayer 16L",
        "MACH-SPR-16",
        ProductCategoryKind.MACHINE,
        "2400",
        "2150",
        "2600",
        "18",
        "15",
        False,
    ),
    (
        "Sprayer Nozzle",
        "SPARE-NOZ",
        ProductCategoryKind.SPARE_PART,
        "150",
        "120",
        "180",
        "18",
        "100",
        False,
    ),
    (
        "Garden Trowel",
        "TOOL-TRWL",
        ProductCategoryKind.TOOL,
        "180",
        "150",
        "200",
        "18",
        "70",
        False,
    ),
]

DEMO_CUSTOMERS = [
    ("CUST-WALK", "Walk-in Customer", CustomerType.WALK_IN, "0"),
    ("CUST-RAVI", "Ravi Kumar (Farmer)", CustomerType.FARMER, "0"),
    ("DLR-GREEN", "Green Agro Dealers", CustomerType.DEALER, "100000"),
    ("DLR-KISAN", "Kisan Traders", CustomerType.DEALER, "50000"),
]

DEMO_SUPPLIERS = [
    ("SUP-AGRI", "AgriSeeds Pvt Ltd"),
    ("SUP-IFFCO", "IFFCO Distributors"),
    ("SUP-BAYER", "Bayer CropScience"),
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
        org_id = result.organization.id
        for email, name, role_code in DEMO_USERS:
            await service.create_user(
                organization_id=org_id,
                email=email,
                password=DEMO_PASSWORD,
                full_name=name,
                role_code=role_code,
                branch_id=result.branch.id,
            )

        # Business data: a shop, a base unit, products, stock, customers, suppliers.
        unit = Unit(organization_id=org_id, code="pcs", name="Pieces")
        shop = Warehouse(
            organization_id=org_id, branch_id=result.branch.id, name="Main Shop", code="SHOP"
        )
        session.add_all([unit, shop])
        await session.flush()

        categories: dict[ProductCategoryKind, uuid.UUID] = {}
        inventory = InventoryService(session)
        for name, sku, kind, retail, wholesale, mrp, gst, stock, batches in DEMO_PRODUCTS:
            if kind not in categories:
                cat = Category(
                    organization_id=org_id,
                    name=kind.value.title(),
                    code=kind.value.upper()[:8],
                    kind=kind,
                )
                session.add(cat)
                await session.flush()
                categories[kind] = cat.id
            product = Product(
                organization_id=org_id,
                category_id=categories[kind],
                base_unit_id=unit.id,
                name=name,
                sku=sku,
                retail_price=Decimal(retail),
                wholesale_price=Decimal(wholesale),
                mrp=Decimal(mrp),
                gst_rate=Decimal(gst),
                tracks_batches=batches,
                min_stock=Decimal("20"),
            )
            session.add(product)
            await session.flush()
            await inventory.receive(
                organization_id=org_id,
                warehouse_id=shop.id,
                product_id=product.id,
                base_quantity=Decimal(stock),
            )

        for code, name, ctype, limit in DEMO_CUSTOMERS:
            session.add(
                Customer(
                    organization_id=org_id,
                    code=code,
                    name=name,
                    customer_type=ctype,
                    credit_limit=Decimal(limit),
                )
            )
        for code, name in DEMO_SUPPLIERS:
            session.add(Supplier(organization_id=org_id, code=code, name=name))

        await session.commit()
        print(
            f"Seeded org {org_id}: {len(DEMO_USERS) + 1} users, "
            f"{len(DEMO_PRODUCTS)} products, {len(DEMO_CUSTOMERS)} customers, "
            f"{len(DEMO_SUPPLIERS)} suppliers."
        )

    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(seed())
