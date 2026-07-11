"""Phase 2 inventory integration tests against real Postgres.

Exercises the append-only ledger + balance projection: receive stock into two
batches, issue via FEFO (earliest expiry first), block overselling, and confirm
the projected balance always equals the sum of ledger movements.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from app.core.database import get_sessionmaker
from app.core.exceptions import BusinessRuleError
from app.modules.catalogue.models import Category, Product, ProductCategoryKind, Unit
from app.modules.inventory.models import StockBalance, StockMovement
from app.modules.inventory.service import InventoryService
from app.modules.organizations.service import OrganizationProvisioningService
from sqlalchemy import func, select

pytestmark = pytest.mark.usefixtures("db_ready")

TODAY = date(2026, 7, 11)


async def _setup() -> dict[str, uuid.UUID]:
    factory = get_sessionmaker()
    async with factory() as session:
        result = await OrganizationProvisioningService(session).provision(
            org_name="Inv Co",
            owner_email="owner@inv.local",
            owner_password="OwnerPass123",
            owner_name="Owner",
        )
        org_id = result.organization.id
        unit = Unit(organization_id=org_id, code="pcs", name="Pieces")
        cat = Category(
            organization_id=org_id,
            name="Fungicides",
            code="FUNG",
            kind=ProductCategoryKind.FUNGICIDE,
        )
        session.add_all([unit, cat])
        await session.flush()
        product = Product(
            organization_id=org_id,
            category_id=cat.id,
            base_unit_id=unit.id,
            name="Copper Fungicide 1L",
            sku="FUNG-CU-1L",
            tracks_batches=True,
            tracks_expiry=True,
        )
        session.add(product)
        await session.flush()

        from app.modules.inventory.models import Batch

        near = Batch(
            organization_id=org_id,
            product_id=product.id,
            batch_number="NEAR",
            expiry_date=TODAY + timedelta(days=15),
        )
        far = Batch(
            organization_id=org_id,
            product_id=product.id,
            batch_number="FAR",
            expiry_date=TODAY + timedelta(days=120),
        )
        session.add_all([near, far])
        await session.flush()

        # A warehouse for this org.
        from app.modules.organizations.models import Warehouse

        wh = Warehouse(
            organization_id=org_id, branch_id=result.branch.id, name="Main WH", code="WH1"
        )
        session.add(wh)
        await session.flush()

        ids = {
            "org": org_id,
            "product": product.id,
            "warehouse": wh.id,
            "near": near.id,
            "far": far.id,
        }
        await session.commit()
        return ids


async def _sum_ledger(session, product_id: uuid.UUID) -> Decimal:
    total = await session.execute(
        select(func.coalesce(func.sum(StockMovement.base_quantity), 0)).where(
            StockMovement.product_id == product_id
        )
    )
    return Decimal(str(total.scalar()))


async def test_receive_then_fefo_issue_and_ledger_matches_balance() -> None:
    ids = await _setup()
    factory = get_sessionmaker()
    async with factory() as session:
        service = InventoryService(session)
        # Receive 5 into NEAR (expires sooner), 20 into FAR.
        await service.receive(
            organization_id=ids["org"],
            warehouse_id=ids["warehouse"],
            product_id=ids["product"],
            base_quantity=Decimal("5"),
            batch_id=ids["near"],
        )
        await service.receive(
            organization_id=ids["org"],
            warehouse_id=ids["warehouse"],
            product_id=ids["product"],
            base_quantity=Decimal("20"),
            batch_id=ids["far"],
        )
        await session.commit()

    async with factory() as session:
        service = InventoryService(session)
        posted = await service.issue_fefo(
            organization_id=ids["org"],
            warehouse_id=ids["warehouse"],
            product_id=ids["product"],
            base_quantity=Decimal("7"),
            as_of=TODAY,
        )
        await session.commit()
        # FEFO: 5 from NEAR then 2 from FAR.
        assert posted[0].batch_id == ids["near"]
        assert posted[0].base_quantity == Decimal("-5.000")
        assert posted[1].batch_id == ids["far"]
        assert posted[1].base_quantity == Decimal("-2.000")

    async with factory() as session:
        # Balance projection == sum of ledger movements (25 received - 7 issued).
        ledger_total = await _sum_ledger(session, ids["product"])
        assert ledger_total == Decimal("18.000")
        balances = await session.execute(
            select(func.coalesce(func.sum(StockBalance.on_hand), 0)).where(
                StockBalance.product_id == ids["product"]
            )
        )
        assert Decimal(str(balances.scalar())) == Decimal("18.000")


async def test_overselling_is_blocked() -> None:
    ids = await _setup()
    factory = get_sessionmaker()
    async with factory() as session:
        service = InventoryService(session)
        await service.receive(
            organization_id=ids["org"],
            warehouse_id=ids["warehouse"],
            product_id=ids["product"],
            base_quantity=Decimal("3"),
            batch_id=ids["far"],
        )
        await session.commit()

    async with factory() as session:
        service = InventoryService(session)
        with pytest.raises(BusinessRuleError) as exc:
            await service.issue_fefo(
                organization_id=ids["org"],
                warehouse_id=ids["warehouse"],
                product_id=ids["product"],
                base_quantity=Decimal("10"),
                as_of=TODAY,
            )
        assert exc.value.code == "insufficient_stock"


async def test_expired_batch_is_not_sold() -> None:
    ids = await _setup()
    factory = get_sessionmaker()
    async with factory() as session:
        service = InventoryService(session)
        await service.receive(
            organization_id=ids["org"],
            warehouse_id=ids["warehouse"],
            product_id=ids["product"],
            base_quantity=Decimal("5"),
            batch_id=ids["near"],
        )
        await session.commit()

    # As of a date after NEAR's expiry, the only stock is expired -> blocked.
    after_expiry = TODAY + timedelta(days=30)
    async with factory() as session:
        service = InventoryService(session)
        with pytest.raises(BusinessRuleError):
            await service.issue_fefo(
                organization_id=ids["org"],
                warehouse_id=ids["warehouse"],
                product_id=ids["product"],
                base_quantity=Decimal("1"),
                as_of=after_expiry,
            )
