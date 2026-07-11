"""Catalogue endpoints: list/search/create products (tenant-scoped, RBAC)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import CurrentUser
from app.core.deps import db_session, require_permission
from app.modules.catalogue.models import Product

router = APIRouter(tags=["products"])


class ProductOut(BaseModel):
    id: uuid.UUID
    name: str
    sku: str
    barcode: str | None
    retail_price: Decimal
    wholesale_price: Decimal
    mrp: Decimal
    gst_rate: Decimal
    tracks_batches: bool
    is_active: bool


class ProductPage(BaseModel):
    items: list[ProductOut]
    total: int
    limit: int
    offset: int


class CreateProductRequest(BaseModel):
    name: str = Field(min_length=1, max_length=250)
    sku: str = Field(min_length=1, max_length=60)
    category_id: uuid.UUID
    base_unit_id: uuid.UUID
    retail_price: Decimal = Field(default=Decimal("0"), ge=0)
    wholesale_price: Decimal = Field(default=Decimal("0"), ge=0)
    mrp: Decimal = Field(default=Decimal("0"), ge=0)
    gst_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    tracks_batches: bool = False
    tracks_expiry: bool = False


def _to_out(p: Product) -> ProductOut:
    return ProductOut(
        id=p.id,
        name=p.name,
        sku=p.sku,
        barcode=p.barcode,
        retail_price=p.retail_price,
        wholesale_price=p.wholesale_price,
        mrp=p.mrp,
        gst_rate=p.gst_rate,
        tracks_batches=p.tracks_batches,
        is_active=p.is_active,
    )


@router.get("", response_model=ProductPage)
async def list_products(
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_permission("product.view")),
    session: AsyncSession = Depends(db_session),
) -> ProductPage:
    base = select(Product).where(Product.organization_id == user.organization_id)
    if search:
        pattern = f"%{search.strip()}%"
        base = base.where(
            or_(
                Product.name.ilike(pattern),
                Product.sku.ilike(pattern),
                Product.barcode.ilike(pattern),
            )
        )

    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    rows = await session.execute(base.order_by(Product.name).limit(limit).offset(offset))
    return ProductPage(
        items=[_to_out(p) for p in rows.scalars().all()],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ProductOut, status_code=201)
async def create_product(
    payload: CreateProductRequest,
    user: CurrentUser = Depends(require_permission("product.create")),
    session: AsyncSession = Depends(db_session),
) -> ProductOut:
    product = Product(
        organization_id=user.organization_id,
        category_id=payload.category_id,
        base_unit_id=payload.base_unit_id,
        name=payload.name,
        sku=payload.sku,
        retail_price=payload.retail_price,
        wholesale_price=payload.wholesale_price,
        mrp=payload.mrp,
        gst_rate=payload.gst_rate,
        tracks_batches=payload.tracks_batches,
        tracks_expiry=payload.tracks_expiry,
    )
    session.add(product)
    await session.commit()
    return _to_out(product)
