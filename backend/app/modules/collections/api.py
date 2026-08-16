"""Collections endpoint: receive a customer payment (RBAC: payment.receive)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.money import Money
from app.core.context import CurrentUser
from app.core.deps import db_session, require_permission
from app.modules.collections.service import CollectionsService
from app.modules.customers.models import Customer
from app.modules.payments.models import Payment, PaymentDirection, PaymentMethod
from app.modules.sales.models import PaymentStatus, SalesInvoice
from app.modules.users.models import User

router = APIRouter(tags=["collections"])


class OutstandingInvoiceOut(BaseModel):
    id: uuid.UUID
    invoice_number: str
    invoice_date: date
    grand_total: Decimal
    paid_amount: Decimal
    outstanding: Decimal
    payment_status: str


class OutstandingResponse(BaseModel):
    invoices: list[OutstandingInvoiceOut]
    total_outstanding: Decimal


@router.get("/outstanding", response_model=OutstandingResponse)
async def outstanding(
    customer_id: uuid.UUID = Query(...),
    user: CurrentUser = Depends(require_permission("payment.receive")),
    session: AsyncSession = Depends(db_session),
) -> OutstandingResponse:
    rows = await session.execute(
        select(SalesInvoice)
        .where(
            SalesInvoice.organization_id == user.organization_id,
            SalesInvoice.customer_id == customer_id,
            SalesInvoice.payment_status != PaymentStatus.PAID,
        )
        .order_by(SalesInvoice.invoice_date, SalesInvoice.created_at)
    )
    invoices = list(rows.scalars().all())
    total = Money(sum((i.grand_total - i.paid_amount for i in invoices), Decimal("0")))
    return OutstandingResponse(
        invoices=[
            OutstandingInvoiceOut(
                id=i.id,
                invoice_number=i.invoice_number,
                invoice_date=i.invoice_date,
                grand_total=i.grand_total,
                paid_amount=i.paid_amount,
                outstanding=i.grand_total - i.paid_amount,
                payment_status=i.payment_status.value,
            )
            for i in invoices
        ],
        total_outstanding=total,
    )


class ReceivablesRow(BaseModel):
    customer_id: uuid.UUID
    customer_name: str
    customer_code: str
    phone: str | None
    open_invoices: int
    outstanding: Decimal
    oldest_invoice_date: date | None
    days_overdue: int


class ReceivablesResponse(BaseModel):
    rows: list[ReceivablesRow]
    total_outstanding: Decimal


@router.get("/receivables", response_model=ReceivablesResponse)
async def receivables(
    user: CurrentUser = Depends(require_permission("payment.receive")),
    session: AsyncSession = Depends(db_session),
) -> ReceivablesResponse:
    """Every customer who owes money, largest balance first."""
    today = datetime.now(tz=timezone.utc).date()
    stmt = (
        select(
            Customer.id,
            Customer.name,
            Customer.code,
            Customer.phone,
            func.count(SalesInvoice.id),
            func.coalesce(func.sum(SalesInvoice.grand_total - SalesInvoice.paid_amount), 0),
            func.min(SalesInvoice.invoice_date),
        )
        .join(SalesInvoice, SalesInvoice.customer_id == Customer.id)
        .where(
            Customer.organization_id == user.organization_id,
            SalesInvoice.payment_status != PaymentStatus.PAID,
        )
        .group_by(Customer.id, Customer.name, Customer.code, Customer.phone)
        .having(func.sum(SalesInvoice.grand_total - SalesInvoice.paid_amount) > 0)
        .order_by(func.sum(SalesInvoice.grand_total - SalesInvoice.paid_amount).desc())
    )
    rows: list[ReceivablesRow] = []
    total = Decimal("0.00")
    for cid, name, code, phone, count, outstanding, oldest in (await session.execute(stmt)).all():
        amount = Money(Decimal(str(outstanding)))
        total = Money(total + amount)
        rows.append(
            ReceivablesRow(
                customer_id=cid,
                customer_name=name,
                customer_code=code,
                phone=phone,
                open_invoices=int(count),
                outstanding=amount,
                oldest_invoice_date=oldest,
                days_overdue=(today - oldest).days if oldest else 0,
            )
        )
    return ReceivablesResponse(rows=rows, total_outstanding=total)


class PaymentOut(BaseModel):
    id: uuid.UUID
    received_at: datetime
    customer_id: uuid.UUID | None
    customer_name: str | None
    method: PaymentMethod
    amount: Decimal
    reference: str | None
    received_by: str | None


class PaymentPage(BaseModel):
    items: list[PaymentOut]
    total: int
    limit: int
    offset: int
    total_amount: Decimal


@router.get("/payments", response_model=PaymentPage)
async def list_payments(
    customer_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_permission("payment.receive")),
    session: AsyncSession = Depends(db_session),
) -> PaymentPage:
    """Money received, newest first."""
    base = (
        select(Payment, Customer.name, User.full_name)
        .outerjoin(Customer, Customer.id == Payment.customer_id)
        .outerjoin(User, User.id == Payment.created_by)
        .where(
            Payment.organization_id == user.organization_id,
            Payment.direction == PaymentDirection.INBOUND,
        )
    )
    if customer_id is not None:
        base = base.where(Payment.customer_id == customer_id)
    if date_from is not None:
        base = base.where(func.date(Payment.received_at) >= date_from)
    if date_to is not None:
        base = base.where(func.date(Payment.received_at) <= date_to)

    subquery = base.subquery()
    total = await session.scalar(select(func.count()).select_from(subquery))
    total_amount = await session.scalar(select(func.coalesce(func.sum(subquery.c.amount), 0)))
    rows = await session.execute(
        base.order_by(Payment.received_at.desc()).limit(limit).offset(offset)
    )
    return PaymentPage(
        items=[
            PaymentOut(
                id=p.id,
                received_at=p.received_at,
                customer_id=p.customer_id,
                customer_name=customer_name,
                method=p.method,
                amount=p.amount,
                reference=p.reference,
                received_by=actor,
            )
            for p, customer_name, actor in rows.all()
        ],
        total=int(total or 0),
        limit=limit,
        offset=offset,
        total_amount=Decimal(str(total_amount or 0)),
    )


class ReceivePaymentRequest(BaseModel):
    customer_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    method: PaymentMethod
    reference: str | None = None


class ReceivePaymentResponse(BaseModel):
    payment_id: uuid.UUID
    allocated_total: Decimal
    unallocated: Decimal
    settled_invoice_ids: list[uuid.UUID]


@router.post("/payments", response_model=ReceivePaymentResponse, status_code=201)
async def receive_payment(
    payload: ReceivePaymentRequest,
    user: CurrentUser = Depends(require_permission("payment.receive")),
    session: AsyncSession = Depends(db_session),
) -> ReceivePaymentResponse:
    service = CollectionsService(session)
    result = await service.receive_payment(
        organization_id=user.organization_id,
        customer_id=payload.customer_id,
        amount=payload.amount,
        method=payload.method,
        payment_date=datetime.now(tz=timezone.utc).date(),
        reference=payload.reference,
        created_by=user.user_id,
    )
    await session.commit()
    return ReceivePaymentResponse(
        payment_id=result.payment_id,
        allocated_total=result.allocated_total,
        unallocated=result.unallocated,
        settled_invoice_ids=result.settled_invoice_ids,
    )
