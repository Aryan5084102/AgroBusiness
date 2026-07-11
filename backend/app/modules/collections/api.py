"""Collections endpoint: receive a customer payment (RBAC: payment.receive)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.money import Money
from app.core.context import CurrentUser
from app.core.deps import db_session, require_permission
from app.modules.collections.service import CollectionsService
from app.modules.payments.models import PaymentMethod
from app.modules.sales.models import PaymentStatus, SalesInvoice

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
