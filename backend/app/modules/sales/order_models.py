"""Wholesale sales order + items (quotation → order → dispatch → invoice)."""

from __future__ import annotations

import enum
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin
from app.core.database import Base


class SalesOrderStatus(str, enum.Enum):
    QUOTATION = "quotation"
    CONFIRMED = "confirmed"
    PARTIALLY_DISPATCHED = "partially_dispatched"
    DISPATCHED = "dispatched"
    INVOICED = "invoiced"
    CANCELLED = "cancelled"


class SalesOrder(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "sales_orders"
    __table_args__ = (
        UniqueConstraint("organization_id", "order_number", name="uq_sales_order_no"),
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
    customer_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    salesperson_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    order_number: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[SalesOrderStatus] = mapped_column(
        Enum(SalesOrderStatus, name="sales_order_status"),
        default=SalesOrderStatus.CONFIRMED,
        nullable=False,
    )
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    grand_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    credit_override_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sales_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sales_invoices.id", ondelete="SET NULL")
    )


class SalesOrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sales_order_items"

    sales_order_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sales_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    base_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    reserved_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), default=Decimal("0"), nullable=False
    )
    dispatched_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), default=Decimal("0"), nullable=False
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    price_source: Mapped[str] = mapped_column(String(30), nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    taxable_value: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    line_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
