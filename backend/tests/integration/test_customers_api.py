"""Integration tests for the customers endpoint (list with outstanding, create)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.core.database import get_sessionmaker
from app.modules.organizations.service import OrganizationProvisioningService
from httpx import AsyncClient


async def _login_owner(api: AsyncClient) -> None:
    factory = get_sessionmaker()
    async with factory() as session:
        await OrganizationProvisioningService(session).provision(
            org_name="Cust Co",
            owner_email="owner@cust.local",
            owner_password="OwnerPass123",
            owner_name="Owner",
        )
        await session.commit()
    await api.post(
        "/api/v1/auth/login",
        json={"email": "owner@cust.local", "password": "OwnerPass123"},
    )


@pytest.mark.usefixtures("db_ready")
async def test_create_and_list_customers_with_credit(api: AsyncClient) -> None:
    await _login_owner(api)

    created = await api.post(
        "/api/v1/customers",
        json={
            "code": "D1",
            "name": "Green Dealer",
            "customer_type": "dealer",
            "credit_limit": "50000",
        },
    )
    assert created.status_code == 201, created.text
    assert Decimal(created.json()["available_credit"]) == Decimal("50000.00")

    listing = await api.get("/api/v1/customers")
    assert listing.status_code == 200
    body = listing.json()
    assert len(body) == 1
    row = body[0]
    assert row["name"] == "Green Dealer"
    assert Decimal(row["outstanding"]) == Decimal("0.00")
    assert Decimal(row["available_credit"]) == Decimal("50000.00")

    # Search narrows the list.
    search = await api.get("/api/v1/customers", params={"search": "green"})
    assert len(search.json()) == 1
    none = await api.get("/api/v1/customers", params={"search": "zzz"})
    assert len(none.json()) == 0
