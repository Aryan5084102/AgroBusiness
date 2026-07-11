"""Integration tests for the collections HTTP endpoints (outstanding + pay)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from app.core.database import get_sessionmaker
from app.modules.catalogue.models import Category, Product, ProductCategoryKind, Unit
from app.modules.customers.models import Customer, CustomerType
from app.modules.inventory.service import InventoryService
from app.modules.organizations.models import Warehouse
from app.modules.organizations.service import OrganizationProvisioningService
from app.modules.sales.wholesale_service import OrderLineInput, WholesaleService
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("db_ready")

TODAY = date(2026, 7, 11)


async def _seed_two_credit_invoices() -> dict[str, uuid.UUID]:
    factory = get_sessionmaker()
    async with factory() as session:
        prov = await OrganizationProvisioningService(session).provision(
            org_name="Coll Co",
            owner_email="owner@coll.local",
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
            name="DAP",
            sku="DAP-1",
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

    for _ in range(2):
        async with factory() as session:
            order = await WholesaleService(session).create_order(
                organization_id=ids["org"],
                warehouse_id=ids["warehouse"],
                customer_id=ids["dealer"],
                order_date=TODAY,
                as_of=TODAY,
                lines=[OrderLineInput(product_id=ids["product"], base_quantity=Decimal("5"))],
            )
            await session.commit()
        async with factory() as session:
            await WholesaleService(session).dispatch_and_invoice(
                organization_id=ids["org"],
                sales_order_id=order.sales_order_id,
                invoice_date=TODAY,
                as_of=TODAY,
            )
            await session.commit()
    return ids


async def test_outstanding_then_partial_payment(api: AsyncClient) -> None:
    ids = await _seed_two_credit_invoices()
    await api.post(
        "/api/v1/auth/login",
        json={"email": "owner@coll.local", "password": "OwnerPass123"},
    )

    # Two credit invoices of 500 each -> 1000 outstanding.
    out = await api.get(
        "/api/v1/collections/outstanding", params={"customer_id": str(ids["dealer"])}
    )
    assert out.status_code == 200
    body = out.json()
    assert len(body["invoices"]) == 2
    assert Decimal(body["total_outstanding"]) == Decimal("1000.00")

    # Pay 700: settles the oldest (500) fully, the next (200) partially.
    pay = await api.post(
        "/api/v1/collections/payments",
        json={"customer_id": str(ids["dealer"]), "amount": "700", "method": "cash"},
    )
    assert pay.status_code == 201, pay.text
    pbody = pay.json()
    assert Decimal(pbody["allocated_total"]) == Decimal("700.00")
    assert len(pbody["settled_invoice_ids"]) == 1

    # Outstanding now 300.
    out2 = await api.get(
        "/api/v1/collections/outstanding", params={"customer_id": str(ids["dealer"])}
    )
    assert Decimal(out2.json()["total_outstanding"]) == Decimal("300.00")
