"""Development seed data. NEVER run automatically in production.

Creates one organization with its default roles/permissions, an owner, the
standard demo users, and a full slice of realistic business history — stock with
batches and expiry, retail invoices across the last two weeks, wholesale orders
(confirmed and dispatched), collections, and repair jobs — so **every role** has
populated screens the moment they sign in.

    python -m app.seed            # seed a fresh database
    python -m app.seed --reset    # wipe existing demo data first, then seed
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import Base, get_engine, get_sessionmaker
from app.modules.audit.service import AuditService
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductCategoryKind,
    Unit,
)
from app.modules.collections.service import CollectionsService
from app.modules.customers.models import Customer, CustomerType
from app.modules.inventory.models import Batch, MovementType
from app.modules.inventory.service import InventoryService
from app.modules.notifications.service import NotificationService
from app.modules.organizations.models import Organization, Warehouse, WarehouseType
from app.modules.organizations.service import OrganizationProvisioningService
from app.modules.payments.models import PaymentMethod
from app.modules.purchases.service import PurchaseService, ReceiptCharges, ReceiptLineInput
from app.modules.sales.service import PaymentInput, SaleLineInput, SalesService
from app.modules.sales.wholesale_service import OrderLineInput, WholesaleService
from app.modules.service_jobs.models import RepairStatus
from app.modules.service_jobs.service import ServiceJobService
from app.modules.suppliers.models import Supplier
from app.modules.users.models import User

DEMO_PASSWORD = "AgriFlow@123"  # documented development-only password
ORG_NAME = "AgriFlow Demo Traders"
OWNER_EMAIL = "owner@agriflow.local"

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
    ("CUST-WALK", "Walk-in Customer", CustomerType.WALK_IN, "0", None),
    ("CUST-RAVI", "Ravi Kumar (Farmer)", CustomerType.FARMER, "20000", "9876500011"),
    ("CUST-SITA", "Sita Devi (Farmer)", CustomerType.FARMER, "15000", "9876500022"),
    ("DLR-GREEN", "Green Agro Dealers", CustomerType.DEALER, "100000", "9876500033"),
    ("DLR-KISAN", "Kisan Traders", CustomerType.DEALER, "50000", "9876500044"),
    ("RTL-BHARAT", "Bharat Krishi Kendra", CustomerType.RETAILER, "35000", "9876500055"),
]

DEMO_SUPPLIERS = [
    ("SUP-AGRI", "AgriSeeds Pvt Ltd"),
    ("SUP-IFFCO", "IFFCO Distributors"),
    ("SUP-BAYER", "Bayer CropScience"),
]


def _today() -> date:
    return datetime.now(tz=timezone.utc).date()


async def _wipe(session: AsyncSession) -> None:
    """Truncate every application table so a reseed starts from a clean slate."""
    tables = [t.name for t in reversed(Base.metadata.sorted_tables)]
    await session.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    await session.commit()
    print(f"Wiped {len(tables)} tables.")


async def _seed_catalogue(
    session: AsyncSession, org_id: uuid.UUID, shop_id: uuid.UUID
) -> dict[str, Product]:
    """Products with opening stock; batch-tracked lines get a dated batch."""
    unit = Unit(organization_id=org_id, code="pcs", name="Pieces")
    session.add(unit)
    await session.flush()

    inventory = InventoryService(session)
    categories: dict[ProductCategoryKind, uuid.UUID] = {}
    products: dict[str, Product] = {}
    today = _today()

    for index, (
        name,
        sku,
        kind,
        retail,
        wholesale,
        mrp,
        gst,
        stock,
        batches,
    ) in enumerate(DEMO_PRODUCTS):
        if kind not in categories:
            category = Category(
                organization_id=org_id,
                name=kind.value.replace("_", " ").title(),
                code=kind.value.upper()[:8],
                kind=kind,
            )
            session.add(category)
            await session.flush()
            categories[kind] = category.id

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
            tracks_expiry=batches,
            min_stock=Decimal("20"),
        )
        session.add(product)
        await session.flush()
        products[sku] = product

        batch_id: uuid.UUID | None = None
        if batches:
            # Main batch: comfortably in date, so day-to-day selling always works.
            months_out = [18, 12, 14, 20, 24, 15, 22, 30, 16, 19][index % 10]
            batch = Batch(
                organization_id=org_id,
                product_id=product.id,
                batch_number=f"B{today.year}{index + 1:03d}",
                manufacture_date=today - timedelta(days=120),
                expiry_date=today + timedelta(days=30 * months_out),
                mrp=Decimal(mrp),
            )
            session.add(batch)
            await session.flush()
            batch_id = batch.id

        await inventory.receive(
            organization_id=org_id,
            warehouse_id=shop_id,
            product_id=product.id,
            base_quantity=Decimal(stock),
            batch_id=batch_id,
            movement_type=MovementType.OPENING,
        )

    # Two extra batches so the batch screen shows every state the FEFO engine
    # reasons about. The near-expiry lot is deliberately large enough that the
    # seeded sales cannot exhaust it; the expired lot is never allocatable.
    for sku, batch_number, days, quantity in [
        ("FUNG-CU-1", "NEAR-EXPIRY", 22, "25"),
        ("PEST-NEEM-500", "EXPIRED", -12, "10"),
    ]:
        product = products[sku]
        batch = Batch(
            organization_id=org_id,
            product_id=product.id,
            batch_number=f"B{today.year}-{batch_number}",
            manufacture_date=today - timedelta(days=540),
            expiry_date=today + timedelta(days=days),
            mrp=product.mrp,
        )
        session.add(batch)
        await session.flush()
        await inventory.receive(
            organization_id=org_id,
            warehouse_id=shop_id,
            product_id=product.id,
            base_quantity=Decimal(quantity),
            batch_id=batch.id,
            movement_type=MovementType.OPENING,
        )
    return products


async def _seed_retail_history(
    session: AsyncSession,
    org_id: uuid.UUID,
    shop_id: uuid.UUID,
    branch_id: uuid.UUID,
    products: dict[str, Product],
    customers: dict[str, Customer],
    cashier_id: uuid.UUID,
) -> None:
    """A fortnight of counter sales so the trend chart and registers have shape."""
    sales = SalesService(session)
    today = _today()
    # (days ago, sku, qty, customer code, method)
    script = [
        (13, "FERT-UREA-50", "4", "CUST-WALK", PaymentMethod.CASH),
        (12, "SEED-MZ-1", "2", "CUST-RAVI", PaymentMethod.UPI),
        (11, "PEST-NEEM-500", "3", "CUST-WALK", PaymentMethod.CASH),
        (9, "FERT-DAP-50", "2", "CUST-SITA", PaymentMethod.CARD),
        (8, "TOOL-TRWL", "5", "CUST-WALK", PaymentMethod.CASH),
        (7, "HERB-GLY-1", "2", "CUST-RAVI", PaymentMethod.UPI),
        (5, "SEED-PD-5", "3", "CUST-WALK", PaymentMethod.CASH),
        (4, "SPARE-NOZ", "6", "CUST-SITA", PaymentMethod.CASH),
        (3, "FERT-UREA-50", "6", "CUST-WALK", PaymentMethod.UPI),
        (2, "FUNG-CU-1", "2", "CUST-RAVI", PaymentMethod.CASH),
        (1, "MACH-SPR-16", "1", "CUST-SITA", PaymentMethod.CARD),
        (0, "FERT-DAP-50", "3", "CUST-WALK", PaymentMethod.CASH),
        (0, "SEED-MZ-1", "4", "CUST-RAVI", PaymentMethod.UPI),
    ]
    for days_ago, sku, qty, customer_code, method in script:
        invoice_date = today - timedelta(days=days_ago)
        product = products[sku]
        quantity = Decimal(qty)
        # Quote first so the payment matches the authoritative total exactly.
        quote = await sales.quote(
            organization_id=org_id,
            warehouse_id=shop_id,
            lines=[SaleLineInput(product_id=product.id, base_quantity=quantity)],
            as_of=invoice_date,
        )
        await sales.create_retail_invoice(
            organization_id=org_id,
            warehouse_id=shop_id,
            invoice_date=invoice_date,
            lines=[SaleLineInput(product_id=product.id, base_quantity=quantity)],
            payments=[PaymentInput(method=method, amount=quote.grand_total)],
            customer_id=customers[customer_code].id,
            branch_id=branch_id,
            created_by=cashier_id,
            as_of=invoice_date,
        )
    await session.commit()


async def _seed_wholesale(
    session: AsyncSession,
    org_id: uuid.UUID,
    shop_id: uuid.UUID,
    branch_id: uuid.UUID,
    products: dict[str, Product],
    customers: dict[str, Customer],
    salesperson_id: uuid.UUID,
) -> None:
    """Two dispatched dealer orders (credit invoices), one still open, one quote."""
    wholesale = WholesaleService(session)
    today = _today()

    dispatched = [
        ("DLR-GREEN", [("FERT-UREA-50", "40"), ("FERT-DAP-50", "20")], 6),
        ("DLR-KISAN", [("SEED-MZ-1", "25"), ("PEST-NEEM-500", "15")], 3),
    ]
    for customer_code, lines, days_ago in dispatched:
        order_date = today - timedelta(days=days_ago)
        result = await wholesale.create_order(
            organization_id=org_id,
            warehouse_id=shop_id,
            customer_id=customers[customer_code].id,
            order_date=order_date,
            lines=[
                OrderLineInput(product_id=products[sku].id, base_quantity=Decimal(qty))
                for sku, qty in lines
            ],
            branch_id=branch_id,
            salesperson_id=salesperson_id,
            credit_override_approved=True,
            as_of=order_date,
        )
        await wholesale.dispatch_and_invoice(
            organization_id=org_id,
            sales_order_id=result.sales_order_id,
            invoice_date=order_date,
            created_by=salesperson_id,
            as_of=order_date,
        )

    # Confirmed but not yet dispatched — the salesperson's open pipeline.
    await wholesale.create_order(
        organization_id=org_id,
        warehouse_id=shop_id,
        customer_id=customers["RTL-BHARAT"].id,
        order_date=today,
        lines=[
            OrderLineInput(product_id=products["HERB-GLY-1"].id, base_quantity=Decimal("10")),
            OrderLineInput(product_id=products["FUNG-CU-1"].id, base_quantity=Decimal("8")),
        ],
        branch_id=branch_id,
        salesperson_id=salesperson_id,
        credit_override_approved=True,
        as_of=today,
    )
    # A quotation: no stock reservation, no credit check.
    await wholesale.create_order(
        organization_id=org_id,
        warehouse_id=shop_id,
        customer_id=customers["DLR-KISAN"].id,
        order_date=today,
        lines=[OrderLineInput(product_id=products["SEED-PD-5"].id, base_quantity=Decimal("12"))],
        branch_id=branch_id,
        salesperson_id=salesperson_id,
        is_quotation=True,
        as_of=today,
    )
    await session.commit()


async def _seed_purchases(
    session: AsyncSession,
    org_id: uuid.UUID,
    godown_id: uuid.UUID,
    branch_id: uuid.UUID,
    products: dict[str, Product],
    suppliers: dict[str, Supplier],
    buyer_id: uuid.UUID,
) -> None:
    """Two goods receipts into the godown, with freight spread as landed cost."""
    service = PurchaseService(session)
    today = _today()
    receipts = [
        (
            "SUP-IFFCO",
            [("FERT-UREA-50", "100", "252"), ("FERT-DAP-50", "60", "1150")],
            "2400",
            5,
        ),
        (
            "SUP-AGRI",
            [("SEED-MZ-1", "60", "395"), ("SEED-PD-5", "40", "880")],
            "1200",
            2,
        ),
    ]
    for supplier_code, lines, freight, days_ago in receipts:
        receipt_date = today - timedelta(days=days_ago)
        await service.receive_goods(
            organization_id=org_id,
            warehouse_id=godown_id,
            supplier_id=suppliers[supplier_code].id,
            receipt_date=receipt_date,
            charges=ReceiptCharges(freight=Decimal(freight)),
            created_by=buyer_id,
            branch_id=branch_id,
            lines=[
                ReceiptLineInput(
                    purchase_order_item_id=None,
                    product_id=products[sku].id,
                    received_base_quantity=Decimal(qty),
                    unit_rate=Decimal(rate),
                    batch_number=f"SUP-{receipt_date:%y%m%d}-{sku[-3:]}",
                    expiry_date=receipt_date + timedelta(days=540),
                )
                for sku, qty, rate in lines
            ],
        )
    await session.commit()


async def _seed_collections(
    session: AsyncSession,
    org_id: uuid.UUID,
    customers: dict[str, Customer],
    collector_id: uuid.UUID,
) -> None:
    """Part-settle one dealer so receivables, ageing and the ledger all have data."""
    service = CollectionsService(session)
    await service.receive_payment(
        organization_id=org_id,
        customer_id=customers["DLR-GREEN"].id,
        amount=Decimal("15000.00"),
        method=PaymentMethod.BANK_TRANSFER,
        payment_date=_today(),
        reference="NEFT/DEMO/0001",
        created_by=collector_id,
    )
    await session.commit()


async def _seed_service_jobs(
    session: AsyncSession,
    org_id: uuid.UUID,
    shop_id: uuid.UUID,
    branch_id: uuid.UUID,
    products: dict[str, Product],
    customers: dict[str, Customer],
    technician_id: uuid.UUID,
) -> None:
    """Repair jobs in several states, one with a spare part already consumed."""
    service = ServiceJobService(session)
    today = _today()

    in_progress = await service.create_job(
        organization_id=org_id,
        warehouse_id=shop_id,
        received_date=today - timedelta(days=3),
        customer_id=customers["CUST-RAVI"].id,
        product_id=products["MACH-SPR-16"].id,
        complaint="Sprayer not building pressure; leaking at the nozzle.",
        branch_id=branch_id,
        technician_id=technician_id,
    )
    in_progress.status = RepairStatus.IN_PROGRESS
    await service.consume_part(
        organization_id=org_id,
        repair_job_id=in_progress.id,
        product_id=products["SPARE-NOZ"].id,
        base_quantity=Decimal("1"),
        created_by=technician_id,
        as_of=today,
    )

    ready = await service.create_job(
        organization_id=org_id,
        warehouse_id=shop_id,
        received_date=today - timedelta(days=6),
        customer_id=customers["CUST-SITA"].id,
        product_id=products["MACH-SPR-16"].id,
        complaint="Annual service and seal replacement.",
        branch_id=branch_id,
        technician_id=technician_id,
    )
    await service.set_labour_and_complete(
        organization_id=org_id,
        repair_job_id=ready.id,
        labour_charges=Decimal("350.00"),
        completed_date=today - timedelta(days=1),
    )

    await service.create_job(
        organization_id=org_id,
        warehouse_id=shop_id,
        received_date=today,
        customer_id=customers["RTL-BHARAT"].id,
        product_id=products["MACH-SPR-16"].id,
        complaint="Handle cracked during transport; awaiting inspection.",
        branch_id=branch_id,
        technician_id=technician_id,
    )
    await session.commit()


async def _seed_notifications_and_audit(
    session: AsyncSession, org_id: uuid.UUID, users: dict[str, User]
) -> None:
    notifications = NotificationService(session)
    await notifications.create(
        organization_id=org_id,
        user_id=users["inventory@agriflow.local"].id,
        type="low_stock",
        title="Stock below minimum",
        body="Knapsack Sprayer 16L has fallen below its reorder level.",
    )
    await notifications.create(
        organization_id=org_id,
        user_id=users["accountant@agriflow.local"].id,
        type="receivable",
        title="Dealer balance outstanding",
        body="Green Agro Dealers still owes money on a dispatched order.",
    )

    audit = AuditService(session)
    for action, entity, reason in [
        ("organization.provisioned", "organization", "Demo tenant created"),
        ("user.created", "user", "Demo staff accounts created"),
        ("product.created", "product", "Catalogue seeded"),
        ("stock.opening_balance", "stock_movement", "Opening stock posted"),
    ]:
        await audit.record(
            action=action,
            organization_id=org_id,
            actor_user_id=users[OWNER_EMAIL].id,
            entity_type=entity,
            reason=reason,
        )
    await session.commit()


async def seed(reset: bool = False) -> None:
    settings = get_settings()
    if settings.is_production:
        raise RuntimeError("Refusing to seed demo data in production.")

    factory = get_sessionmaker()
    async with factory() as session:
        if reset:
            await _wipe(session)
        existing = await session.scalar(select(Organization.id).limit(1))
        if existing is not None:
            print(
                "This database already contains an organization. "
                "Re-run with --reset to wipe it and reseed."
            )
            await get_engine().dispose()
            return

        provisioning = OrganizationProvisioningService(session)
        result = await provisioning.provision(
            org_name=ORG_NAME,
            owner_email=OWNER_EMAIL,
            owner_password=DEMO_PASSWORD,
            owner_name="Business Owner",
        )
        org_id = result.organization.id
        branch_id = result.branch.id
        result.organization.legal_name = "AgriFlow Demo Traders Pvt Ltd"
        result.organization.gstin = "27AAAAA0000A1Z5"
        result.organization.address = "Market Road, Nashik, Maharashtra 422001"

        users: dict[str, User] = {OWNER_EMAIL: result.owner}
        for email, name, role_code in DEMO_USERS:
            users[email] = await provisioning.create_user(
                organization_id=org_id,
                email=email,
                password=DEMO_PASSWORD,
                full_name=name,
                role_code=role_code,
                branch_id=branch_id,
            )

        shop = Warehouse(
            organization_id=org_id,
            branch_id=branch_id,
            name="Main Shop",
            code="SHOP",
            type=WarehouseType.SHOP,
        )
        godown = Warehouse(
            organization_id=org_id,
            branch_id=branch_id,
            name="Back Godown",
            code="GODOWN",
            type=WarehouseType.GODOWN,
        )
        session.add_all([shop, godown])
        await session.flush()

        products = await _seed_catalogue(session, org_id, shop.id)

        customers: dict[str, Customer] = {}
        for code, name, ctype, limit, phone in DEMO_CUSTOMERS:
            customer = Customer(
                organization_id=org_id,
                code=code,
                name=name,
                customer_type=ctype,
                credit_limit=Decimal(limit),
                credit_period_days=30 if Decimal(limit) > 0 else 0,
                phone=phone,
            )
            session.add(customer)
            customers[code] = customer

        suppliers: dict[str, Supplier] = {}
        for code, name in DEMO_SUPPLIERS:
            supplier = Supplier(organization_id=org_id, code=code, name=name)
            session.add(supplier)
            suppliers[code] = supplier
        await session.commit()

        await _seed_purchases(
            session,
            org_id,
            godown.id,
            branch_id,
            products,
            suppliers,
            users["inventory@agriflow.local"].id,
        )
        await _seed_retail_history(
            session,
            org_id,
            shop.id,
            branch_id,
            products,
            customers,
            users["billing@agriflow.local"].id,
        )
        await _seed_wholesale(
            session,
            org_id,
            shop.id,
            branch_id,
            products,
            customers,
            users["sales@agriflow.local"].id,
        )
        await _seed_collections(session, org_id, customers, users["accountant@agriflow.local"].id)
        await _seed_service_jobs(
            session,
            org_id,
            shop.id,
            branch_id,
            products,
            customers,
            users["technician@agriflow.local"].id,
        )
        await _seed_notifications_and_audit(session, org_id, users)

        print(
            f"Seeded org {org_id}\n"
            f"  users      : {len(users)} (password: {DEMO_PASSWORD})\n"
            f"  warehouses : 2 (Main Shop, Back Godown)\n"
            f"  products   : {len(DEMO_PRODUCTS)} with batches + opening stock\n"
            f"  customers  : {len(DEMO_CUSTOMERS)}   suppliers: {len(DEMO_SUPPLIERS)}\n"
            f"  history    : retail invoices, wholesale orders, goods receipts,\n"
            f"               a collection, repair jobs, notifications, audit trail"
        )

    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(seed(reset="--reset" in sys.argv))
