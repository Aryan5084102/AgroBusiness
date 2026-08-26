"""Phase 4 retail POS integration tests against real Postgres.

Covers: receive stock, finalize a retail invoice (pricing engine totals + FEFO
stock deduction), idempotent replay (no duplicate), insufficient-stock block,
and the walk-in-must-pay-in-full rule.
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
from app.modules.payments.models import PaymentMethod
from app.modules.sales.models import PaymentStatus, SalesInvoice
from app.modules.sales.service import PaymentInput, SaleLineInput, SalesService
from sqlalchemy import func, select

pytestmark = pytest.mark.usefixtures("db_ready")

TODAY = date(2026, 7, 11)


async def _setup(*, stock: Decimal = Decimal("100")) -> dict[str, uuid.UUID]:
    factory = get_sessionmaker()
    async with factory() as session:
        prov = await OrganizationProvisioningService(session).provision(
            org_name="Sales Co",
            owner_email="owner@sales.local",
            owner_password="OwnerPass123",
            owner_name="Owner",
        )
        org_id = prov.organization.id
        unit = Unit(organization_id=org_id, code="pcs", name="Pieces")
        cat = Category(
            organization_id=org_id,
            name="Pesticides",
            code="PEST",
            kind=ProductCategoryKind.PESTICIDE,
        )
        session.add_all([unit, cat])
        await session.flush()
        product = Product(
            organization_id=org_id,
            category_id=cat.id,
            base_unit_id=unit.id,
            name="Neem Oil 500ml",
            sku="PEST-NEEM-500",
            retail_price=Decimal("200.00"),
            mrp=Decimal("250.00"),
            gst_rate=Decimal("18"),
        )
        customer = Customer(
            organization_id=org_id,
            code="C1",
            name="Ravi Farmer",
            customer_type=CustomerType.FARMER,
            credit_limit=Decimal("100000"),
        )
        wh = Warehouse(organization_id=org_id, branch_id=prov.branch.id, name="Shop", code="SHOP")
        session.add_all([product, customer, wh])
        await session.flush()
        ids = {
            "org": org_id,
            "branch": prov.branch.id,
            "product": product.id,
            "customer": customer.id,
            "warehouse": wh.id,
        }
        # Seed stock via inventory service (no batch tracking on this product).
        inv = InventoryService(session)
        await inv.receive(
            organization_id=org_id,
            warehouse_id=wh.id,
            product_id=product.id,
            base_quantity=stock,
        )
        await session.commit()
        return ids


async def test_retail_sale_prices_and_deducts_stock() -> None:
    ids = await _setup()
    factory = get_sessionmaker()
    async with factory() as session:
        service = SalesService(session)
        result = await service.create_retail_invoice(
            organization_id=ids["org"],
            warehouse_id=ids["warehouse"],
            customer_id=ids["customer"],
            invoice_date=TODAY,
            as_of=TODAY,
            lines=[SaleLineInput(product_id=ids["product"], base_quantity=Decimal("2"))],
            payments=[PaymentInput(method=PaymentMethod.CASH, amount=Decimal("472.00"))],
        )
        await session.commit()
        # 2 * 200 = 400 net; 18% GST = 72; total 472.
        assert result.grand_total == Decimal("472.00")
        assert result.payment_status == PaymentStatus.PAID
        assert result.invoice_number.startswith("INV-")

    async with factory() as session:
        # Stock fell from 100 to 98 in both ledger and balance.
        ledger = await session.execute(
            select(func.coalesce(func.sum(StockMovement.base_quantity), 0)).where(
                StockMovement.product_id == ids["product"]
            )
        )
        assert Decimal(str(ledger.scalar())) == Decimal("98.000")
        bal = await session.execute(
            select(func.coalesce(func.sum(StockBalance.on_hand), 0)).where(
                StockBalance.product_id == ids["product"]
            )
        )
        assert Decimal(str(bal.scalar())) == Decimal("98.000")


async def test_idempotent_replay_returns_same_invoice() -> None:
    ids = await _setup()
    factory = get_sessionmaker()
    key = "pos-terminal-1-txn-abc"

    async with factory() as session:
        service = SalesService(session)
        first = await service.create_retail_invoice(
            organization_id=ids["org"],
            warehouse_id=ids["warehouse"],
            customer_id=ids["customer"],
            invoice_date=TODAY,
            as_of=TODAY,
            lines=[SaleLineInput(product_id=ids["product"], base_quantity=Decimal("1"))],
            payments=[PaymentInput(method=PaymentMethod.UPI, amount=Decimal("236.00"))],
            idempotency_key=key,
        )
        await session.commit()

    async with factory() as session:
        service = SalesService(session)
        replay = await service.create_retail_invoice(
            organization_id=ids["org"],
            warehouse_id=ids["warehouse"],
            customer_id=ids["customer"],
            invoice_date=TODAY,
            as_of=TODAY,
            lines=[SaleLineInput(product_id=ids["product"], base_quantity=Decimal("1"))],
            payments=[PaymentInput(method=PaymentMethod.UPI, amount=Decimal("236.00"))],
            idempotency_key=key,
        )
        await session.commit()
        assert replay.replayed is True
        assert replay.invoice_id == first.invoice_id

    async with factory() as session:
        # Only ONE sale movement exists (replay did not deduct stock twice).
        count = await session.execute(
            select(func.count())
            .select_from(StockMovement)
            .where(
                StockMovement.product_id == ids["product"],
                StockMovement.base_quantity < 0,
            )
        )
        assert count.scalar() == 1


async def test_insufficient_stock_blocks_and_rolls_back() -> None:
    ids = await _setup(stock=Decimal("1"))
    factory = get_sessionmaker()
    async with factory() as session:
        service = SalesService(session)
        with pytest.raises(BusinessRuleError) as exc:
            await service.create_retail_invoice(
                organization_id=ids["org"],
                warehouse_id=ids["warehouse"],
                customer_id=ids["customer"],
                invoice_date=TODAY,
                as_of=TODAY,
                lines=[SaleLineInput(product_id=ids["product"], base_quantity=Decimal("5"))],
                payments=[PaymentInput(method=PaymentMethod.CASH, amount=Decimal("1180"))],
            )
        assert exc.value.code == "insufficient_stock"
        await session.rollback()

    async with factory() as session:
        # No invoice was created; stock untouched at 1.
        inv_count = await session.execute(select(func.count()).select_from(SalesInvoice))
        assert inv_count.scalar() == 0


async def test_walk_in_must_pay_in_full() -> None:
    ids = await _setup()
    factory = get_sessionmaker()
    async with factory() as session:
        service = SalesService(session)
        with pytest.raises(BusinessRuleError) as exc:
            await service.create_retail_invoice(
                organization_id=ids["org"],
                warehouse_id=ids["warehouse"],
                customer_id=None,  # walk-in
                invoice_date=TODAY,
                as_of=TODAY,
                lines=[SaleLineInput(product_id=ids["product"], base_quantity=Decimal("1"))],
                payments=[PaymentInput(method=PaymentMethod.CASH, amount=Decimal("100"))],
            )
        assert exc.value.code == "walk_in_credit_not_allowed"


async def test_counter_khata_sale_lands_as_credit() -> None:
    """A named customer may take goods with nothing paid — it becomes a receivable."""
    ids = await _setup()
    factory = get_sessionmaker()
    async with factory() as session:
        service = SalesService(session)
        result = await service.create_retail_invoice(
            organization_id=ids["org"],
            warehouse_id=ids["warehouse"],
            customer_id=ids["customer"],
            invoice_date=TODAY,
            as_of=TODAY,
            lines=[SaleLineInput(product_id=ids["product"], base_quantity=Decimal("2"))],
            payments=[],  # the whole bill goes on khata
        )
        await session.commit()

    assert result.payment_status is PaymentStatus.CREDIT
    assert result.paid_amount == Decimal("0.00")
    assert result.grand_total > 0


async def test_counter_khata_respects_the_credit_limit() -> None:
    """The limit that governs dealer orders governs the counter too.

    Without this the limit would be enforceable on the wholesale screen and
    silently skipped for the same customer at the retail counter.
    """
    ids = await _setup()
    factory = get_sessionmaker()
    async with factory() as session:
        customer = await session.get(Customer, ids["customer"])
        assert customer is not None
        customer.credit_limit = Decimal("300")
        await session.commit()

    async with factory() as session:
        service = SalesService(session)
        with pytest.raises(BusinessRuleError) as exc:
            await service.create_retail_invoice(
                organization_id=ids["org"],
                warehouse_id=ids["warehouse"],
                customer_id=ids["customer"],
                invoice_date=TODAY,
                as_of=TODAY,
                # 3 x 200 + GST is well past a 300 limit.
                lines=[SaleLineInput(product_id=ids["product"], base_quantity=Decimal("3"))],
                payments=[],
            )
        assert exc.value.code == "credit_limit_exceeded"

    # A part payment that brings the unpaid balance under the limit is fine.
    async with factory() as session:
        service = SalesService(session)
        result = await service.create_retail_invoice(
            organization_id=ids["org"],
            warehouse_id=ids["warehouse"],
            customer_id=ids["customer"],
            invoice_date=TODAY,
            as_of=TODAY,
            lines=[SaleLineInput(product_id=ids["product"], base_quantity=Decimal("3"))],
            payments=[PaymentInput(method=PaymentMethod.CASH, amount=Decimal("500"))],
        )
        await session.commit()
        assert result.payment_status is PaymentStatus.PARTIAL


async def test_customer_without_a_limit_is_unlimited_at_the_counter() -> None:
    """credit_limit = 0 means "no limit set", matching the wholesale rule."""
    ids = await _setup()
    factory = get_sessionmaker()
    async with factory() as session:
        customer = await session.get(Customer, ids["customer"])
        assert customer is not None
        customer.credit_limit = Decimal("0")
        await session.commit()

    async with factory() as session:
        service = SalesService(session)
        result = await service.create_retail_invoice(
            organization_id=ids["org"],
            warehouse_id=ids["warehouse"],
            customer_id=ids["customer"],
            invoice_date=TODAY,
            as_of=TODAY,
            lines=[SaleLineInput(product_id=ids["product"], base_quantity=Decimal("5"))],
            payments=[],
        )
        await session.commit()
        assert result.payment_status is PaymentStatus.CREDIT
