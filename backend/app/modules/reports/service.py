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
from app.modules.inventory.models import StockBalance
from app.modules.payments.models import Payment, PaymentDirection
from app.modules.sales.models import (
    PaymentStatus,
    SaleChannel,
    SalesInvoice,
    SalesInvoiceItem,
)


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
