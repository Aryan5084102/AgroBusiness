"""Warranty and warranty-claim models (per serialized machine)."""

from __future__ import annotations

import enum
import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class WarrantyClaimStatus(str, enum.Enum):
    OPEN = "open"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLOSED = "closed"


class Warranty(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "warranties"

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
    serial_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("serial_numbers.id", ondelete="RESTRICT"),
        index=True,
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT")
    )
    sales_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sales_invoices.id", ondelete="SET NULL")
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)


class WarrantyClaim(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "warranty_claims"

    warranty_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("warranties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[WarrantyClaimStatus] = mapped_column(
        Enum(WarrantyClaimStatus, name="warranty_claim_status"),
        default=WarrantyClaimStatus.OPEN,
        nullable=False,
    )
