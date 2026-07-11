"""Inventory models: batches, serials, the append-only stock ledger, balances.

``StockMovement`` is the authoritative, immutable record of every stock change.
``StockBalance`` is a fast projection (per product/warehouse/batch) rebuildable
from the ledger; it is never edited directly except through movement posting.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin
from app.core.database import Base


class MovementType(str, enum.Enum):
    """Every reason stock can move. ``direction`` gives the sign of the change."""

    OPENING = "opening"
    PURCHASE_RECEIPT = "purchase_receipt"
    RETAIL_SALE = "retail_sale"
    WHOLESALE_SALE = "wholesale_sale"
    SALES_RETURN = "sales_return"
    PURCHASE_RETURN = "purchase_return"
    TRANSFER_OUT = "transfer_out"
    TRANSFER_IN = "transfer_in"
    DAMAGE = "damage"
    EXPIRY = "expiry"
    ADJUSTMENT = "adjustment"
    REPAIR_CONSUMPTION = "repair_consumption"
    REPAIR_RETURN = "repair_return"
    RECONCILIATION = "reconciliation"


# Movement types that increase on-hand stock (+1) vs decrease it (-1).
INBOUND_TYPES = frozenset(
    {
        MovementType.OPENING,
        MovementType.PURCHASE_RECEIPT,
        MovementType.SALES_RETURN,
        MovementType.TRANSFER_IN,
        MovementType.REPAIR_RETURN,
    }
)
OUTBOUND_TYPES = frozenset(
    {
        MovementType.RETAIL_SALE,
        MovementType.WHOLESALE_SALE,
        MovementType.PURCHASE_RETURN,
        MovementType.TRANSFER_OUT,
        MovementType.DAMAGE,
        MovementType.EXPIRY,
        MovementType.REPAIR_CONSUMPTION,
    }
)


def movement_direction(movement_type: MovementType) -> int:
    """Return +1 for inbound, -1 for outbound, 0 for signed adjustments."""
    if movement_type in INBOUND_TYPES:
        return 1
    if movement_type in OUTBOUND_TYPES:
        return -1
    return 0  # ADJUSTMENT / RECONCILIATION carry an explicit signed quantity


class Batch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "batches"
    __table_args__ = (UniqueConstraint("product_id", "batch_number", name="uq_batch_number"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    batch_number: Mapped[str] = mapped_column(String(80), nullable=False)
    manufacture_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date, index=True)
    mrp: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))


class SerialNumber(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "serial_numbers"
    __table_args__ = (UniqueConstraint("product_id", "serial", name="uq_serial_per_product"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    serial: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="in_stock", nullable=False)


class StockMovement(UUIDPrimaryKeyMixin, Base):
    """Append-only ledger row. No soft delete, no updates: corrections are new rows."""

    __tablename__ = "stock_movements"
    __table_args__ = (CheckConstraint("base_quantity <> 0", name="ck_movement_nonzero"),)

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
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("batches.id", ondelete="RESTRICT")
    )
    serial_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("serial_numbers.id", ondelete="RESTRICT")
    )

    movement_type: Mapped[MovementType] = mapped_column(
        Enum(MovementType, name="stock_movement_type"), nullable=False
    )
    # Signed base-unit quantity: positive = in, negative = out.
    base_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)

    source_document_type: Mapped[str | None] = mapped_column(String(50))
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    reason: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class StockBalance(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    """Projection of on-hand + reserved base quantity per product/warehouse/batch."""

    __tablename__ = "stock_balances"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "product_id", "batch_id", name="uq_balance_scope"),
        CheckConstraint("on_hand >= 0", name="ck_balance_non_negative"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("batches.id", ondelete="RESTRICT")
    )
    on_hand: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=Decimal("0"), nullable=False)
    reserved: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=Decimal("0"), nullable=False)

    @property
    def available(self) -> Decimal:
        return self.on_hand - self.reserved
