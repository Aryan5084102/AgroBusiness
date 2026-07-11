"""Retail POS endpoint. Finalized invoices are immutable (no update route)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import CurrentUser
from app.core.deps import db_session, require_permission
from app.modules.payments.models import PaymentMethod
from app.modules.sales.service import (
    PaymentInput,
    SaleLineInput,
    SalesService,
)

router = APIRouter(tags=["pos"])


class SaleLineBody(BaseModel):
    product_id: uuid.UUID
    base_quantity: Decimal = Field(gt=0)
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class PaymentBody(BaseModel):
    method: PaymentMethod
    amount: Decimal = Field(gt=0)
    reference: str | None = None


class CreateInvoiceRequest(BaseModel):
    warehouse_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    lines: list[SaleLineBody] = Field(min_length=1)
    payments: list[PaymentBody] = Field(default_factory=list)


class InvoiceResponse(BaseModel):
    invoice_id: uuid.UUID
    invoice_number: str
    grand_total: Decimal
    paid_amount: Decimal
    payment_status: str
    replayed: bool
    warnings: list[str]


@router.post("/invoices", response_model=InvoiceResponse, status_code=201)
async def create_invoice(
    payload: CreateInvoiceRequest,
    user: CurrentUser = Depends(require_permission("sales.create")),
    session: AsyncSession = Depends(db_session),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> InvoiceResponse:
    service = SalesService(session)
    result = await service.create_retail_invoice(
        organization_id=user.organization_id,
        warehouse_id=payload.warehouse_id,
        invoice_date=datetime.now(tz=timezone.utc).date(),
        lines=[
            SaleLineInput(
                product_id=ln.product_id,
                base_quantity=ln.base_quantity,
                discount_percent=ln.discount_percent,
            )
            for ln in payload.lines
        ],
        payments=[
            PaymentInput(method=p.method, amount=p.amount, reference=p.reference)
            for p in payload.payments
        ],
        customer_id=payload.customer_id,
        created_by=user.user_id,
        idempotency_key=idempotency_key,
        as_of=date.today(),
    )
    await session.commit()
    return InvoiceResponse(
        invoice_id=result.invoice_id,
        invoice_number=result.invoice_number,
        grand_total=result.grand_total,
        paid_amount=result.paid_amount,
        payment_status=result.payment_status.value,
        replayed=result.replayed,
        warnings=result.warnings,
    )
