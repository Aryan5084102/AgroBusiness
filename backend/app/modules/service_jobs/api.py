"""Machine service endpoints: repair jobs, spare-part usage, completion.

All routes require ``service.manage``. Consuming a part deducts stock through the
inventory ledger (FEFO); returning it posts a reversing movement.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import CurrentUser
from app.core.deps import db_session, require_permission
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.modules.catalogue.models import Product
from app.modules.customers.models import Customer
from app.modules.service_jobs.models import RepairJob, RepairJobPart, RepairStatus
from app.modules.service_jobs.service import ServiceJobService
from app.modules.users.models import User

router = APIRouter(tags=["service"])


class JobPartOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    base_quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    is_returned: bool


class JobOut(BaseModel):
    id: uuid.UUID
    job_number: str
    status: RepairStatus
    customer_id: uuid.UUID | None
    customer_name: str | None
    product_id: uuid.UUID | None
    product_name: str | None
    technician_id: uuid.UUID | None
    technician_name: str | None
    warehouse_id: uuid.UUID
    complaint: str | None
    is_warranty_covered: bool
    labour_charges: Decimal
    parts_total: Decimal
    customer_payable: Decimal
    received_date: date
    completed_date: date | None
    created_at: datetime


class JobDetail(JobOut):
    parts: list[JobPartOut]


class JobPage(BaseModel):
    items: list[JobOut]
    total: int
    limit: int
    offset: int
    open_count: int


def _to_job_out(
    job: RepairJob,
    customer_name: str | None,
    product_name: str | None,
    technician_name: str | None,
) -> JobOut:
    return JobOut(
        id=job.id,
        job_number=job.job_number,
        status=job.status,
        customer_id=job.customer_id,
        customer_name=customer_name,
        product_id=job.product_id,
        product_name=product_name,
        technician_id=job.technician_id,
        technician_name=technician_name,
        warehouse_id=job.warehouse_id,
        complaint=job.complaint,
        is_warranty_covered=job.is_warranty_covered,
        labour_charges=job.labour_charges,
        parts_total=job.parts_total,
        customer_payable=job.customer_payable,
        received_date=job.received_date,
        completed_date=job.completed_date,
        created_at=job.created_at,
    )


# Statuses that still need work from the workshop.
_OPEN_STATUSES = [
    RepairStatus.RECEIVED,
    RepairStatus.UNDER_INSPECTION,
    RepairStatus.ESTIMATE_PREPARED,
    RepairStatus.AWAITING_APPROVAL,
    RepairStatus.APPROVED,
    RepairStatus.IN_PROGRESS,
    RepairStatus.WAITING_FOR_PART,
    RepairStatus.QUALITY_CHECK,
]


@router.get("/jobs", response_model=JobPage)
async def list_jobs(
    status: RepairStatus | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_permission("service.manage")),
    session: AsyncSession = Depends(db_session),
) -> JobPage:
    base = (
        select(RepairJob, Customer.name, Product.name, User.full_name)
        .outerjoin(Customer, Customer.id == RepairJob.customer_id)
        .outerjoin(Product, Product.id == RepairJob.product_id)
        .outerjoin(User, User.id == RepairJob.technician_id)
        .where(RepairJob.organization_id == user.organization_id)
    )
    if status is not None:
        base = base.where(RepairJob.status == status)
    if search:
        base = base.where(RepairJob.job_number.ilike(f"%{search.strip()}%"))

    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    open_count = await session.scalar(
        select(func.count())
        .select_from(RepairJob)
        .where(
            RepairJob.organization_id == user.organization_id,
            RepairJob.status.in_(_OPEN_STATUSES),
        )
    )
    rows = await session.execute(
        base.order_by(RepairJob.created_at.desc()).limit(limit).offset(offset)
    )
    return JobPage(
        items=[_to_job_out(job, cname, pname, tname) for job, cname, pname, tname in rows.all()],
        total=int(total or 0),
        limit=limit,
        offset=offset,
        open_count=int(open_count or 0),
    )


@router.get("/jobs/{job_id}", response_model=JobDetail)
async def get_job(
    job_id: uuid.UUID,
    user: CurrentUser = Depends(require_permission("service.manage")),
    session: AsyncSession = Depends(db_session),
) -> JobDetail:
    row = (
        await session.execute(
            select(RepairJob, Customer.name, Product.name, User.full_name)
            .outerjoin(Customer, Customer.id == RepairJob.customer_id)
            .outerjoin(Product, Product.id == RepairJob.product_id)
            .outerjoin(User, User.id == RepairJob.technician_id)
            .where(
                RepairJob.id == job_id,
                RepairJob.organization_id == user.organization_id,
            )
        )
    ).first()
    if row is None:
        raise NotFoundError("Unknown repair job.")
    job, cname, pname, tname = row

    part_rows = await session.execute(
        select(RepairJobPart, Product.name)
        .join(Product, Product.id == RepairJobPart.product_id)
        .where(RepairJobPart.repair_job_id == job.id)
        .order_by(RepairJobPart.created_at)
    )
    parts = [
        JobPartOut(
            id=part.id,
            product_id=part.product_id,
            product_name=product_name,
            base_quantity=part.base_quantity,
            unit_price=part.unit_price,
            line_total=part.unit_price * part.base_quantity,
            is_returned=part.is_returned,
        )
        for part, product_name in part_rows.all()
    ]
    return JobDetail(**_to_job_out(job, cname, pname, tname).model_dump(), parts=parts)


class CreateJobRequest(BaseModel):
    warehouse_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    complaint: str | None = Field(default=None, max_length=500)


@router.post("/jobs", response_model=JobOut, status_code=201)
async def create_job(
    payload: CreateJobRequest,
    user: CurrentUser = Depends(require_permission("service.manage")),
    session: AsyncSession = Depends(db_session),
) -> JobOut:
    job = await ServiceJobService(session).create_job(
        organization_id=user.organization_id,
        warehouse_id=payload.warehouse_id,
        received_date=datetime.now(tz=timezone.utc).date(),
        customer_id=payload.customer_id,
        product_id=payload.product_id,
        complaint=payload.complaint,
        branch_id=user.default_branch_id,
        technician_id=user.user_id,
    )
    await session.commit()
    return _to_job_out(job, None, None, None)


class UpdateStatusRequest(BaseModel):
    status: RepairStatus


@router.post("/jobs/{job_id}/status", response_model=JobOut)
async def update_status(
    job_id: uuid.UUID,
    payload: UpdateStatusRequest,
    user: CurrentUser = Depends(require_permission("service.manage")),
    session: AsyncSession = Depends(db_session),
) -> JobOut:
    job = await session.get(RepairJob, job_id)
    if job is None or job.organization_id != user.organization_id:
        raise NotFoundError("Unknown repair job.")
    if job.status in {RepairStatus.DELIVERED, RepairStatus.CANCELLED}:
        raise BusinessRuleError(
            "This job is closed and can no longer change status.", code="job_closed"
        )
    job.status = payload.status
    if payload.status == RepairStatus.DELIVERED and job.completed_date is None:
        job.completed_date = datetime.now(tz=timezone.utc).date()
    await session.commit()
    return _to_job_out(job, None, None, None)


class ConsumePartRequest(BaseModel):
    product_id: uuid.UUID
    base_quantity: Decimal = Field(gt=0)


class ConsumePartResponse(BaseModel):
    repair_job_part_id: uuid.UUID
    parts_total: Decimal
    customer_payable: Decimal


@router.post("/jobs/{job_id}/parts", response_model=ConsumePartResponse, status_code=201)
async def consume_part(
    job_id: uuid.UUID,
    payload: ConsumePartRequest,
    user: CurrentUser = Depends(require_permission("service.manage")),
    session: AsyncSession = Depends(db_session),
) -> ConsumePartResponse:
    result = await ServiceJobService(session).consume_part(
        organization_id=user.organization_id,
        repair_job_id=job_id,
        product_id=payload.product_id,
        base_quantity=payload.base_quantity,
        created_by=user.user_id,
    )
    await session.commit()
    return ConsumePartResponse(
        repair_job_part_id=result.repair_job_part_id,
        parts_total=result.parts_total,
        customer_payable=result.customer_payable,
    )


@router.post("/jobs/{job_id}/parts/{part_id}/return", status_code=200)
async def return_part(
    job_id: uuid.UUID,
    part_id: uuid.UUID,
    user: CurrentUser = Depends(require_permission("service.manage")),
    session: AsyncSession = Depends(db_session),
) -> dict[str, str]:
    await ServiceJobService(session).return_part(
        organization_id=user.organization_id,
        repair_job_part_id=part_id,
        created_by=user.user_id,
    )
    await session.commit()
    return {"status": "returned"}


class CompleteJobRequest(BaseModel):
    labour_charges: Decimal = Field(default=Decimal("0"), ge=0)


@router.post("/jobs/{job_id}/complete", response_model=JobOut)
async def complete_job(
    job_id: uuid.UUID,
    payload: CompleteJobRequest,
    user: CurrentUser = Depends(require_permission("service.manage")),
    session: AsyncSession = Depends(db_session),
) -> JobOut:
    """Set labour charges and mark the job ready for delivery."""
    job = await ServiceJobService(session).set_labour_and_complete(
        organization_id=user.organization_id,
        repair_job_id=job_id,
        labour_charges=payload.labour_charges,
        completed_date=datetime.now(tz=timezone.utc).date(),
    )
    await session.commit()
    return _to_job_out(job, None, None, None)
