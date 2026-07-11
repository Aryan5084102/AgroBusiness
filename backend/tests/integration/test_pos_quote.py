"""Integration tests for the POS quote + warehouses endpoints."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from app.core.database import get_sessionmaker
from app.modules.catalogue.models import Category, Product, ProductCategoryKind, Unit
from app.modules.inventory.service import InventoryService
from app.modules.organizations.models import Warehouse
from app.modules.organizations.service import OrganizationProvisioningService
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("db_ready")


async def _seed() -> dict[str, uuid.UUID]:
    factory = get_sessionmaker()
    async with factory() as session:
        prov = await OrganizationProvisioningService(session).provision(
            org_name="POS Co",
            owner_email="owner@pos.local",
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
            name="Neem Oil",
            sku="NEEM-1",
            retail_price=Decimal("100.00"),
            mrp=Decimal("100.00"),
            gst_rate=Decimal("18"),
        )
        wh = Warehouse(organization_id=org_id, branch_id=prov.branch.id, name="Shop", code="S1")
        session.add_all([product, wh])
        await session.flush()
        ids = {"org": org_id, "product": product.id, "warehouse": wh.id}
        await InventoryService(session).receive(
            organization_id=org_id,
            warehouse_id=wh.id,
            product_id=product.id,
            base_quantity=Decimal("40"),
        )
        await session.commit()
        return ids


async def test_warehouses_list_and_quote(api: AsyncClient) -> None:
    ids = await _seed()
    await api.post(
        "/api/v1/auth/login",
        json={"email": "owner@pos.local", "password": "OwnerPass123"},
    )

    # Warehouses endpoint returns the seeded shop.
    wh = await api.get("/api/v1/org/warehouses")
    assert wh.status_code == 200
    assert any(w["code"] == "S1" for w in wh.json())

    # Quote 3 units: net 300, 18% GST = 54, total 354; available stock 40.
    quote = await api.post(
        "/api/v1/pos/quote",
        json={
            "warehouse_id": str(ids["warehouse"]),
            "lines": [{"product_id": str(ids["product"]), "base_quantity": "3"}],
        },
    )
    assert quote.status_code == 200, quote.text
    body = quote.json()
    assert Decimal(body["grand_total"]) == Decimal("354.00")
    assert Decimal(body["tax_total"]) == Decimal("54.00")
    line = body["lines"][0]
    assert line["name"] == "Neem Oil"
    assert Decimal(line["available_stock"]) == Decimal("40.000")
    assert line["price_source"] == "retail"


async def test_quote_then_finalize_totals_match(api: AsyncClient) -> None:
    ids = await _seed()
    await api.post(
        "/api/v1/auth/login",
        json={"email": "owner@pos.local", "password": "OwnerPass123"},
    )
    cart = {
        "warehouse_id": str(ids["warehouse"]),
        "lines": [{"product_id": str(ids["product"]), "base_quantity": "2"}],
    }
    quote = (await api.post("/api/v1/pos/quote", json=cart)).json()
    grand = quote["grand_total"]

    # Paying exactly the quoted grand total finalizes cleanly (walk-in full pay).
    finalize = await api.post(
        "/api/v1/pos/invoices",
        headers={"Idempotency-Key": "term-1-tx-1"},
        json={**cart, "payments": [{"method": "cash", "amount": grand}]},
    )
    assert finalize.status_code == 201, finalize.text
    assert Decimal(finalize.json()["grand_total"]) == Decimal(grand)
    assert finalize.json()["payment_status"] == "paid"
