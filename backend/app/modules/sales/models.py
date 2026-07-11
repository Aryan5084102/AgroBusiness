"""Sales models: retail/wholesale invoices with a per-line pricing snapshot.

A finalized invoice is immutable: there is no update path. Each line stores the
resolved price and its source at sale time so historical invoices never change
when price lists are later edited. Corrections use returns/credit notes.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Date,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin
from app.core.database import Base


class SaleChannel(str, enum.Enum):
    RETAIL = "retail"
    WHOLESALE = "wholesale"


class PaymentStatus(str, enum.Enum):
    PAID = "paid"
    PARTIAL = "partial"
    CREDIT = "credit"


class SalesInvoice(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "sales_invoices"
    __table_args__ = (
        UniqueConstraint("organization_id", "invoice_number", name="uq_sales_invoice_no"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT")
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    invoice_number: Mapped[str] = mapped_column(String(40), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    channel: Mapped[SaleChannel] = mapped_column(
        Enum(SaleChannel, name="sale_channel"), default=SaleChannel.RETAIL, nullable=False
    )

    subtotal: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    discount_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    grand_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="sales_payment_status"),
        default=PaymentStatus.CREDIT,
        nullable=False,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class SalesInvoiceItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable priced line. ``price_source`` records how the price was resolved."""

    __tablename__ = "sales_invoice_items"

    sales_invoice_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sales_invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("batches.id", ondelete="RESTRICT")
    )
    base_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    price_source: Mapped[str] = mapped_column(String(30), nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    taxable_value: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    line_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
