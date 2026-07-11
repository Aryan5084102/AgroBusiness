"""Phase 8 reports + notifications integration tests against real Postgres.

Builds real retail sales, then checks the dashboard aggregates (today's sales +
collections), the GST summary buckets, and in-app notification create/list/read.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from app.core.database import get_sessionmaker
from app.modules.catalogue.models import Category, Product, ProductCategoryKind, Unit
from app.modules.customers.models import Customer, CustomerType
from app.modules.inventory.service import InventoryService
from app.modules.notifications.service import NotificationService
from app.modules.organizations.models import Warehouse
from app.modules.organizations.service import OrganizationProvisioningService
from app.modules.payments.models import PaymentMethod
from app.modules.reports.service import ReportsService
from app.modules.sales.service import PaymentInput, SaleLineInput, SalesService

pytestmark = pytest.mark.usefixtures("db_ready")

TODAY = date(2026, 7, 11)


async def _setup_with_sale() -> dict[str, uuid.UUID]:
    factory = get_sessionmaker()
    async with factory() as session:
        prov = await OrganizationProvisioningService(session).provision(
            org_name="Rep Co",
            owner_email="owner@rep.local",
            owner_password="OwnerPass123",
            owner_name="Owner",
        )
        org_id = prov.organization.id
        unit = Unit(organization_id=org_id, code="pcs", name="Pieces")
        cat = Category(
            organization_id=org_id,
            name="Pest",
            code="PEST",
            kind=ProductCategoryKind.PESTICIDE,
        )
        session.add_all([unit, cat])
        await session.flush()
        product = Product(
            organization_id=org_id,
            category_id=cat.id,
            base_unit_id=unit.id,
            name="Spray",
            sku="PEST-SPR",
            retail_price=Decimal("100.00"),
            mrp=Decimal("100.00"),
            gst_rate=Decimal("18"),
            min_stock=Decimal("50"),
        )
        customer = Customer(
            organization_id=org_id,
            code="C1",
            name="Farmer",
            customer_type=CustomerType.FARMER,
        )
        wh = Warehouse(organization_id=org_id, branch_id=prov.branch.id, name="Shop", code="S1")
        session.add_all([product, customer, wh])
        await session.flush()
        ids = {
            "org": org_id,
            "branch": prov.branch.id,
            "product": product.id,
            "customer": customer.id,
            "warehouse": wh.id,
            "owner": prov.owner.id,
        }
        # Stock 10 (below min_stock 50 after none received? received 10 < 50 -> low).
        await InventoryService(session).receive(
            organization_id=org_id,
            warehouse_id=wh.id,
            product_id=product.id,
            base_quantity=Decimal("10"),
        )
        await session.commit()

    # One retail sale of 2 units, paid cash.
    async with factory() as session:
        await SalesService(session).create_retail_invoice(
            organization_id=ids["org"],
            warehouse_id=ids["warehouse"],
            customer_id=ids["customer"],
            invoice_date=TODAY,
            as_of=TODAY,
            lines=[SaleLineInput(product_id=ids["product"], base_quantity=Decimal("2"))],
            payments=[PaymentInput(method=PaymentMethod.CASH, amount=Decimal("236.00"))],
        )
        await session.commit()
    return ids


async def test_dashboard_aggregates_sales_and_low_stock() -> None:
    ids = await _setup_with_sale()
    factory = get_sessionmaker()
    async with factory() as session:
        summary = await ReportsService(session).dashboard(organization_id=ids["org"], as_of=TODAY)
        # 2 * 100 + 18% = 236 total sale today, all retail.
        assert summary.sales_today_total == Decimal("236.00")
        assert summary.retail_today_total == Decimal("236.00")
        assert summary.wholesale_today_total == Decimal("0.00")
        assert summary.collected_today_total == Decimal("236.00")
        # Paid in full -> no receivables.
        assert summary.receivables_outstanding == Decimal("0.00")
        # 8 on hand < min_stock 50 -> low stock.
        assert summary.low_stock_product_count == 1


async def test_gst_summary_buckets_by_rate() -> None:
    ids = await _setup_with_sale()
    factory = get_sessionmaker()
    async with factory() as session:
        summary = await ReportsService(session).gst_summary(
            organization_id=ids["org"], date_from=TODAY, date_to=TODAY
        )
        assert len(summary.buckets) == 1
        bucket = summary.buckets[0]
        assert bucket.gst_rate == Decimal("18.00")
        assert bucket.taxable_value == Decimal("200.00")
        assert bucket.tax_amount == Decimal("36.00")
        assert summary.total_tax == Decimal("36.00")


async def test_notifications_create_list_and_read() -> None:
    ids = await _setup_with_sale()
    factory = get_sessionmaker()
    async with factory() as session:
        svc = NotificationService(session)
        note = await svc.create(
            organization_id=ids["org"],
            user_id=ids["owner"],
            type="low_stock",
            title="Low stock: Spray",
            body="On-hand below minimum.",
        )
        await session.commit()
        note_id = note.id

    async with factory() as session:
        svc = NotificationService(session)
        unread = await svc.list_for_user(
            organization_id=ids["org"], user_id=ids["owner"], unread_only=True
        )
        assert len(unread) == 1
        await svc.mark_read(
            organization_id=ids["org"], user_id=ids["owner"], notification_id=note_id
        )
        await session.commit()

    async with factory() as session:
        svc = NotificationService(session)
        unread = await svc.list_for_user(
            organization_id=ids["org"], user_id=ids["owner"], unread_only=True
        )
        assert len(unread) == 0
