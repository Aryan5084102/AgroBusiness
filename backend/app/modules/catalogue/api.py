"""Catalogue endpoints: list/search/create products (tenant-scoped, RBAC)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import CurrentUser
from app.core.deps import db_session, get_current_user, require_permission
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductCategoryKind,
    Unit,
)
from app.modules.inventory.models import StockBalance

router = APIRouter(tags=["products"])


class ProductOut(BaseModel):
    id: uuid.UUID
    name: str
    sku: str
    barcode: str | None
    category_id: uuid.UUID
    category_name: str | None
    base_unit_id: uuid.UUID
    unit_code: str | None
    hsn_code: str | None
    retail_price: Decimal
    wholesale_price: Decimal
    mrp: Decimal
    gst_rate: Decimal
    min_stock: Decimal
    on_hand: Decimal
    tracks_batches: bool
    tracks_expiry: bool
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
    barcode: str | None = Field(default=None, max_length=60)
    hsn_code: str | None = Field(default=None, max_length=12)
    retail_price: Decimal = Field(default=Decimal("0"), ge=0)
    wholesale_price: Decimal = Field(default=Decimal("0"), ge=0)
    mrp: Decimal = Field(default=Decimal("0"), ge=0)
    gst_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    min_stock: Decimal = Field(default=Decimal("0"), ge=0)
    tracks_batches: bool = False
    tracks_expiry: bool = False


class UpdateProductRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=250)
    barcode: str | None = Field(default=None, max_length=60)
    hsn_code: str | None = Field(default=None, max_length=12)
    retail_price: Decimal | None = Field(default=None, ge=0)
    wholesale_price: Decimal | None = Field(default=None, ge=0)
    mrp: Decimal | None = Field(default=None, ge=0)
    gst_rate: Decimal | None = Field(default=None, ge=0, le=100)
    min_stock: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class CategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    kind: ProductCategoryKind


class UnitOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str


def _to_out(
    p: Product,
    category_name: str | None = None,
    unit_code: str | None = None,
    on_hand: Decimal = Decimal("0"),
) -> ProductOut:
    return ProductOut(
        id=p.id,
        name=p.name,
        sku=p.sku,
        barcode=p.barcode,
        category_id=p.category_id,
        category_name=category_name,
        base_unit_id=p.base_unit_id,
        unit_code=unit_code,
        hsn_code=p.hsn_code,
        retail_price=p.retail_price,
        wholesale_price=p.wholesale_price,
        mrp=p.mrp,
        gst_rate=p.gst_rate,
        min_stock=p.min_stock,
        on_hand=on_hand,
        tracks_batches=p.tracks_batches,
        tracks_expiry=p.tracks_expiry,
        is_active=p.is_active,
    )


@router.get("", response_model=ProductPage)
async def list_products(
    search: str | None = Query(default=None, max_length=100),
    category_id: uuid.UUID | None = Query(default=None),
    active_only: bool = Query(default=False),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_permission("product.view")),
    session: AsyncSession = Depends(db_session),
) -> ProductPage:
    stock = (
        select(
            StockBalance.product_id.label("pid"),
            func.sum(StockBalance.on_hand).label("on_hand"),
        )
        .where(StockBalance.organization_id == user.organization_id)
        .group_by(StockBalance.product_id)
        .subquery()
    )
    base = (
        select(Product, Category.name, Unit.code, func.coalesce(stock.c.on_hand, 0))
        .outerjoin(Category, Category.id == Product.category_id)
        .outerjoin(Unit, Unit.id == Product.base_unit_id)
        .outerjoin(stock, stock.c.pid == Product.id)
        .where(Product.organization_id == user.organization_id)
    )
    if search:
        pattern = f"%{search.strip()}%"
        base = base.where(
            or_(
                Product.name.ilike(pattern),
                Product.sku.ilike(pattern),
                Product.barcode.ilike(pattern),
            )
        )
    if category_id is not None:
        base = base.where(Product.category_id == category_id)
    if active_only:
        base = base.where(Product.is_active.is_(True))

    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    rows = await session.execute(base.order_by(Product.name).limit(limit).offset(offset))
    return ProductPage(
        items=[
            _to_out(p, category_name, unit_code, Decimal(str(on_hand)))
            for p, category_name, unit_code, on_hand in rows.all()
        ],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    user: CurrentUser = Depends(require_permission("product.view")),
    session: AsyncSession = Depends(db_session),
) -> list[CategoryOut]:
    rows = await session.execute(
        select(Category)
        .where(Category.organization_id == user.organization_id)
        .order_by(Category.name)
    )
    return [
        CategoryOut(id=c.id, name=c.name, code=c.code, kind=c.kind) for c in rows.scalars().all()
    ]


@router.get("/units", response_model=list[UnitOut])
async def list_units(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> list[UnitOut]:
    rows = await session.execute(
        select(Unit).where(Unit.organization_id == user.organization_id).order_by(Unit.name)
    )
    return [UnitOut(id=u.id, code=u.code, name=u.name) for u in rows.scalars().all()]


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: uuid.UUID,
    user: CurrentUser = Depends(require_permission("product.view")),
    session: AsyncSession = Depends(db_session),
) -> ProductOut:
    row = (
        await session.execute(
            select(Product, Category.name, Unit.code)
            .outerjoin(Category, Category.id == Product.category_id)
            .outerjoin(Unit, Unit.id == Product.base_unit_id)
            .where(
                Product.id == product_id,
                Product.organization_id == user.organization_id,
            )
        )
    ).first()
    if row is None:
        raise NotFoundError("Unknown product.")
    product, category_name, unit_code = row
    on_hand = await session.scalar(
        select(func.coalesce(func.sum(StockBalance.on_hand), 0)).where(
            StockBalance.product_id == product_id
        )
    )
    return _to_out(product, category_name, unit_code, Decimal(str(on_hand or 0)))


@router.post("", response_model=ProductOut, status_code=201)
async def create_product(
    payload: CreateProductRequest,
    user: CurrentUser = Depends(require_permission("product.create")),
    session: AsyncSession = Depends(db_session),
) -> ProductOut:
    duplicate = await session.scalar(
        select(func.count())
        .select_from(Product)
        .where(
            Product.organization_id == user.organization_id,
            Product.sku == payload.sku,
        )
    )
    if duplicate:
        raise ConflictError(f"A product with SKU {payload.sku} already exists.")
    product = Product(
        organization_id=user.organization_id,
        category_id=payload.category_id,
        base_unit_id=payload.base_unit_id,
        name=payload.name,
        sku=payload.sku,
        barcode=payload.barcode,
        hsn_code=payload.hsn_code,
        retail_price=payload.retail_price,
        wholesale_price=payload.wholesale_price,
        mrp=payload.mrp,
        gst_rate=payload.gst_rate,
        min_stock=payload.min_stock,
        tracks_batches=payload.tracks_batches,
        tracks_expiry=payload.tracks_expiry,
    )
    session.add(product)
    await session.commit()
    # The session keeps objects alive after commit (expire_on_commit=False),
    # so refresh to return exactly what the database stored — NUMERIC columns
    # normalise scale, and a client sending "7500" must read back "7500.00".
    await session.refresh(product)
    return _to_out(product)


@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: uuid.UUID,
    payload: UpdateProductRequest,
    user: CurrentUser = Depends(require_permission("product.update")),
    session: AsyncSession = Depends(db_session),
) -> ProductOut:
    """Edit catalogue fields. Prices here only affect future sales — finalized
    invoices keep their own pricing snapshot."""
    product = await session.get(Product, product_id)
    if product is None or product.organization_id != user.organization_id:
        raise NotFoundError("Unknown product.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    await session.commit()
    await session.refresh(product)
    return _to_out(product)
