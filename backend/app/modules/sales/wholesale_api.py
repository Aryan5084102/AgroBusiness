"""Wholesale endpoints: create order/quotation and dispatch→invoice."""

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
from app.modules.customers.models import Customer
from app.modules.organizations.models import Warehouse
from app.modules.sales.order_models import SalesOrder, SalesOrderItem, SalesOrderStatus
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


class OrderListItem(BaseModel):
    id: uuid.UUID
    order_number: str
    order_date: date
    status: SalesOrderStatus
    customer_id: uuid.UUID
    customer_name: str
    warehouse_name: str
    grand_total: Decimal
    credit_override_approved: bool
    sales_invoice_id: uuid.UUID | None


class OrderPage(BaseModel):
    items: list[OrderListItem]
    total: int
    limit: int
    offset: int
    open_value: Decimal


class OrderItemOut(BaseModel):
    product_id: uuid.UUID
    product_name: str
    sku: str
    base_quantity: Decimal
    reserved_quantity: Decimal
    dispatched_quantity: Decimal
    unit_price: Decimal
    price_source: str
    taxable_value: Decimal
    gst_rate: Decimal
    tax_amount: Decimal
    line_total: Decimal


class OrderDetail(OrderListItem):
    subtotal: Decimal
    tax_total: Decimal
    items: list[OrderItemOut]


def _to_order_item(order: SalesOrder, customer_name: str, warehouse_name: str) -> OrderListItem:
    return OrderListItem(
        id=order.id,
        order_number=order.order_number,
        order_date=order.order_date,
        status=order.status,
        customer_id=order.customer_id,
        customer_name=customer_name,
        warehouse_name=warehouse_name,
        grand_total=order.grand_total,
        credit_override_approved=order.credit_override_approved,
        sales_invoice_id=order.sales_invoice_id,
    )


# Orders still awaiting dispatch/invoicing.
_OPEN_ORDER_STATUSES = [
    SalesOrderStatus.QUOTATION,
    SalesOrderStatus.CONFIRMED,
    SalesOrderStatus.PARTIALLY_DISPATCHED,
]


@router.get("/orders", response_model=OrderPage)
async def list_orders(
    status: SalesOrderStatus | None = Query(default=None),
    customer_id: uuid.UUID | None = Query(default=None),
    search: str | None = Query(default=None, max_length=60),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_permission("sales.create")),
    session: AsyncSession = Depends(db_session),
) -> OrderPage:
    base = (
        select(SalesOrder, Customer.name, Warehouse.name)
        .join(Customer, Customer.id == SalesOrder.customer_id)
        .join(Warehouse, Warehouse.id == SalesOrder.warehouse_id)
        .where(SalesOrder.organization_id == user.organization_id)
    )
    if status is not None:
        base = base.where(SalesOrder.status == status)
    if customer_id is not None:
        base = base.where(SalesOrder.customer_id == customer_id)
    if search:
        base = base.where(SalesOrder.order_number.ilike(f"%{search.strip()}%"))

    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    open_value = await session.scalar(
        select(func.coalesce(func.sum(SalesOrder.grand_total), 0)).where(
            SalesOrder.organization_id == user.organization_id,
            SalesOrder.status.in_(_OPEN_ORDER_STATUSES),
        )
    )
    rows = await session.execute(
        base.order_by(SalesOrder.order_date.desc(), SalesOrder.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return OrderPage(
        items=[_to_order_item(o, cname, wname) for o, cname, wname in rows.all()],
        total=int(total or 0),
        limit=limit,
        offset=offset,
        open_value=Decimal(str(open_value or 0)),
    )


@router.get("/orders/{sales_order_id}", response_model=OrderDetail)
async def get_order(
    sales_order_id: uuid.UUID,
    user: CurrentUser = Depends(require_permission("sales.create")),
    session: AsyncSession = Depends(db_session),
) -> OrderDetail:
    row = (
        await session.execute(
            select(SalesOrder, Customer.name, Warehouse.name)
            .join(Customer, Customer.id == SalesOrder.customer_id)
            .join(Warehouse, Warehouse.id == SalesOrder.warehouse_id)
            .where(
                SalesOrder.id == sales_order_id,
                SalesOrder.organization_id == user.organization_id,
            )
        )
    ).first()
    if row is None:
        raise NotFoundError("Unknown sales order.")
    order, customer_name, warehouse_name = row

    item_rows = await session.execute(
        select(SalesOrderItem, Product.name, Product.sku)
        .join(Product, Product.id == SalesOrderItem.product_id)
        .where(SalesOrderItem.sales_order_id == order.id)
        .order_by(SalesOrderItem.created_at)
    )
    return OrderDetail(
        **_to_order_item(order, customer_name, warehouse_name).model_dump(),
        subtotal=order.subtotal,
        tax_total=order.tax_total,
        items=[
            OrderItemOut(
                product_id=item.product_id,
                product_name=name,
                sku=sku,
                base_quantity=item.base_quantity,
                reserved_quantity=item.reserved_quantity,
                dispatched_quantity=item.dispatched_quantity,
                unit_price=item.unit_price,
                price_source=item.price_source,
                taxable_value=item.taxable_value,
                gst_rate=item.gst_rate,
                tax_amount=item.tax_amount,
                line_total=item.line_total,
            )
            for item, name, sku in item_rows.all()
        ],
    )


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
        branch_id=user.default_branch_id,
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
