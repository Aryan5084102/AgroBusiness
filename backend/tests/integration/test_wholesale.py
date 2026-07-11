"""Phase 5 wholesale integration tests against real Postgres.

Covers: order confirmation reserves stock (available drops, on-hand unchanged),
credit-limit block, dispatch releases the reservation + deducts stock + creates a
wholesale invoice on credit, and quotations reserve nothing.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from app.core.database import get_sessionmaker
from app.core.exceptions import BusinessRuleError
from app.modules.catalogue.models import Category, Product, ProductCategoryKind, Unit
from app.modules.customers.models import Customer, CustomerType
from app.modules.inventory.models import StockBalance, StockMovement
from app.modules.inventory.service import InventoryService
from app.modules.organizations.models import Warehouse
from app.modules.organizations.service import OrganizationProvisioningService
from app.modules.sales.models import PaymentStatus, SaleChannel, SalesInvoice
from app.modules.sales.order_models import SalesOrderStatus
from app.modules.sales.wholesale_service import OrderLineInput, WholesaleService
from sqlalchemy import func, select

pytestmark = pytest.mark.usefixtures("db_ready")

TODAY = date(2026, 7, 11)


async def _setup(
    *, stock: Decimal = Decimal("100"), credit_limit: Decimal = Decimal("1000000")
) -> dict[str, uuid.UUID]:
    factory = get_sessionmaker()
    async with factory() as session:
        prov = await OrganizationProvisioningService(session).provision(
            org_name="WS Co",
            owner_email="owner@ws.local",
            owner_password="OwnerPass123",
            owner_name="Owner",
        )
        org_id = prov.organization.id
        unit = Unit(organization_id=org_id, code="pcs", name="Pieces")
        cat = Category(
            organization_id=org_id,
            name="Fertilizers",
            code="FERT",
            kind=ProductCategoryKind.FERTILIZER,
        )
        session.add_all([unit, cat])
        await session.flush()
        product = Product(
            organization_id=org_id,
            category_id=cat.id,
            base_unit_id=unit.id,
            name="Urea 50kg",
            sku="FERT-UREA-50",
            retail_price=Decimal("300.00"),
            wholesale_price=Decimal("270.00"),
            mrp=Decimal("300.00"),
            gst_rate=Decimal("5"),
        )
        dealer = Customer(
            organization_id=org_id,
            code="D1",
            name="Green Dealer",
            customer_type=CustomerType.DEALER,
            credit_limit=credit_limit,
        )
        wh = Warehouse(organization_id=org_id, branch_id=prov.branch.id, name="Godown", code="GD1")
        session.add_all([product, dealer, wh])
        await session.flush()
        ids = {
            "org": org_id,
            "branch": prov.branch.id,
            "product": product.id,
            "dealer": dealer.id,
            "warehouse": wh.id,
        }
        await InventoryService(session).receive(
            organization_id=org_id,
            warehouse_id=wh.id,
            product_id=product.id,
            base_quantity=stock,
        )
        await session.commit()
        return ids


async def _available(product_id: uuid.UUID) -> tuple[Decimal, Decimal]:
    factory = get_sessionmaker()
    async with factory() as session:
        row = await session.execute(
            select(
                func.coalesce(func.sum(StockBalance.on_hand), 0),
                func.coalesce(func.sum(StockBalance.reserved), 0),
            ).where(StockBalance.product_id == product_id)
        )
        on_hand, reserved = row.one()
        return Decimal(str(on_hand)), Decimal(str(reserved))


async def test_confirmed_order_reserves_stock_using_wholesale_price() -> None:
    ids = await _setup()
    factory = get_sessionmaker()
    async with factory() as session:
        result = await WholesaleService(session).create_order(
            organization_id=ids["org"],
            warehouse_id=ids["warehouse"],
            customer_id=ids["dealer"],
            order_date=TODAY,
            as_of=TODAY,
            lines=[OrderLineInput(product_id=ids["product"], base_quantity=Decimal("10"))],
        )
        await session.commit()
        # 10 * 270 wholesale = 2700 net; 5% GST = 135; total 2835.
        assert result.status == SalesOrderStatus.CONFIRMED
        assert result.grand_total == Decimal("2835.00")

    on_hand, reserved = await _available(ids["product"])
    # On-hand unchanged; 10 reserved (available = 90).
    assert on_hand == Decimal("100.000")
    assert reserved == Decimal("10.000")


async def test_credit_limit_blocks_order() -> None:
    ids = await _setup(credit_limit=Decimal("1000"))
    factory = get_sessionmaker()
    async with factory() as session:
        with pytest.raises(BusinessRuleError) as exc:
            await WholesaleService(session).create_order(
                organization_id=ids["org"],
                warehouse_id=ids["warehouse"],
                customer_id=ids["dealer"],
                order_date=TODAY,
                as_of=TODAY,
                lines=[OrderLineInput(product_id=ids["product"], base_quantity=Decimal("10"))],
            )
        assert exc.value.code == "credit_limit_exceeded"
        await session.rollback()

    # Nothing reserved after a blocked order.
    _, reserved = await _available(ids["product"])
    assert reserved == Decimal("0.000")


async def test_credit_override_allows_order() -> None:
    ids = await _setup(credit_limit=Decimal("1000"))
    factory = get_sessionmaker()
    async with factory() as session:
        result = await WholesaleService(session).create_order(
            organization_id=ids["org"],
            warehouse_id=ids["warehouse"],
            customer_id=ids["dealer"],
            order_date=TODAY,
            as_of=TODAY,
            credit_override_approved=True,
            lines=[OrderLineInput(product_id=ids["product"], base_quantity=Decimal("10"))],
        )
        await session.commit()
        assert result.status == SalesOrderStatus.CONFIRMED


async def test_dispatch_releases_reservation_and_deducts_stock() -> None:
    ids = await _setup()
    factory = get_sessionmaker()
    async with factory() as session:
        order = await WholesaleService(session).create_order(
            organization_id=ids["org"],
            warehouse_id=ids["warehouse"],
            customer_id=ids["dealer"],
            order_date=TODAY,
            as_of=TODAY,
            lines=[OrderLineInput(product_id=ids["product"], base_quantity=Decimal("10"))],
        )
        await session.commit()
        order_id = order.sales_order_id

    async with factory() as session:
        dispatch = await WholesaleService(session).dispatch_and_invoice(
            organization_id=ids["org"],
            sales_order_id=order_id,
            invoice_date=TODAY,
            as_of=TODAY,
        )
        await session.commit()
        assert dispatch.invoice_number.startswith("INV-")

    on_hand, reserved = await _available(ids["product"])
    # Reservation released and stock deducted: 100 -> 90 on-hand, 0 reserved.
    assert on_hand == Decimal("90.000")
    assert reserved == Decimal("0.000")

    async with factory() as session:
        # A WHOLESALE credit invoice exists; ledger shows a wholesale-sale movement.
        inv = (
            (
                await session.execute(
                    select(SalesInvoice).where(SalesInvoice.customer_id == ids["dealer"])
                )
            )
            .scalars()
            .first()
        )
        assert inv is not None
        assert inv.channel == SaleChannel.WHOLESALE
        assert inv.payment_status == PaymentStatus.CREDIT
        moves = await session.execute(
            select(func.count())
            .select_from(StockMovement)
            .where(
                StockMovement.product_id == ids["product"],
                StockMovement.base_quantity < 0,
            )
        )
        assert moves.scalar() == 1


async def test_quotation_reserves_nothing() -> None:
    ids = await _setup()
    factory = get_sessionmaker()
    async with factory() as session:
        result = await WholesaleService(session).create_order(
            organization_id=ids["org"],
            warehouse_id=ids["warehouse"],
            customer_id=ids["dealer"],
            order_date=TODAY,
            as_of=TODAY,
            is_quotation=True,
            lines=[OrderLineInput(product_id=ids["product"], base_quantity=Decimal("10"))],
        )
        await session.commit()
        assert result.status == SalesOrderStatus.QUOTATION

    _, reserved = await _available(ids["product"])
    assert reserved == Decimal("0.000")
