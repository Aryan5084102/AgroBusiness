"""Customer endpoints: list (with credit + outstanding) and create."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import CurrentUser
from app.core.deps import db_session, require_permission
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.customers.models import Customer, CustomerType
from app.modules.sales.models import PaymentStatus, SalesInvoice

router = APIRouter(tags=["customers"])


class CustomerOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    customer_type: CustomerType
    phone: str | None
    gstin: str | None
    village: str | None
    credit_limit: Decimal
    credit_period_days: int
    outstanding: Decimal
    available_credit: Decimal
    is_active: bool


class CreateCustomerRequest(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    customer_type: CustomerType = CustomerType.RETAIL
    phone: str | None = Field(default=None, max_length=20)
    gstin: str | None = Field(default=None, max_length=20)
    village: str | None = Field(default=None, max_length=120)
    credit_limit: Decimal = Field(default=Decimal("0"), ge=0)
    credit_period_days: int = Field(default=0, ge=0, le=365)


class UpdateCustomerRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    customer_type: CustomerType | None = None
    phone: str | None = Field(default=None, max_length=20)
    gstin: str | None = Field(default=None, max_length=20)
    village: str | None = Field(default=None, max_length=120)
    credit_limit: Decimal | None = Field(default=None, ge=0)
    credit_period_days: int | None = Field(default=None, ge=0, le=365)
    is_active: bool | None = None


def _to_out(customer: Customer, outstanding: Decimal) -> CustomerOut:
    return CustomerOut(
        id=customer.id,
        code=customer.code,
        name=customer.name,
        customer_type=customer.customer_type,
        phone=customer.phone,
        gstin=customer.gstin,
        village=customer.village,
        credit_limit=customer.credit_limit,
        credit_period_days=customer.credit_period_days,
        outstanding=outstanding,
        available_credit=customer.credit_limit - outstanding,
        is_active=customer.is_active,
    )


@router.get("", response_model=list[CustomerOut])
async def list_customers(
    search: str | None = Query(default=None, max_length=100),
    user: CurrentUser = Depends(require_permission("customer.view")),
    session: AsyncSession = Depends(db_session),
) -> list[CustomerOut]:
    # Per-customer outstanding across non-paid invoices, computed in one query.
    outstanding_sq = (
        select(
            SalesInvoice.customer_id.label("cid"),
            func.coalesce(func.sum(SalesInvoice.grand_total - SalesInvoice.paid_amount), 0).label(
                "outstanding"
            ),
        )
        .where(SalesInvoice.payment_status != PaymentStatus.PAID)
        .group_by(SalesInvoice.customer_id)
        .subquery()
    )
    stmt = (
        select(Customer, func.coalesce(outstanding_sq.c.outstanding, 0))
        .outerjoin(outstanding_sq, outstanding_sq.c.cid == Customer.id)
        .where(Customer.organization_id == user.organization_id)
        .order_by(Customer.name)
    )
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(Customer.name.ilike(pattern), Customer.code.ilike(pattern)))

    rows = await session.execute(stmt)
    return [_to_out(customer, Decimal(str(outstanding))) for customer, outstanding in rows.all()]


async def _outstanding_for(session: AsyncSession, customer_id: uuid.UUID) -> Decimal:
    total = await session.scalar(
        select(
            func.coalesce(func.sum(SalesInvoice.grand_total - SalesInvoice.paid_amount), 0)
        ).where(
            SalesInvoice.customer_id == customer_id,
            SalesInvoice.payment_status != PaymentStatus.PAID,
        )
    )
    return Decimal(str(total or 0))


@router.get("/{customer_id}", response_model=CustomerOut)
async def get_customer(
    customer_id: uuid.UUID,
    user: CurrentUser = Depends(require_permission("customer.view")),
    session: AsyncSession = Depends(db_session),
) -> CustomerOut:
    customer = await session.get(Customer, customer_id)
    if customer is None or customer.organization_id != user.organization_id:
        raise NotFoundError("Unknown customer.")
    return _to_out(customer, await _outstanding_for(session, customer_id))


@router.post("", response_model=CustomerOut, status_code=201)
async def create_customer(
    payload: CreateCustomerRequest,
    user: CurrentUser = Depends(require_permission("customer.create")),
    session: AsyncSession = Depends(db_session),
) -> CustomerOut:
    duplicate = await session.scalar(
        select(func.count())
        .select_from(Customer)
        .where(
            Customer.organization_id == user.organization_id,
            Customer.code == payload.code,
        )
    )
    if duplicate:
        raise ConflictError(f"A customer with code {payload.code} already exists.")
    customer = Customer(
        organization_id=user.organization_id,
        code=payload.code,
        name=payload.name,
        customer_type=payload.customer_type,
        phone=payload.phone,
        gstin=payload.gstin,
        village=payload.village,
        credit_limit=payload.credit_limit,
        credit_period_days=payload.credit_period_days,
    )
    session.add(customer)
    await session.commit()
    # The session keeps objects alive after commit (expire_on_commit=False),
    # so refresh to return exactly what the database stored — NUMERIC columns
    # normalise scale, and a client sending "7500" must read back "7500.00".
    await session.refresh(customer)
    return _to_out(customer, Decimal("0.00"))


@router.patch("/{customer_id}", response_model=CustomerOut)
async def update_customer(
    customer_id: uuid.UUID,
    payload: UpdateCustomerRequest,
    user: CurrentUser = Depends(require_permission("customer.create")),
    session: AsyncSession = Depends(db_session),
) -> CustomerOut:
    customer = await session.get(Customer, customer_id)
    if customer is None or customer.organization_id != user.organization_id:
        raise NotFoundError("Unknown customer.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    await session.commit()
    await session.refresh(customer)
    return _to_out(customer, await _outstanding_for(session, customer_id))
