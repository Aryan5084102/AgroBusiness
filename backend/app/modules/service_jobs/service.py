"""Service-job service: repair jobs, warranty check, spare-part consumption.

Consuming a spare part posts a REPAIR_CONSUMPTION movement to the stock ledger;
returning it posts a REPAIR_RETURN movement (a new audited reversal, never an
edit). Customer-payable = labour + parts, with parts waived when under warranty.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.money import Money
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.modules.catalogue.models import Product
from app.modules.inventory.models import MovementType
from app.modules.inventory.service import InventoryService
from app.modules.numbering.service import NumberingService
from app.modules.service_jobs.models import RepairJob, RepairJobPart, RepairStatus
from app.modules.warranties.models import Warranty


@dataclass
class ConsumePartResult:
    repair_job_part_id: uuid.UUID
    parts_total: Decimal
    customer_payable: Decimal


class ServiceJobService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._numbering = NumberingService(session)
        self._inventory = InventoryService(session)

    async def is_under_warranty(self, serial_id: uuid.UUID, as_of: date) -> Warranty | None:
        result = await self._session.execute(
            select(Warranty).where(
                Warranty.serial_id == serial_id,
                Warranty.start_date <= as_of,
                Warranty.end_date >= as_of,
            )
        )
        return result.scalars().first()

    async def create_job(
        self,
        *,
        organization_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        received_date: date,
        customer_id: uuid.UUID | None = None,
        product_id: uuid.UUID | None = None,
        serial_id: uuid.UUID | None = None,
        complaint: str | None = None,
        branch_id: uuid.UUID | None = None,
        technician_id: uuid.UUID | None = None,
    ) -> RepairJob:
        job_number = await self._numbering.next_number(
            organization_id=organization_id,
            document_type="repair_job",
            branch_id=branch_id,
        )
        warranty = None
        if serial_id is not None:
            warranty = await self.is_under_warranty(serial_id, received_date)
        job = RepairJob(
            organization_id=organization_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            job_number=job_number,
            customer_id=customer_id,
            product_id=product_id,
            serial_id=serial_id,
            warranty_id=warranty.id if warranty else None,
            is_warranty_covered=warranty is not None,
            technician_id=technician_id,
            complaint=complaint,
            status=RepairStatus.RECEIVED,
            received_date=received_date,
        )
        self._session.add(job)
        await self._session.flush()
        return job

    async def consume_part(
        self,
        *,
        organization_id: uuid.UUID,
        repair_job_id: uuid.UUID,
        product_id: uuid.UUID,
        base_quantity: Decimal,
        created_by: uuid.UUID | None = None,
        as_of: date | None = None,
    ) -> ConsumePartResult:
        job = await self._get_job(organization_id, repair_job_id)
        if base_quantity <= 0:
            raise BusinessRuleError("Part quantity must be positive.")
        product = await self._session.get(Product, product_id)
        if product is None or product.organization_id != organization_id:
            raise NotFoundError("Unknown part.")

        posted = await self._inventory.issue_fefo(
            organization_id=organization_id,
            warehouse_id=job.warehouse_id,
            product_id=product_id,
            base_quantity=base_quantity,
            movement_type=MovementType.REPAIR_CONSUMPTION,
            branch_id=job.branch_id,
            source_document_type="repair_job",
            source_document_id=job.id,
            created_by=created_by,
            as_of=as_of,
        )
        part = RepairJobPart(
            repair_job_id=job.id,
            product_id=product_id,
            base_quantity=base_quantity,
            unit_price=product.retail_price,
            # One movement per batch is possible; store the first as the anchor.
            consumption_movement_id=posted[0].movement_id if posted else None,
        )
        self._session.add(part)
        await self._session.flush()

        line_value = Money(product.retail_price * base_quantity)
        job.parts_total = Money(job.parts_total + line_value)
        self._recompute_payable(job)
        await self._session.flush()
        return ConsumePartResult(
            repair_job_part_id=part.id,
            parts_total=job.parts_total,
            customer_payable=job.customer_payable,
        )

    async def return_part(
        self,
        *,
        organization_id: uuid.UUID,
        repair_job_part_id: uuid.UUID,
        created_by: uuid.UUID | None = None,
    ) -> None:
        part = await self._session.get(RepairJobPart, repair_job_part_id)
        if part is None:
            raise NotFoundError("Unknown repair-job part.")
        if part.is_returned:
            raise BusinessRuleError("Part already returned.", code="already_returned")
        job = await self._get_job(organization_id, part.repair_job_id)

        posted = await self._inventory.post_movement(
            organization_id=organization_id,
            warehouse_id=job.warehouse_id,
            product_id=part.product_id,
            movement_type=MovementType.REPAIR_RETURN,
            base_quantity=part.base_quantity,
            branch_id=job.branch_id,
            source_document_type="repair_job",
            source_document_id=job.id,
            created_by=created_by,
        )
        part.is_returned = True
        part.return_movement_id = posted.movement_id
        job.parts_total = Money(job.parts_total - Money(part.unit_price * part.base_quantity))
        self._recompute_payable(job)
        await self._session.flush()

    async def set_labour_and_complete(
        self,
        *,
        organization_id: uuid.UUID,
        repair_job_id: uuid.UUID,
        labour_charges: Decimal,
        completed_date: date,
    ) -> RepairJob:
        job = await self._get_job(organization_id, repair_job_id)
        job.labour_charges = Money(labour_charges)
        self._recompute_payable(job)
        job.status = RepairStatus.READY
        job.completed_date = completed_date
        await self._session.flush()
        return job

    def _recompute_payable(self, job: RepairJob) -> None:
        # Parts are waived when the job is warranty-covered; labour always billed.
        parts = Decimal("0.00") if job.is_warranty_covered else job.parts_total
        job.customer_payable = Money(job.labour_charges + parts)

    async def _get_job(self, organization_id: uuid.UUID, repair_job_id: uuid.UUID) -> RepairJob:
        job = await self._session.get(RepairJob, repair_job_id)
        if job is None or job.organization_id != organization_id:
            raise NotFoundError("Unknown repair job.")
        return job
