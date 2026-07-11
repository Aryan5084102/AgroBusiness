"""Phase 6 collections + accounting integration tests against real Postgres.

Covers: two wholesale credit invoices, a partial collection allocated FIFO
(oldest fully paid, next partially), the customer ledger balance, and a balanced
double-entry journal (Dr Cash == Cr AR).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from app.core.database import get_sessionmaker
from app.modules.accounting.models import JournalEntry, JournalEntryLine
from app.modules.catalogue.models import Category, Product, ProductCategoryKind, Unit
from app.modules.collections.service import CollectionsService
from app.modules.customers.models import Customer, CustomerType
from app.modules.inventory.service import InventoryService
from app.modules.organizations.models import Warehouse
from app.modules.organizations.service import OrganizationProvisioningService
from app.modules.payments.models import PaymentMethod
from app.modules.sales.models import SalesInvoice
from app.modules.sales.wholesale_service import OrderLineInput, WholesaleService
from sqlalchemy import func, select

pytestmark = pytest.mark.usefixtures("db_ready")

TODAY = date(2026, 7, 11)


async def _setup_two_invoices() -> dict[str, uuid.UUID]:
    factory = get_sessionmaker()
    async with factory() as session:
        prov = await OrganizationProvisioningService(session).provision(
            org_name="Ledger Co",
            owner_email="owner@ledger.local",
            owner_password="OwnerPass123",
            owner_name="Owner",
        )
        org_id = prov.organization.id
        unit = Unit(organization_id=org_id, code="pcs", name="Pieces")
        cat = Category(
            organization_id=org_id,
            name="Fert",
            code="FERT",
            kind=ProductCategoryKind.FERTILIZER,
        )
        session.add_all([unit, cat])
        await session.flush()
        product = Product(
            organization_id=org_id,
            category_id=cat.id,
            base_unit_id=unit.id,
            name="DAP 50kg",
            sku="FERT-DAP",
            wholesale_price=Decimal("100.00"),
            retail_price=Decimal("100.00"),
            mrp=Decimal("100.00"),
            gst_rate=Decimal("0"),
        )
        dealer = Customer(
            organization_id=org_id,
            code="D1",
            name="Dealer",
            customer_type=CustomerType.DEALER,
            credit_limit=Decimal("1000000"),
        )
        wh = Warehouse(organization_id=org_id, branch_id=prov.branch.id, name="GD", code="GD1")
        session.add_all([product, dealer, wh])
        await session.flush()
        ids = {"org": org_id, "product": product.id, "dealer": dealer.id, "warehouse": wh.id}
        await InventoryService(session).receive(
            organization_id=org_id,
            warehouse_id=wh.id,
            product_id=product.id,
            base_quantity=Decimal("1000"),
        )
        await session.commit()

    # Create two wholesale credit invoices of 500 each (5 units @ 100, 0% GST).
    for _ in range(2):
        async with factory() as session:
            ws = WholesaleService(session)
            order = await ws.create_order(
                organization_id=ids["org"],
                warehouse_id=ids["warehouse"],
                customer_id=ids["dealer"],
                order_date=TODAY,
                as_of=TODAY,
                lines=[OrderLineInput(product_id=ids["product"], base_quantity=Decimal("5"))],
            )
            await session.commit()
        async with factory() as session:
            ws = WholesaleService(session)
            await ws.dispatch_and_invoice(
                organization_id=ids["org"],
                sales_order_id=order.sales_order_id,
                invoice_date=TODAY,
                as_of=TODAY,
            )
            await session.commit()
    return ids


async def test_partial_collection_allocates_fifo_and_balances_journal() -> None:
    ids = await _setup_two_invoices()
    factory = get_sessionmaker()

    async with factory() as session:
        collections = CollectionsService(session)
        balance = await collections.customer_ledger_balance(ids["org"], ids["dealer"])
        assert balance == Decimal("1000.00")  # two invoices of 500

        # Pay 700: settles the first invoice (500) fully, second partially (200).
        result = await collections.receive_payment(
            organization_id=ids["org"],
            customer_id=ids["dealer"],
            amount=Decimal("700.00"),
            method=PaymentMethod.CASH,
            payment_date=TODAY,
        )
        await session.commit()
        assert result.allocated_total == Decimal("700.00")
        assert result.unallocated == Decimal("0.00")
        assert len(result.settled_invoice_ids) == 1

    async with factory() as session:
        # One invoice PAID, one PARTIAL; ledger balance now 300.
        statuses = (
            (
                await session.execute(
                    select(SalesInvoice.payment_status).where(
                        SalesInvoice.customer_id == ids["dealer"]
                    )
                )
            )
            .scalars()
            .all()
        )
        assert sorted(s.value for s in statuses) == ["paid", "partial"]

        balance = await CollectionsService(session).customer_ledger_balance(
            ids["org"], ids["dealer"]
        )
        assert balance == Decimal("300.00")

    async with factory() as session:
        # The collection journal balances: total debits == total credits.
        entry = (
            (
                await session.execute(
                    select(JournalEntry).where(JournalEntry.source_document_type == "payment")
                )
            )
            .scalars()
            .first()
        )
        assert entry is not None
        totals = await session.execute(
            select(
                func.coalesce(func.sum(JournalEntryLine.debit), 0),
                func.coalesce(func.sum(JournalEntryLine.credit), 0),
            ).where(JournalEntryLine.journal_entry_id == entry.id)
        )
        debit, credit = totals.one()
        assert Decimal(str(debit)) == Decimal("700.00")
        assert Decimal(str(credit)) == Decimal("700.00")


async def test_overpayment_leaves_advance() -> None:
    ids = await _setup_two_invoices()
    factory = get_sessionmaker()
    async with factory() as session:
        collections = CollectionsService(session)
        result = await collections.receive_payment(
            organization_id=ids["org"],
            customer_id=ids["dealer"],
            amount=Decimal("1500.00"),
            method=PaymentMethod.UPI,
            payment_date=TODAY,
        )
        await session.commit()
        # 1000 settles both invoices; 500 remains as an unallocated advance.
        assert result.allocated_total == Decimal("1000.00")
        assert result.unallocated == Decimal("500.00")
        assert len(result.settled_invoice_ids) == 2
