"""Phase 9 concurrency test: two simultaneous sales cannot oversell stock.

Two retail invoices each try to take the entire remaining stock at the same
time. Row-level locking on the stock balance must serialise them so exactly one
succeeds and the other is refused — no overselling, final stock is zero.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date
from decimal import Decimal

import pytest
from app.core.database import get_sessionmaker
from app.core.exceptions import BusinessRuleError
from app.modules.catalogue.models import Category, Product, ProductCategoryKind, Unit
from app.modules.customers.models import Customer, CustomerType
from app.modules.inventory.models import StockBalance
from app.modules.inventory.service import InventoryService
from app.modules.organizations.models import Warehouse
from app.modules.organizations.service import OrganizationProvisioningService
from app.modules.payments.models import PaymentMethod
from app.modules.sales.service import PaymentInput, SaleLineInput, SalesService
from sqlalchemy import func, select

pytestmark = pytest.mark.usefixtures("db_ready")

TODAY = date(2026, 7, 11)


async def _setup() -> dict[str, uuid.UUID]:
    factory = get_sessionmaker()
    async with factory() as session:
        prov = await OrganizationProvisioningService(session).provision(
            org_name="Race Co",
            owner_email="owner@race.local",
            owner_password="OwnerPass123",
            owner_name="Owner",
        )
        org_id = prov.organization.id
        unit = Unit(organization_id=org_id, code="pcs", name="Pieces")
        cat = Category(
            organization_id=org_id,
            name="Seed",
            code="SEED",
            kind=ProductCategoryKind.SEED,
        )
        session.add_all([unit, cat])
        await session.flush()
        product = Product(
            organization_id=org_id,
            category_id=cat.id,
            base_unit_id=unit.id,
            name="Rare Seed",
            sku="SEED-RARE",
            retail_price=Decimal("100.00"),
            mrp=Decimal("100.00"),
            gst_rate=Decimal("0"),
        )
        customer = Customer(
            organization_id=org_id,
            code="C1",
            name="Buyer",
            customer_type=CustomerType.FARMER,
        )
        wh = Warehouse(organization_id=org_id, branch_id=prov.branch.id, name="Shop", code="S1")
        session.add_all([product, customer, wh])
        await session.flush()
        ids = {
            "org": org_id,
            "product": product.id,
            "customer": customer.id,
            "warehouse": wh.id,
        }
        # Exactly 5 units in stock.
        await InventoryService(session).receive(
            organization_id=org_id,
            warehouse_id=wh.id,
            product_id=product.id,
            base_quantity=Decimal("5"),
        )
        await session.commit()
        return ids


async def test_two_concurrent_sales_do_not_oversell() -> None:
    ids = await _setup()
    factory = get_sessionmaker()

    async def sell_all() -> str:
        async with factory() as session:
            try:
                await SalesService(session).create_retail_invoice(
                    organization_id=ids["org"],
                    warehouse_id=ids["warehouse"],
                    customer_id=ids["customer"],
                    invoice_date=TODAY,
                    as_of=TODAY,
                    lines=[SaleLineInput(product_id=ids["product"], base_quantity=Decimal("5"))],
                    payments=[PaymentInput(method=PaymentMethod.CASH, amount=Decimal("500.00"))],
                )
                await session.commit()
                return "ok"
            except BusinessRuleError as exc:
                await session.rollback()
                return exc.code or "error"

    results = await asyncio.gather(sell_all(), sell_all())

    # Exactly one sale succeeds; the other is refused for insufficient stock.
    assert sorted(results) == ["insufficient_stock", "ok"]

    async with factory() as session:
        on_hand = await session.execute(
            select(func.coalesce(func.sum(StockBalance.on_hand), 0)).where(
                StockBalance.product_id == ids["product"]
            )
        )
        assert Decimal(str(on_hand.scalar())) == Decimal("0.000")
