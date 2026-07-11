"""Purchase models: purchase order, goods receipt, purchase invoice + items.

Flow: PurchaseOrder -> GoodsReceipt (posts stock movements) -> PurchaseInvoice.
Purchase invoices carry a unique (supplier, invoice_number) constraint so the
same supplier bill cannot be booked twice (duplicate-invoice detection).
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


class PurchaseOrderStatus(str, enum.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class PurchaseOrder(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (UniqueConstraint("organization_id", "po_number", name="uq_po_number"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT")
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    po_number: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        Enum(PurchaseOrderStatus, name="purchase_order_status"),
        default=PurchaseOrderStatus.DRAFT,
        nullable=False,
    )
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_date: Mapped[date | None] = mapped_column(Date)
    freight: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    loading: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    other_charges: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(String(500))


class PurchaseOrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "purchase_order_items"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Ordered quantity in base units.
    ordered_base_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    received_base_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), default=Decimal("0"), nullable=False
    )
    unit_rate: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    trade_discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))


class GoodsReceipt(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "goods_receipts"
    __table_args__ = (UniqueConstraint("organization_id", "grn_number", name="uq_grn_number"),)

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
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="SET NULL")
    )
    grn_number: Mapped[str] = mapped_column(String(40), nullable=False)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)


class GoodsReceiptItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "goods_receipt_items"

    goods_receipt_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("goods_receipts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("batches.id", ondelete="RESTRICT")
    )
    stock_movement_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("stock_movements.id", ondelete="RESTRICT")
    )
    received_base_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    free_base_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), default=Decimal("0"), nullable=False
    )
    unit_rate: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    landed_unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("0"))


class PurchaseInvoice(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "purchase_invoices"
    __table_args__ = (
        # Duplicate supplier-invoice detection.
        UniqueConstraint(
            "organization_id",
            "supplier_id",
            "supplier_invoice_number",
            name="uq_supplier_invoice",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    goods_receipt_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("goods_receipts.id", ondelete="SET NULL")
    )
    supplier_invoice_number: Mapped[str] = mapped_column(String(60), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    goods_value: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
