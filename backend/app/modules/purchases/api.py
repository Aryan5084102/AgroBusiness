"""Purchase endpoints: unplanned goods receipt (receives stock + landed cost)."""

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
from app.core.exceptions import NotFoundError
from app.modules.catalogue.models import Product
from app.modules.organizations.models import Warehouse
from app.modules.purchases.models import GoodsReceipt, GoodsReceiptItem
from app.modules.purchases.service import (
    PurchaseService,
    ReceiptCharges,
    ReceiptLineInput,
)
from app.modules.suppliers.models import Supplier

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


class ReceiptListItem(BaseModel):
    id: uuid.UUID
    grn_number: str
    receipt_date: date
    supplier_id: uuid.UUID
    supplier_name: str
    warehouse_name: str
    line_count: int
    total_value: Decimal


class ReceiptPage(BaseModel):
    items: list[ReceiptListItem]
    total: int
    limit: int
    offset: int


class ReceiptItemOut(BaseModel):
    product_id: uuid.UUID
    product_name: str
    sku: str
    received_base_quantity: Decimal
    free_base_quantity: Decimal
    unit_rate: Decimal
    landed_unit_cost: Decimal
    line_value: Decimal


class ReceiptDetail(ReceiptListItem):
    items: list[ReceiptItemOut]


@router.get("/goods-receipts", response_model=ReceiptPage)
async def list_goods_receipts(
    supplier_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    search: str | None = Query(default=None, max_length=60),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_permission("purchase.view")),
    session: AsyncSession = Depends(db_session),
) -> ReceiptPage:
    """Goods-receipt history with per-receipt line count and goods value."""
    totals = (
        select(
            GoodsReceiptItem.goods_receipt_id.label("grn_id"),
            func.count().label("line_count"),
            func.coalesce(
                func.sum(GoodsReceiptItem.received_base_quantity * GoodsReceiptItem.unit_rate), 0
            ).label("total_value"),
        )
        .group_by(GoodsReceiptItem.goods_receipt_id)
        .subquery()
    )
    base = (
        select(
            GoodsReceipt,
            Supplier.name,
            Warehouse.name,
            func.coalesce(totals.c.line_count, 0),
            func.coalesce(totals.c.total_value, 0),
        )
        .join(Supplier, Supplier.id == GoodsReceipt.supplier_id)
        .join(Warehouse, Warehouse.id == GoodsReceipt.warehouse_id)
        .outerjoin(totals, totals.c.grn_id == GoodsReceipt.id)
        .where(GoodsReceipt.organization_id == user.organization_id)
    )
    if supplier_id is not None:
        base = base.where(GoodsReceipt.supplier_id == supplier_id)
    if date_from is not None:
        base = base.where(GoodsReceipt.receipt_date >= date_from)
    if date_to is not None:
        base = base.where(GoodsReceipt.receipt_date <= date_to)
    if search:
        base = base.where(GoodsReceipt.grn_number.ilike(f"%{search.strip()}%"))

    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    rows = await session.execute(
        base.order_by(GoodsReceipt.receipt_date.desc(), GoodsReceipt.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return ReceiptPage(
        items=[
            ReceiptListItem(
                id=grn.id,
                grn_number=grn.grn_number,
                receipt_date=grn.receipt_date,
                supplier_id=grn.supplier_id,
                supplier_name=supplier_name,
                warehouse_name=warehouse_name,
                line_count=int(line_count),
                total_value=Decimal(str(total_value)),
            )
            for grn, supplier_name, warehouse_name, line_count, total_value in rows.all()
        ],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


@router.get("/goods-receipts/{receipt_id}", response_model=ReceiptDetail)
async def get_goods_receipt(
    receipt_id: uuid.UUID,
    user: CurrentUser = Depends(require_permission("purchase.view")),
    session: AsyncSession = Depends(db_session),
) -> ReceiptDetail:
    row = (
        await session.execute(
            select(GoodsReceipt, Supplier.name, Warehouse.name)
            .join(Supplier, Supplier.id == GoodsReceipt.supplier_id)
            .join(Warehouse, Warehouse.id == GoodsReceipt.warehouse_id)
            .where(
                GoodsReceipt.id == receipt_id,
                GoodsReceipt.organization_id == user.organization_id,
            )
        )
    ).first()
    if row is None:
        raise NotFoundError("Unknown goods receipt.")
    grn, supplier_name, warehouse_name = row

    item_rows = await session.execute(
        select(GoodsReceiptItem, Product.name, Product.sku)
        .join(Product, Product.id == GoodsReceiptItem.product_id)
        .where(GoodsReceiptItem.goods_receipt_id == grn.id)
        .order_by(GoodsReceiptItem.created_at)
    )
    items = [
        ReceiptItemOut(
            product_id=item.product_id,
            product_name=name,
            sku=sku,
            received_base_quantity=item.received_base_quantity,
            free_base_quantity=item.free_base_quantity,
            unit_rate=item.unit_rate,
            landed_unit_cost=item.landed_unit_cost,
            line_value=item.received_base_quantity * item.unit_rate,
        )
        for item, name, sku in item_rows.all()
    ]
    return ReceiptDetail(
        id=grn.id,
        grn_number=grn.grn_number,
        receipt_date=grn.receipt_date,
        supplier_id=grn.supplier_id,
        supplier_name=supplier_name,
        warehouse_name=warehouse_name,
        line_count=len(items),
        total_value=sum((i.line_value for i in items), Decimal("0")),
        items=items,
    )


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
        branch_id=user.default_branch_id,
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
