"""Customer model (walk-in, farmer, retail, dealer, ...)."""

from __future__ import annotations

import enum
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin
from app.core.database import Base


class CustomerType(str, enum.Enum):
    WALK_IN = "walk_in"
    FARMER = "farmer"
    RETAIL = "retail"
    RETAILER = "retailer"
    DEALER = "dealer"
    DISTRIBUTOR = "distributor"
    INSTITUTION = "institution"


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_customer_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_type: Mapped[CustomerType] = mapped_column(
        Enum(CustomerType, name="customer_type"),
        default=CustomerType.RETAIL,
        nullable=False,
    )
    phone: Mapped[str | None] = mapped_column(String(20), index=True)
    gstin: Mapped[str | None] = mapped_column(String(20))
    # Postal address for the tax invoice's "billed to" block. `village` stays
    # alongside it as the short local identifier the counter recognises.
    address: Mapped[str | None] = mapped_column(String(400))
    village: Mapped[str | None] = mapped_column(String(120))
    credit_limit: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), default=Decimal("0"), nullable=False
    )
    credit_period_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), default=Decimal("0"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
