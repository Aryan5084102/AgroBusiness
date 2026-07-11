"""Integration test for the goods-receipt HTTP endpoint (receives stock)."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from app.core.database import get_sessionmaker
from app.modules.catalogue.models import Category, Product, ProductCategoryKind, Unit
from app.modules.inventory.models import StockBalance
from app.modules.organizations.models import Warehouse
from app.modules.organizations.service import OrganizationProvisioningService
from app.modules.suppliers.models import Supplier
from httpx import AsyncClient
from sqlalchemy import func, select

pytestmark = pytest.mark.usefixtures("db_ready")


async def _seed() -> dict[str, uuid.UUID]:
    factory = get_sessionmaker()
    async with factory() as session:
        prov = await OrganizationProvisioningService(session).provision(
            org_name="GR Co",
            owner_email="owner@gr.local",
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
            name="Maize",
            sku="MZ",
            tracks_batches=True,
            tracks_expiry=True,
        )
        supplier = Supplier(organization_id=org_id, code="S1", name="AgriSeeds")
        wh = Warehouse(organization_id=org_id, branch_id=prov.branch.id, name="GD", code="GD1")
        session.add_all([product, supplier, wh])
        await session.flush()
        ids = {
            "org": org_id,
            "product": product.id,
            "supplier": supplier.id,
            "warehouse": wh.id,
        }
        await session.commit()
        return ids


async def test_goods_receipt_increases_stock_with_landed_cost(api: AsyncClient) -> None:
    ids = await _seed()
    await api.post(
        "/api/v1/auth/login",
        json={"email": "owner@gr.local", "password": "OwnerPass123"},
    )

    resp = await api.post(
        "/api/v1/purchases/goods-receipts",
        json={
            "warehouse_id": str(ids["warehouse"]),
            "supplier_id": str(ids["supplier"]),
            "freight": "500",
            "lines": [
                {
                    "product_id": str(ids["product"]),
                    "received_base_quantity": "100",
                    "unit_rate": "50",
                    "batch_number": "MZ-B1",
                    "expiry_date": "2027-06-30",
                }
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["grn_number"].startswith("GRN-")
    # (100*50 + 500 freight) / 100 = 55.00 landed unit cost.
    assert Decimal(body["landed_unit_costs"][0]["landed_unit_cost"]) == Decimal("55.0000")

    factory = get_sessionmaker()
    async with factory() as session:
        on_hand = await session.execute(
            select(func.coalesce(func.sum(StockBalance.on_hand), 0)).where(
                StockBalance.product_id == ids["product"]
            )
        )
        assert Decimal(str(on_hand.scalar())) == Decimal("100.000")


async def test_goods_receipt_requires_permission(api: AsyncClient) -> None:
    ids = await _seed()
    # An accountant lacks purchase.create.
    factory = get_sessionmaker()
    async with factory() as session:
        await OrganizationProvisioningService(session).create_user(
            organization_id=ids["org"],
            email="acc@gr.local",
            password="AccPass1234",
            full_name="Acc",
            role_code="accountant",
            branch_id=None,
        )
        await session.commit()
    await api.post(
        "/api/v1/auth/login",
        json={"email": "acc@gr.local", "password": "AccPass1234"},
    )
    resp = await api.post(
        "/api/v1/purchases/goods-receipts",
        json={
            "warehouse_id": str(ids["warehouse"]),
            "supplier_id": str(ids["supplier"]),
            "lines": [
                {"product_id": str(ids["product"]), "received_base_quantity": "1", "unit_rate": "1"}
            ],
        },
    )
    assert resp.status_code == 403
