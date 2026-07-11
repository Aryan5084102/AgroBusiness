"""Catalogue models: category, brand, unit, product and product-unit conversions.

The universal ``Product`` carries the common business fields as typed columns and
category-specific fields in a JSONB ``attributes`` map (metadata-based attribute
system) so seeds/pesticides/machines/spares extend without schema churn while the
important business fields stay strongly typed.
"""

from __future__ import annotations

import enum
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin
from app.core.database import Base


class ProductCategoryKind(str, enum.Enum):
    """Top-level product families that drive category-specific attributes/rules."""

    SEED = "seed"
    FERTILIZER = "fertilizer"
    PESTICIDE = "pesticide"
    INSECTICIDE = "insecticide"
    HERBICIDE = "herbicide"
    FUNGICIDE = "fungicide"
    MACHINE = "machine"
    SPARE_PART = "spare_part"
    TOOL = "tool"
    ACCESSORY = "accessory"


class Category(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_category_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    kind: Mapped[ProductCategoryKind] = mapped_column(
        Enum(ProductCategoryKind, name="product_category_kind"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL")
    )


class Brand(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "brands"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_brand_name"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(200))


class Unit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A unit of measure (piece, gram, ml, bottle, carton, bag, quintal...)."""

    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_unit_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)


class Product(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("organization_id", "sku", name="uq_product_sku"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL")
    )
    base_unit_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("units.id", ondelete="RESTRICT"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(250), nullable=False)
    local_name: Mapped[str | None] = mapped_column(String(250))
    sku: Mapped[str] = mapped_column(String(60), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(60), index=True)
    hsn_code: Mapped[str | None] = mapped_column(String(12))
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))

    mrp: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    retail_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    wholesale_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))

    # Inventory control flags.
    tracks_batches: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tracks_serials: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tracks_expiry: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_stock: Mapped[Decimal] = mapped_column(Numeric(16, 3), default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Category-specific fields (germination %, active ingredient, NPK, model no...).
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class ProductUnit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A purchasable/sellable packaging unit for a product and its base factor.

    ``base_factor`` = number of the product's base units contained in one of this
    unit (e.g. carton -> 20 bottles). Stock is always stored in base units.
    """

    __tablename__ = "product_units"
    __table_args__ = (UniqueConstraint("product_id", "unit_id", name="uq_product_unit"),)

    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("units.id", ondelete="RESTRICT"), nullable=False
    )
    base_factor: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False)
    is_purchase_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_sale_default: Mapped[bool] = mapped_column(Boolean, default=False)
