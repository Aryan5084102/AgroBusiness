"""Purchase endpoints: unplanned goods receipt (receives stock + landed cost)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import CurrentUser
from app.core.deps import db_session, require_permission
from app.modules.purchases.service import (
    PurchaseService,
    ReceiptCharges,
    ReceiptLineInput,
)

router = APIRouter(tags=["purchases"])


class ReceiptLineBody(BaseModel):
    product_id: uuid.UUID
    received_base_quantity: Decimal = Field(gt=0)
    unit_rate: Decimal = Field(ge=0)
    free_base_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    trade_discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    batch_number: str | None = None
    expiry_date: date | None = None


class GoodsReceiptRequest(BaseModel):
    warehouse_id: uuid.UUID
    supplier_id: uuid.UUID
    lines: list[ReceiptLineBody] = Field(min_length=1)
    freight: Decimal = Field(default=Decimal("0"), ge=0)
    loading: Decimal = Field(default=Decimal("0"), ge=0)
    other_charges: Decimal = Field(default=Decimal("0"), ge=0)


class LandedCostOut(BaseModel):
    product_id: str
    landed_unit_cost: Decimal


class GoodsReceiptResponse(BaseModel):
    goods_receipt_id: uuid.UUID
    grn_number: str
    landed_unit_costs: list[LandedCostOut]


@router.post("/goods-receipts", response_model=GoodsReceiptResponse, status_code=201)
async def create_goods_receipt(
    payload: GoodsReceiptRequest,
    user: CurrentUser = Depends(require_permission("purchase.create")),
    session: AsyncSession = Depends(db_session),
) -> GoodsReceiptResponse:
    service = PurchaseService(session)
    result = await service.receive_goods(
        organization_id=user.organization_id,
        warehouse_id=payload.warehouse_id,
        supplier_id=payload.supplier_id,
        receipt_date=datetime.now(tz=timezone.utc).date(),
        charges=ReceiptCharges(
            freight=payload.freight,
            loading=payload.loading,
            other_charges=payload.other_charges,
        ),
        created_by=user.user_id,
        lines=[
            ReceiptLineInput(
                purchase_order_item_id=None,
                product_id=ln.product_id,
                received_base_quantity=ln.received_base_quantity,
                unit_rate=ln.unit_rate,
                free_base_quantity=ln.free_base_quantity,
                trade_discount_percent=ln.trade_discount_percent,
                batch_number=ln.batch_number,
                expiry_date=ln.expiry_date,
            )
            for ln in payload.lines
        ],
    )
    await session.commit()
    return GoodsReceiptResponse(
        goods_receipt_id=result.goods_receipt_id,
        grn_number=result.grn_number,
        landed_unit_costs=[
            LandedCostOut(product_id=pid, landed_unit_cost=cost)
            for pid, cost in result.landed_unit_costs.items()
        ],
    )
