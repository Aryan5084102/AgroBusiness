"""Retail POS endpoint. Finalized invoices are immutable (no update route)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import CurrentUser
from app.core.deps import db_session, require_permission
from app.core.exceptions import NotFoundError
from app.modules.catalogue.models import Product, Unit
from app.modules.customers.models import Customer
from app.modules.organizations.models import Warehouse
from app.modules.payments.models import Payment, PaymentAllocation, PaymentMethod
from app.modules.sales.models import (
    PaymentStatus,
    SaleChannel,
    SalesInvoice,
    SalesInvoiceItem,
)
from app.modules.sales.service import (
    PaymentInput,
    SaleLineInput,
    SalesService,
)
from app.modules.users.models import User

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


class QuoteRequest(BaseModel):
    warehouse_id: uuid.UUID
    lines: list[SaleLineBody] = Field(min_length=1)


class QuoteLineOut(BaseModel):
    product_id: uuid.UUID
    name: str
    quantity: Decimal
    unit_price: Decimal
    price_source: str
    net_amount: Decimal
    tax_amount: Decimal
    line_total: Decimal
    available_stock: Decimal


class QuoteResponse(BaseModel):
    lines: list[QuoteLineOut]
    subtotal: Decimal
    tax_total: Decimal
    grand_total: Decimal
    warnings: list[str]


class InvoiceListItem(BaseModel):
    id: uuid.UUID
    invoice_number: str
    invoice_date: date
    channel: SaleChannel
    customer_name: str | None
    warehouse_name: str
    grand_total: Decimal
    paid_amount: Decimal
    outstanding: Decimal
    payment_status: PaymentStatus
    created_by_name: str | None


class InvoicePage(BaseModel):
    items: list[InvoiceListItem]
    total: int
    limit: int
    offset: int
    total_value: Decimal


class InvoiceItemOut(BaseModel):
    product_id: uuid.UUID
    product_name: str
    sku: str
    hsn_code: str | None
    unit_code: str
    base_quantity: Decimal
    unit_price: Decimal
    price_source: str
    discount_amount: Decimal
    taxable_value: Decimal
    gst_rate: Decimal
    tax_amount: Decimal
    line_total: Decimal


class InvoicePaymentOut(BaseModel):
    method: PaymentMethod
    amount: Decimal
    reference: str | None


class InvoiceDetail(InvoiceListItem):
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    customer_id: uuid.UUID | None
    # Buyer details a printed tax invoice has to carry.
    customer_phone: str | None
    customer_gstin: str | None
    customer_address: str | None
    customer_village: str | None
    items: list[InvoiceItemOut]
    payments: list[InvoicePaymentOut]


@router.get("/invoices", response_model=InvoicePage)
async def list_invoices(
    channel: SaleChannel | None = Query(default=None),
    customer_id: uuid.UUID | None = Query(default=None),
    payment_status: PaymentStatus | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    search: str | None = Query(default=None, max_length=60),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_permission("sales.create")),
    session: AsyncSession = Depends(db_session),
) -> InvoicePage:
    """Invoice history, newest first. Finalized invoices are immutable."""
    base = (
        select(SalesInvoice, Customer.name, Warehouse.name, User.full_name)
        .outerjoin(Customer, Customer.id == SalesInvoice.customer_id)
        .join(Warehouse, Warehouse.id == SalesInvoice.warehouse_id)
        .outerjoin(User, User.id == SalesInvoice.created_by)
        .where(SalesInvoice.organization_id == user.organization_id)
    )
    if channel is not None:
        base = base.where(SalesInvoice.channel == channel)
    if customer_id is not None:
        base = base.where(SalesInvoice.customer_id == customer_id)
    if payment_status is not None:
        base = base.where(SalesInvoice.payment_status == payment_status)
    if date_from is not None:
        base = base.where(SalesInvoice.invoice_date >= date_from)
    if date_to is not None:
        base = base.where(SalesInvoice.invoice_date <= date_to)
    if search:
        base = base.where(SalesInvoice.invoice_number.ilike(f"%{search.strip()}%"))

    subquery = base.subquery()
    total = await session.scalar(select(func.count()).select_from(subquery))
    total_value = await session.scalar(select(func.coalesce(func.sum(subquery.c.grand_total), 0)))
    rows = await session.execute(
        base.order_by(SalesInvoice.invoice_date.desc(), SalesInvoice.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return InvoicePage(
        items=[
            _to_list_item(inv, customer_name, warehouse_name, actor)
            for inv, customer_name, warehouse_name, actor in rows.all()
        ],
        total=int(total or 0),
        limit=limit,
        offset=offset,
        total_value=Decimal(str(total_value or 0)),
    )


def _to_list_item(
    inv: SalesInvoice, customer_name: str | None, warehouse_name: str, actor: str | None
) -> InvoiceListItem:
    return InvoiceListItem(
        id=inv.id,
        invoice_number=inv.invoice_number,
        invoice_date=inv.invoice_date,
        channel=inv.channel,
        customer_name=customer_name,
        warehouse_name=warehouse_name,
        grand_total=inv.grand_total,
        paid_amount=inv.paid_amount,
        outstanding=inv.grand_total - inv.paid_amount,
        payment_status=inv.payment_status,
        created_by_name=actor,
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetail)
async def get_invoice(
    invoice_id: uuid.UUID,
    user: CurrentUser = Depends(require_permission("sales.create")),
    session: AsyncSession = Depends(db_session),
) -> InvoiceDetail:
    row = (
        await session.execute(
            select(
                SalesInvoice,
                Customer.name,
                Warehouse.name,
                User.full_name,
                Customer.phone,
                Customer.gstin,
                Customer.address,
                Customer.village,
            )
            .outerjoin(Customer, Customer.id == SalesInvoice.customer_id)
            .join(Warehouse, Warehouse.id == SalesInvoice.warehouse_id)
            .outerjoin(User, User.id == SalesInvoice.created_by)
            .where(
                SalesInvoice.id == invoice_id,
                SalesInvoice.organization_id == user.organization_id,
            )
        )
    ).first()
    if row is None:
        raise NotFoundError("Unknown invoice.")
    invoice, customer_name, warehouse_name, actor, phone, gstin, address, village = row

    # HSN and the selling unit come from the product; both are printed on the
    # tax invoice, so the detail payload carries them rather than making the
    # bill fetch every product separately.
    item_rows = await session.execute(
        select(SalesInvoiceItem, Product.name, Product.sku, Product.hsn_code, Unit.code)
        .join(Product, Product.id == SalesInvoiceItem.product_id)
        .join(Unit, Unit.id == Product.base_unit_id)
        .where(SalesInvoiceItem.sales_invoice_id == invoice.id)
        .order_by(SalesInvoiceItem.created_at)
    )
    payment_rows = await session.execute(
        select(Payment.method, PaymentAllocation.amount, Payment.reference)
        .join(PaymentAllocation, PaymentAllocation.payment_id == Payment.id)
        .where(PaymentAllocation.sales_invoice_id == invoice.id)
        .order_by(Payment.received_at)
    )
    return InvoiceDetail(
        **_to_list_item(invoice, customer_name, warehouse_name, actor).model_dump(),
        subtotal=invoice.subtotal,
        discount_total=invoice.discount_total,
        tax_total=invoice.tax_total,
        customer_id=invoice.customer_id,
        customer_phone=phone,
        customer_gstin=gstin,
        customer_address=address,
        customer_village=village,
        items=[
            InvoiceItemOut(
                product_id=item.product_id,
                product_name=name,
                sku=sku,
                hsn_code=hsn,
                unit_code=unit_code,
                base_quantity=item.base_quantity,
                unit_price=item.unit_price,
                price_source=item.price_source,
                discount_amount=item.discount_amount,
                taxable_value=item.taxable_value,
                gst_rate=item.gst_rate,
                tax_amount=item.tax_amount,
                line_total=item.line_total,
            )
            for item, name, sku, hsn, unit_code in item_rows.all()
        ],
        payments=[
            InvoicePaymentOut(method=method, amount=amount, reference=reference)
            for method, amount, reference in payment_rows.all()
        ],
    )


@router.post("/quote", response_model=QuoteResponse)
async def quote(
    payload: QuoteRequest,
    user: CurrentUser = Depends(require_permission("sales.create")),
    session: AsyncSession = Depends(db_session),
) -> QuoteResponse:
    result = await SalesService(session).quote(
        organization_id=user.organization_id,
        warehouse_id=payload.warehouse_id,
        lines=[
            SaleLineInput(
                product_id=ln.product_id,
                base_quantity=ln.base_quantity,
                discount_percent=ln.discount_percent,
            )
            for ln in payload.lines
        ],
        as_of=date.today(),
    )
    return QuoteResponse(
        lines=[QuoteLineOut(**ln.__dict__) for ln in result.lines],
        subtotal=result.subtotal,
        tax_total=result.tax_total,
        grand_total=result.grand_total,
        warnings=result.warnings,
    )


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
        branch_id=user.default_branch_id,
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
