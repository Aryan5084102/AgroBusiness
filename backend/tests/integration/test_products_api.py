"""Integration tests for the products list/search/create endpoint."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from app.core.database import get_sessionmaker
from app.modules.catalogue.models import Category, ProductCategoryKind, Unit
from app.modules.organizations.service import OrganizationProvisioningService
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("db_ready")


async def _seed() -> tuple[str, str, uuid.UUID, uuid.UUID]:
    factory = get_sessionmaker()
    async with factory() as session:
        prov = await OrganizationProvisioningService(session).provision(
            org_name="Cat Co",
            owner_email="owner@cat.local",
            owner_password="OwnerPass123",
            owner_name="Owner",
        )
        unit = Unit(organization_id=prov.organization.id, code="pcs", name="Pieces")
        cat = Category(
            organization_id=prov.organization.id,
            name="Seeds",
            code="SEED",
            kind=ProductCategoryKind.SEED,
        )
        session.add_all([unit, cat])
        await session.flush()
        cat_id, unit_id = cat.id, unit.id
        await session.commit()
    return "owner@cat.local", "OwnerPass123", cat_id, unit_id


async def test_create_list_and_search_products(api: AsyncClient) -> None:
    email, pw, cat_id, unit_id = await _seed()
    await api.post("/api/v1/auth/login", json={"email": email, "password": pw})

    # Empty to start.
    listing = await api.get("/api/v1/products")
    assert listing.status_code == 200
    assert listing.json()["total"] == 0

    # Create two products.
    for name, sku, price in [("Maize Seed", "MZ-1", "120"), ("Wheat Seed", "WH-1", "90")]:
        resp = await api.post(
            "/api/v1/products",
            json={
                "name": name,
                "sku": sku,
                "category_id": str(cat_id),
                "base_unit_id": str(unit_id),
                "retail_price": price,
                "gst_rate": "5",
            },
        )
        assert resp.status_code == 201, resp.text

    # List returns both.
    listing = await api.get("/api/v1/products")
    body = listing.json()
    assert body["total"] == 2
    assert {i["sku"] for i in body["items"]} == {"MZ-1", "WH-1"}

    # Search narrows to one.
    search = await api.get("/api/v1/products", params={"search": "maize"})
    sbody = search.json()
    assert sbody["total"] == 1
    assert sbody["items"][0]["name"] == "Maize Seed"
    assert Decimal(sbody["items"][0]["retail_price"]) == Decimal("120.00")


async def test_products_requires_permission(api: AsyncClient) -> None:
    await _seed()
    # Create an accountant (whose role lacks product.view).
    factory = get_sessionmaker()
    async with factory() as session:
        from app.modules.organizations.models import Organization
        from sqlalchemy import select

        org = (
            (await session.execute(select(Organization).where(Organization.name == "Cat Co")))
            .scalars()
            .first()
        )
        assert org is not None
        await OrganizationProvisioningService(session).create_user(
            organization_id=org.id,
            email="acc@cat.local",
            password="AccPass1234",
            full_name="Accountant",
            role_code="accountant",
            branch_id=None,
        )
        await session.commit()

    await api.post(
        "/api/v1/auth/login",
        json={"email": "acc@cat.local", "password": "AccPass1234"},
    )
    # accountant lacks product.view.
    resp = await api.get("/api/v1/products")
    assert resp.status_code == 403
