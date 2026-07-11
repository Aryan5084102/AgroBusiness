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
from app.modules.customers.models import Customer, CustomerType
from app.modules.sales.models import PaymentStatus, SalesInvoice

router = APIRouter(tags=["customers"])


class CustomerOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    customer_type: CustomerType
    phone: str | None
    credit_limit: Decimal
    outstanding: Decimal
    available_credit: Decimal
    is_active: bool


class CreateCustomerRequest(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    customer_type: CustomerType = CustomerType.RETAIL
    phone: str | None = None
    credit_limit: Decimal = Field(default=Decimal("0"), ge=0)


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
    result: list[CustomerOut] = []
    for customer, outstanding in rows.all():
        out = Decimal(str(outstanding))
        result.append(
            CustomerOut(
                id=customer.id,
                code=customer.code,
                name=customer.name,
                customer_type=customer.customer_type,
                phone=customer.phone,
                credit_limit=customer.credit_limit,
                outstanding=out,
                available_credit=customer.credit_limit - out,
                is_active=customer.is_active,
            )
        )
    return result


@router.post("", response_model=CustomerOut, status_code=201)
async def create_customer(
    payload: CreateCustomerRequest,
    user: CurrentUser = Depends(require_permission("customer.create")),
    session: AsyncSession = Depends(db_session),
) -> CustomerOut:
    customer = Customer(
        organization_id=user.organization_id,
        code=payload.code,
        name=payload.name,
        customer_type=payload.customer_type,
        phone=payload.phone,
        credit_limit=payload.credit_limit,
    )
    session.add(customer)
    await session.commit()
    return CustomerOut(
        id=customer.id,
        code=customer.code,
        name=customer.name,
        customer_type=customer.customer_type,
        phone=customer.phone,
        credit_limit=customer.credit_limit,
        outstanding=Decimal("0.00"),
        available_credit=customer.credit_limit,
        is_active=customer.is_active,
    )
