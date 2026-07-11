"""Phase 7 service-job integration tests against real Postgres.

Covers: repair job creation, spare-part consumption deducts stock via the ledger
(REPAIR_CONSUMPTION), returning a part reverses it (REPAIR_RETURN), warranty
coverage waives parts, and labour is always billed.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from app.core.database import get_sessionmaker
from app.modules.catalogue.models import Category, Product, ProductCategoryKind, Unit
from app.modules.customers.models import Customer, CustomerType
from app.modules.inventory.models import SerialNumber, StockBalance, StockMovement
from app.modules.inventory.service import InventoryService
from app.modules.organizations.models import Warehouse
from app.modules.organizations.service import OrganizationProvisioningService
from app.modules.service_jobs.models import RepairStatus
from app.modules.service_jobs.service import ServiceJobService
from app.modules.warranties.models import Warranty
from sqlalchemy import func, select

pytestmark = pytest.mark.usefixtures("db_ready")

TODAY = date(2026, 7, 11)


async def _setup() -> dict[str, uuid.UUID]:
    factory = get_sessionmaker()
    async with factory() as session:
        prov = await OrganizationProvisioningService(session).provision(
            org_name="Svc Co",
            owner_email="owner@svc.local",
            owner_password="OwnerPass123",
            owner_name="Owner",
        )
        org_id = prov.organization.id
        unit = Unit(organization_id=org_id, code="pcs", name="Pieces")
        machine_cat = Category(
            organization_id=org_id,
            name="Machines",
            code="MACH",
            kind=ProductCategoryKind.MACHINE,
        )
        spare_cat = Category(
            organization_id=org_id,
            name="Spares",
            code="SPARE",
            kind=ProductCategoryKind.SPARE_PART,
        )
        session.add_all([unit, machine_cat, spare_cat])
        await session.flush()
        machine = Product(
            organization_id=org_id,
            category_id=machine_cat.id,
            base_unit_id=unit.id,
            name="Power Sprayer",
            sku="MACH-SPR",
            tracks_serials=True,
        )
        part = Product(
            organization_id=org_id,
            category_id=spare_cat.id,
            base_unit_id=unit.id,
            name="Nozzle",
            sku="SPARE-NOZ",
            retail_price=Decimal("150.00"),
        )
        serial = SerialNumber(organization_id=org_id, product_id=machine.id, serial="SPR-0001")
        customer = Customer(
            organization_id=org_id,
            code="C1",
            name="Farmer",
            customer_type=CustomerType.FARMER,
        )
        wh = Warehouse(organization_id=org_id, branch_id=prov.branch.id, name="Svc WH", code="SW1")
        session.add_all([machine, part, customer, wh])
        await session.flush()
        serial.product_id = machine.id
        session.add(serial)
        await session.flush()
        ids = {
            "org": org_id,
            "branch": prov.branch.id,
            "machine": machine.id,
            "part": part.id,
            "serial": serial.id,
            "customer": customer.id,
            "warehouse": wh.id,
        }
        # Stock 10 nozzles.
        await InventoryService(session).receive(
            organization_id=org_id,
            warehouse_id=wh.id,
            product_id=part.id,
            base_quantity=Decimal("10"),
        )
        await session.commit()
        return ids


async def _part_stock(product_id: uuid.UUID) -> Decimal:
    factory = get_sessionmaker()
    async with factory() as session:
        row = await session.execute(
            select(func.coalesce(func.sum(StockBalance.on_hand), 0)).where(
                StockBalance.product_id == product_id
            )
        )
        return Decimal(str(row.scalar()))


async def test_consume_and_return_spare_part_moves_stock() -> None:
    ids = await _setup()
    factory = get_sessionmaker()
    async with factory() as session:
        svc = ServiceJobService(session)
        job = await svc.create_job(
            organization_id=ids["org"],
            warehouse_id=ids["warehouse"],
            received_date=TODAY,
            customer_id=ids["customer"],
            product_id=ids["machine"],
            serial_id=ids["serial"],
            complaint="Not spraying",
        )
        await session.commit()
        assert job.job_number.startswith("JOB-")
        assert job.status == RepairStatus.RECEIVED
        job_id = job.id

    async with factory() as session:
        svc = ServiceJobService(session)
        consume = await svc.consume_part(
            organization_id=ids["org"],
            repair_job_id=job_id,
            product_id=ids["part"],
            base_quantity=Decimal("2"),
            as_of=TODAY,
        )
        await session.commit()
        assert consume.parts_total == Decimal("300.00")  # 2 * 150

    assert await _part_stock(ids["part"]) == Decimal("8.000")  # 10 - 2 consumed

    # Return one part-line -> stock comes back.
    async with factory() as session:
        from app.modules.service_jobs.models import RepairJobPart

        part_line = (
            (
                await session.execute(
                    select(RepairJobPart).where(RepairJobPart.repair_job_id == job_id)
                )
            )
            .scalars()
            .first()
        )
        assert part_line is not None
        svc = ServiceJobService(session)
        await svc.return_part(organization_id=ids["org"], repair_job_part_id=part_line.id)
        await session.commit()

    assert await _part_stock(ids["part"]) == Decimal("10.000")  # returned

    async with factory() as session:
        # Ledger has both a consumption (-) and a return (+) movement.
        moves = (
            (
                await session.execute(
                    select(StockMovement.movement_type).where(
                        StockMovement.product_id == ids["part"],
                        StockMovement.source_document_type == "repair_job",
                    )
                )
            )
            .scalars()
            .all()
        )
        kinds = {m.value for m in moves}
        assert "repair_consumption" in kinds
        assert "repair_return" in kinds


async def test_warranty_covered_job_waives_parts_but_bills_labour() -> None:
    ids = await _setup()
    factory = get_sessionmaker()
    # Active warranty on the serial.
    async with factory() as session:
        session.add(
            Warranty(
                organization_id=ids["org"],
                product_id=ids["machine"],
                serial_id=ids["serial"],
                customer_id=ids["customer"],
                start_date=TODAY - timedelta(days=30),
                end_date=TODAY + timedelta(days=335),
            )
        )
        await session.commit()

    async with factory() as session:
        svc = ServiceJobService(session)
        job = await svc.create_job(
            organization_id=ids["org"],
            warehouse_id=ids["warehouse"],
            received_date=TODAY,
            customer_id=ids["customer"],
            product_id=ids["machine"],
            serial_id=ids["serial"],
        )
        await session.commit()
        assert job.is_warranty_covered is True
        job_id = job.id

    async with factory() as session:
        svc = ServiceJobService(session)
        await svc.consume_part(
            organization_id=ids["org"],
            repair_job_id=job_id,
            product_id=ids["part"],
            base_quantity=Decimal("1"),
            as_of=TODAY,
        )
        result = await svc.set_labour_and_complete(
            organization_id=ids["org"],
            repair_job_id=job_id,
            labour_charges=Decimal("200.00"),
            completed_date=TODAY,
        )
        await session.commit()
        # Parts waived (warranty); only labour billed.
        assert result.parts_total == Decimal("150.00")
        assert result.customer_payable == Decimal("200.00")
        assert result.status == RepairStatus.READY
