"""Reporting service — read-only aggregations for the dashboard and registers.

All queries are tenant-scoped by ``organization_id``. Monetary sums come back as
Decimal. Profit reporting is gated by a separate permission at the API layer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.money import Money
from app.modules.catalogue.models import Product
from app.modules.customers.models import Customer
from app.modules.inventory.models import StockBalance
from app.modules.payments.models import Payment, PaymentDirection
from app.modules.purchases.models import GoodsReceipt, GoodsReceiptItem
from app.modules.sales.models import (
    PaymentStatus,
    SaleChannel,
    SalesInvoice,
    SalesInvoiceItem,
)
from app.modules.suppliers.models import Supplier


@dataclass
class DashboardSummary:
    as_of: date
    sales_today_total: Decimal
    retail_today_total: Decimal
    wholesale_today_total: Decimal
    collected_today_total: Decimal
    receivables_outstanding: Decimal
    low_stock_product_count: int


@dataclass
class GstBucket:
    gst_rate: Decimal
    taxable_value: Decimal
    tax_amount: Decimal


@dataclass
class GstSummary:
    buckets: list[GstBucket] = field(default_factory=list)
    total_taxable: Decimal = Decimal("0.00")
    total_tax: Decimal = Decimal("0.00")


@dataclass
class RegisterRow:
    """One line of a sales or purchase register (shared shape for CSV export)."""

    entry_date: date
    document_number: str
    party: str
    category: str
    taxable_value: Decimal
    tax_amount: Decimal
    total: Decimal
    settled: Decimal
    status: str


@dataclass
class StockValuationRow:
    product_id: uuid.UUID
    product_name: str
    sku: str
    on_hand: Decimal
    min_stock: Decimal
    retail_price: Decimal
    stock_value: Decimal
    is_low: bool


@dataclass
class TopProductRow:
    product_id: uuid.UUID
    product_name: str
    sku: str
    quantity_sold: Decimal
    revenue: Decimal


@dataclass
class TrendPoint:
    day: date
    revenue: Decimal
    invoice_count: int


class ReportsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def dashboard(self, *, organization_id: uuid.UUID, as_of: date) -> DashboardSummary:
        sales_today = await self._sales_total_by_channel(organization_id, as_of)
        collected = await self._collected_today(organization_id, as_of)
        receivables = await self._receivables(organization_id)
        low_stock = await self._low_stock_count(organization_id)
        return DashboardSummary(
            as_of=as_of,
            sales_today_total=Money(
                sales_today.get(SaleChannel.RETAIL, Decimal("0"))
                + sales_today.get(SaleChannel.WHOLESALE, Decimal("0"))
            ),
            retail_today_total=Money(sales_today.get(SaleChannel.RETAIL, Decimal("0"))),
            wholesale_today_total=Money(sales_today.get(SaleChannel.WHOLESALE, Decimal("0"))),
            collected_today_total=collected,
            receivables_outstanding=receivables,
            low_stock_product_count=low_stock,
        )

    async def gst_summary(
        self, *, organization_id: uuid.UUID, date_from: date, date_to: date
    ) -> GstSummary:
        stmt = (
            select(
                SalesInvoiceItem.gst_rate,
                func.coalesce(func.sum(SalesInvoiceItem.taxable_value), 0),
                func.coalesce(func.sum(SalesInvoiceItem.tax_amount), 0),
            )
            .join(SalesInvoice, SalesInvoice.id == SalesInvoiceItem.sales_invoice_id)
            .where(
                SalesInvoice.organization_id == organization_id,
                SalesInvoice.invoice_date >= date_from,
                SalesInvoice.invoice_date <= date_to,
            )
            .group_by(SalesInvoiceItem.gst_rate)
            .order_by(SalesInvoiceItem.gst_rate)
        )
        rows = await self._session.execute(stmt)
        summary = GstSummary()
        for rate, taxable, tax in rows.all():
            bucket = GstBucket(
                gst_rate=Decimal(str(rate)),
                taxable_value=Money(Decimal(str(taxable))),
                tax_amount=Money(Decimal(str(tax))),
            )
            summary.buckets.append(bucket)
            summary.total_taxable = Money(summary.total_taxable + bucket.taxable_value)
            summary.total_tax = Money(summary.total_tax + bucket.tax_amount)
        return summary

    async def sales_register(
        self,
        *,
        organization_id: uuid.UUID,
        date_from: date,
        date_to: date,
        channel: SaleChannel | None = None,
        limit: int = 500,
    ) -> list[RegisterRow]:
        """Invoice-level sales register for a date range."""
        stmt = (
            select(
                SalesInvoice.invoice_date,
                SalesInvoice.invoice_number,
                func.coalesce(Customer.name, "Walk-in"),
                SalesInvoice.channel,
                SalesInvoice.subtotal,
                SalesInvoice.tax_total,
                SalesInvoice.grand_total,
                SalesInvoice.paid_amount,
                SalesInvoice.payment_status,
            )
            .outerjoin(Customer, Customer.id == SalesInvoice.customer_id)
            .where(
                SalesInvoice.organization_id == organization_id,
                SalesInvoice.invoice_date >= date_from,
                SalesInvoice.invoice_date <= date_to,
            )
            .order_by(SalesInvoice.invoice_date.desc(), SalesInvoice.invoice_number.desc())
            .limit(limit)
        )
        if channel is not None:
            stmt = stmt.where(SalesInvoice.channel == channel)
        rows = await self._session.execute(stmt)
        return [
            RegisterRow(
                entry_date=entry_date,
                document_number=number,
                party=party,
                category=chan.value,
                taxable_value=Money(subtotal),
                tax_amount=Money(tax),
                total=Money(total),
                settled=Money(paid),
                status=status.value,
            )
            for entry_date, number, party, chan, subtotal, tax, total, paid, status in rows.all()
        ]

    async def purchase_register(
        self,
        *,
        organization_id: uuid.UUID,
        date_from: date,
        date_to: date,
        limit: int = 500,
    ) -> list[RegisterRow]:
        """Goods-receipt level purchase register for a date range."""
        value = func.coalesce(
            func.sum(GoodsReceiptItem.received_base_quantity * GoodsReceiptItem.unit_rate), 0
        )
        stmt = (
            select(
                GoodsReceipt.receipt_date,
                GoodsReceipt.grn_number,
                Supplier.name,
                func.count(GoodsReceiptItem.id),
                value,
            )
            .join(Supplier, Supplier.id == GoodsReceipt.supplier_id)
            .outerjoin(GoodsReceiptItem, GoodsReceiptItem.goods_receipt_id == GoodsReceipt.id)
            .where(
                GoodsReceipt.organization_id == organization_id,
                GoodsReceipt.receipt_date >= date_from,
                GoodsReceipt.receipt_date <= date_to,
            )
            .group_by(
                GoodsReceipt.id, GoodsReceipt.receipt_date, GoodsReceipt.grn_number, Supplier.name
            )
            .order_by(GoodsReceipt.receipt_date.desc())
            .limit(limit)
        )
        rows = await self._session.execute(stmt)
        return [
            RegisterRow(
                entry_date=entry_date,
                document_number=number,
                party=supplier,
                category=f"{int(line_count)} lines",
                taxable_value=Money(Decimal(str(total))),
                tax_amount=Decimal("0.00"),
                total=Money(Decimal(str(total))),
                settled=Decimal("0.00"),
                status="received",
            )
            for entry_date, number, supplier, line_count, total in rows.all()
        ]

    async def stock_valuation(
        self, *, organization_id: uuid.UUID, limit: int = 500
    ) -> list[StockValuationRow]:
        """On-hand quantity and its retail value per product."""
        stmt = (
            select(
                Product.id,
                Product.name,
                Product.sku,
                Product.min_stock,
                Product.retail_price,
                func.coalesce(func.sum(StockBalance.on_hand), 0),
            )
            .outerjoin(
                StockBalance,
                (StockBalance.product_id == Product.id)
                & (StockBalance.organization_id == organization_id),
            )
            .where(Product.organization_id == organization_id, Product.is_active.is_(True))
            .group_by(
                Product.id, Product.name, Product.sku, Product.min_stock, Product.retail_price
            )
            .order_by(Product.name)
            .limit(limit)
        )
        rows = await self._session.execute(stmt)
        return [
            StockValuationRow(
                product_id=pid,
                product_name=name,
                sku=sku,
                on_hand=Decimal(str(on_hand)),
                min_stock=min_stock,
                retail_price=price,
                stock_value=Money(Decimal(str(on_hand)) * price),
                is_low=min_stock > 0 and Decimal(str(on_hand)) < min_stock,
            )
            for pid, name, sku, min_stock, price, on_hand in rows.all()
        ]

    async def top_products(
        self, *, organization_id: uuid.UUID, date_from: date, date_to: date, limit: int = 10
    ) -> list[TopProductRow]:
        """Best sellers by revenue over a date range."""
        stmt = (
            select(
                Product.id,
                Product.name,
                Product.sku,
                func.coalesce(func.sum(SalesInvoiceItem.base_quantity), 0),
                func.coalesce(func.sum(SalesInvoiceItem.line_total), 0),
            )
            .join(SalesInvoiceItem, SalesInvoiceItem.product_id == Product.id)
            .join(SalesInvoice, SalesInvoice.id == SalesInvoiceItem.sales_invoice_id)
            .where(
                SalesInvoice.organization_id == organization_id,
                SalesInvoice.invoice_date >= date_from,
                SalesInvoice.invoice_date <= date_to,
            )
            .group_by(Product.id, Product.name, Product.sku)
            .order_by(func.sum(SalesInvoiceItem.line_total).desc())
            .limit(limit)
        )
        rows = await self._session.execute(stmt)
        return [
            TopProductRow(
                product_id=pid,
                product_name=name,
                sku=sku,
                quantity_sold=Decimal(str(qty)),
                revenue=Money(Decimal(str(revenue))),
            )
            for pid, name, sku, qty, revenue in rows.all()
        ]

    async def sales_trend(
        self, *, organization_id: uuid.UUID, date_from: date, date_to: date
    ) -> list[TrendPoint]:
        """Daily revenue and invoice count, oldest first (for the dashboard chart)."""
        stmt = (
            select(
                SalesInvoice.invoice_date,
                func.coalesce(func.sum(SalesInvoice.grand_total), 0),
                func.count(SalesInvoice.id),
            )
            .where(
                SalesInvoice.organization_id == organization_id,
                SalesInvoice.invoice_date >= date_from,
                SalesInvoice.invoice_date <= date_to,
            )
            .group_by(SalesInvoice.invoice_date)
            .order_by(SalesInvoice.invoice_date)
        )
        rows = await self._session.execute(stmt)
        return [
            TrendPoint(day=day, revenue=Money(Decimal(str(revenue))), invoice_count=int(count))
            for day, revenue, count in rows.all()
        ]

    async def _sales_total_by_channel(
        self, organization_id: uuid.UUID, as_of: date
    ) -> dict[SaleChannel, Decimal]:
        stmt = (
            select(
                SalesInvoice.channel,
                func.coalesce(func.sum(SalesInvoice.grand_total), 0),
            )
            .where(
                SalesInvoice.organization_id == organization_id,
                SalesInvoice.invoice_date == as_of,
            )
            .group_by(SalesInvoice.channel)
        )
        rows = await self._session.execute(stmt)
        return {channel: Decimal(str(total)) for channel, total in rows.all()}

    async def _collected_today(self, organization_id: uuid.UUID, as_of: date) -> Decimal:
        stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.organization_id == organization_id,
            Payment.direction == PaymentDirection.INBOUND,
            func.date(Payment.received_at) == as_of,
        )
        return Money(Decimal(str((await self._session.execute(stmt)).scalar())))

    async def _receivables(self, organization_id: uuid.UUID) -> Decimal:
        stmt = select(
            func.coalesce(func.sum(SalesInvoice.grand_total - SalesInvoice.paid_amount), 0)
        ).where(
            SalesInvoice.organization_id == organization_id,
            SalesInvoice.payment_status != PaymentStatus.PAID,
        )
        return Money(Decimal(str((await self._session.execute(stmt)).scalar())))

    async def _low_stock_count(self, organization_id: uuid.UUID) -> int:
        # Products whose total on-hand is below their configured minimum.
        on_hand = (
            select(
                StockBalance.product_id,
                func.sum(StockBalance.on_hand).label("total_on_hand"),
            )
            .where(StockBalance.organization_id == organization_id)
            .group_by(StockBalance.product_id)
            .subquery()
        )
        stmt = (
            select(func.count())
            .select_from(Product)
            .outerjoin(on_hand, on_hand.c.product_id == Product.id)
            .where(
                Product.organization_id == organization_id,
                Product.is_active.is_(True),
                Product.min_stock > 0,
                func.coalesce(on_hand.c.total_on_hand, 0) < Product.min_stock,
            )
        )
        return int((await self._session.execute(stmt)).scalar() or 0)
