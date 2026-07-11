"""Wholesale endpoints: create order/quotation and dispatch→invoice."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import CurrentUser
from app.core.deps import db_session, require_permission
from app.modules.sales.wholesale_service import OrderLineInput, WholesaleService

router = APIRouter(tags=["wholesale"])


class OrderLineBody(BaseModel):
    product_id: uuid.UUID
    base_quantity: Decimal = Field(gt=0)
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class CreateOrderRequest(BaseModel):
    warehouse_id: uuid.UUID
    customer_id: uuid.UUID
    lines: list[OrderLineBody] = Field(min_length=1)
    is_quotation: bool = False
    credit_override_approved: bool = False


class OrderResponse(BaseModel):
    sales_order_id: uuid.UUID
    order_number: str
    status: str
    grand_total: Decimal
    warnings: list[str]


class DispatchResponse(BaseModel):
    sales_order_id: uuid.UUID
    sales_invoice_id: uuid.UUID
    invoice_number: str
    grand_total: Decimal


@router.post("/orders", response_model=OrderResponse, status_code=201)
async def create_order(
    payload: CreateOrderRequest,
    user: CurrentUser = Depends(require_permission("sales.create")),
    session: AsyncSession = Depends(db_session),
) -> OrderResponse:
    service = WholesaleService(session)
    result = await service.create_order(
        organization_id=user.organization_id,
        warehouse_id=payload.warehouse_id,
        customer_id=payload.customer_id,
        order_date=datetime.now(tz=timezone.utc).date(),
        lines=[
            OrderLineInput(
                product_id=ln.product_id,
                base_quantity=ln.base_quantity,
                discount_percent=ln.discount_percent,
            )
            for ln in payload.lines
        ],
        salesperson_id=user.user_id,
        is_quotation=payload.is_quotation,
        credit_override_approved=payload.credit_override_approved,
        as_of=date.today(),
    )
    await session.commit()
    return OrderResponse(
        sales_order_id=result.sales_order_id,
        order_number=result.order_number,
        status=result.status.value,
        grand_total=result.grand_total,
        warnings=result.warnings,
    )


@router.post(
    "/orders/{sales_order_id}/dispatch",
    response_model=DispatchResponse,
    status_code=201,
)
async def dispatch_order(
    sales_order_id: uuid.UUID,
    user: CurrentUser = Depends(require_permission("sales.finalize")),
    session: AsyncSession = Depends(db_session),
) -> DispatchResponse:
    service = WholesaleService(session)
    result = await service.dispatch_and_invoice(
        organization_id=user.organization_id,
        sales_order_id=sales_order_id,
        invoice_date=datetime.now(tz=timezone.utc).date(),
        created_by=user.user_id,
        as_of=date.today(),
    )
    await session.commit()
    return DispatchResponse(
        sales_order_id=result.sales_order_id,
        sales_invoice_id=result.sales_invoice_id,
        invoice_number=result.invoice_number,
        grand_total=result.grand_total,
    )
