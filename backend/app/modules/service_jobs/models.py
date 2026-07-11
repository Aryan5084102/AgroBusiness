"""Repair job + consumed-parts models."""

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


class RepairStatus(str, enum.Enum):
    RECEIVED = "received"
    UNDER_INSPECTION = "under_inspection"
    ESTIMATE_PREPARED = "estimate_prepared"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_PART = "waiting_for_part"
    QUALITY_CHECK = "quality_check"
    READY = "ready"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class RepairJob(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "repair_jobs"
    __table_args__ = (
        UniqueConstraint("organization_id", "job_number", name="uq_repair_job_number"),
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
    job_number: Mapped[str] = mapped_column(String(40), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT")
    )
    serial_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("serial_numbers.id", ondelete="RESTRICT")
    )
    warranty_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("warranties.id", ondelete="SET NULL")
    )
    technician_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    complaint: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[RepairStatus] = mapped_column(
        Enum(RepairStatus, name="repair_status"),
        default=RepairStatus.RECEIVED,
        nullable=False,
    )
    is_warranty_covered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    labour_charges: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    parts_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    customer_payable: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    completed_date: Mapped[date | None] = mapped_column(Date)


class RepairJobPart(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "repair_job_parts"

    repair_job_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("repair_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    base_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    consumption_movement_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("stock_movements.id", ondelete="RESTRICT")
    )
    return_movement_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("stock_movements.id", ondelete="RESTRICT")
    )
    is_returned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
