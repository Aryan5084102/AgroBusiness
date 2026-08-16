"""Inventory endpoints: stock levels, ledger, batches, adjustments, transfers.

Reads are gated by ``inventory.view``; adjustments by ``inventory.adjust`` and
transfers by ``stock.transfer``. Every mutation goes through
:class:`~app.modules.inventory.service.InventoryService` so the append-only
stock ledger stays the single source of truth.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.context import CurrentUser
from app.core.deps import db_session, require_permission
from app.core.exceptions import BusinessRuleError
from app.modules.catalogue.models import Product, Unit
from app.modules.inventory.models import (
    Batch,
    MovementType,
    StockBalance,
    StockMovement,
)
from app.modules.inventory.service import InventoryService
from app.modules.organizations.models import Warehouse
from app.modules.users.models import User

router = APIRouter(tags=["inventory"])


# --- Stock levels -----------------------------------------------------------
class StockRowOut(BaseModel):
    product_id: uuid.UUID
    product_name: str
    sku: str
    unit_code: str
    warehouse_id: uuid.UUID
    warehouse_name: str
    on_hand: Decimal
    reserved: Decimal
    available: Decimal
    min_stock: Decimal
    is_low: bool


class StockPage(BaseModel):
    items: list[StockRowOut]
    total: int
    limit: int
    offset: int


@router.get("/stock", response_model=StockPage)
async def list_stock(
    warehouse_id: uuid.UUID | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    low_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_permission("inventory.view")),
    session: AsyncSession = Depends(db_session),
) -> StockPage:
    """Stock per product and warehouse (batches summed into one row)."""
    on_hand = func.coalesce(func.sum(StockBalance.on_hand), 0)
    reserved = func.coalesce(func.sum(StockBalance.reserved), 0)

    filters: list[ColumnElement[bool]] = [StockBalance.organization_id == user.organization_id]
    if warehouse_id is not None:
        filters.append(StockBalance.warehouse_id == warehouse_id)
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))

    base = (
        select(
            Product.id,
            Product.name,
            Product.sku,
            Product.min_stock,
            Unit.code,
            Warehouse.id,
            Warehouse.name,
            on_hand.label("on_hand"),
            reserved.label("reserved"),
        )
        .join(Product, Product.id == StockBalance.product_id)
        .join(Unit, Unit.id == Product.base_unit_id)
        .join(Warehouse, Warehouse.id == StockBalance.warehouse_id)
        .where(*filters)
        .group_by(Product.id, Product.name, Product.sku, Product.min_stock, Unit.code, Warehouse.id)
    )
    # "Low" compares the aggregate against the product minimum, so it belongs in HAVING.
    if low_only:
        base = base.having(on_hand < Product.min_stock)

    rows = await session.execute(
        base.order_by(Product.name, Warehouse.name).limit(limit).offset(offset)
    )
    total = await session.scalar(select(func.count()).select_from(base.subquery()))

    items: list[StockRowOut] = []
    for pid, pname, sku, min_stock, unit_code, wid, wname, oh, rsv in rows.all():
        on_hand_dec = Decimal(str(oh))
        reserved_dec = Decimal(str(rsv))
        items.append(
            StockRowOut(
                product_id=pid,
                product_name=pname,
                sku=sku,
                unit_code=unit_code,
                warehouse_id=wid,
                warehouse_name=wname,
                on_hand=on_hand_dec,
                reserved=reserved_dec,
                available=on_hand_dec - reserved_dec,
                min_stock=min_stock,
                is_low=min_stock > 0 and on_hand_dec < min_stock,
            )
        )
    return StockPage(items=items, total=int(total or 0), limit=limit, offset=offset)


# --- Ledger -----------------------------------------------------------------
class MovementOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    movement_type: MovementType
    product_id: uuid.UUID
    product_name: str
    sku: str
    warehouse_id: uuid.UUID
    warehouse_name: str
    base_quantity: Decimal
    batch_number: str | None
    reason: str | None
    source_document_type: str | None
    actor_name: str | None


class MovementPage(BaseModel):
    items: list[MovementOut]
    total: int
    limit: int
    offset: int


@router.get("/movements", response_model=MovementPage)
async def list_movements(
    product_id: uuid.UUID | None = Query(default=None),
    warehouse_id: uuid.UUID | None = Query(default=None),
    movement_type: MovementType | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_permission("inventory.view")),
    session: AsyncSession = Depends(db_session),
) -> MovementPage:
    """The append-only stock ledger, newest first."""
    base = (
        select(
            StockMovement,
            Product.name,
            Product.sku,
            Warehouse.name,
            Batch.batch_number,
            User.full_name,
        )
        .join(Product, Product.id == StockMovement.product_id)
        .join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
        .outerjoin(Batch, Batch.id == StockMovement.batch_id)
        .outerjoin(User, User.id == StockMovement.created_by)
        .where(StockMovement.organization_id == user.organization_id)
    )
    if product_id is not None:
        base = base.where(StockMovement.product_id == product_id)
    if warehouse_id is not None:
        base = base.where(StockMovement.warehouse_id == warehouse_id)
    if movement_type is not None:
        base = base.where(StockMovement.movement_type == movement_type)
    if date_from is not None:
        base = base.where(func.date(StockMovement.created_at) >= date_from)
    if date_to is not None:
        base = base.where(func.date(StockMovement.created_at) <= date_to)

    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    rows = await session.execute(
        base.order_by(StockMovement.created_at.desc()).limit(limit).offset(offset)
    )
    return MovementPage(
        items=[
            MovementOut(
                id=m.id,
                created_at=m.created_at,
                movement_type=m.movement_type,
                product_id=m.product_id,
                product_name=pname,
                sku=sku,
                warehouse_id=m.warehouse_id,
                warehouse_name=wname,
                base_quantity=m.base_quantity,
                batch_number=batch_number,
                reason=m.reason,
                source_document_type=m.source_document_type,
                actor_name=actor,
            )
            for m, pname, sku, wname, batch_number, actor in rows.all()
        ],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


# --- Batches ----------------------------------------------------------------
class BatchRowOut(BaseModel):
    batch_id: uuid.UUID
    batch_number: str
    product_id: uuid.UUID
    product_name: str
    warehouse_id: uuid.UUID
    warehouse_name: str
    expiry_date: date | None
    days_to_expiry: int | None
    on_hand: Decimal
    reserved: Decimal
    available: Decimal
    is_expired: bool


@router.get("/batches", response_model=list[BatchRowOut])
async def list_batches(
    product_id: uuid.UUID | None = Query(default=None),
    warehouse_id: uuid.UUID | None = Query(default=None),
    expiring_within_days: int | None = Query(default=None, ge=0, le=3650),
    limit: int = Query(default=200, ge=1, le=500),
    user: CurrentUser = Depends(require_permission("inventory.view")),
    session: AsyncSession = Depends(db_session),
) -> list[BatchRowOut]:
    """Batch-level stock with expiry, earliest expiry first (FEFO order)."""
    today = datetime.now(tz=timezone.utc).date()
    stmt = (
        select(StockBalance, Batch, Product.name, Warehouse.id, Warehouse.name)
        .join(Batch, Batch.id == StockBalance.batch_id)
        .join(Product, Product.id == StockBalance.product_id)
        .join(Warehouse, Warehouse.id == StockBalance.warehouse_id)
        .where(
            StockBalance.organization_id == user.organization_id,
            StockBalance.on_hand > 0,
        )
    )
    if product_id is not None:
        stmt = stmt.where(StockBalance.product_id == product_id)
    if warehouse_id is not None:
        stmt = stmt.where(StockBalance.warehouse_id == warehouse_id)
    if expiring_within_days is not None:
        stmt = stmt.where(
            Batch.expiry_date.is_not(None),
            Batch.expiry_date <= today + timedelta(days=expiring_within_days),
        )
    rows = await session.execute(stmt.order_by(Batch.expiry_date.asc().nulls_last()).limit(limit))

    result: list[BatchRowOut] = []
    for balance, batch, product_name, wid, wname in rows.all():
        days = (batch.expiry_date - today).days if batch.expiry_date else None
        result.append(
            BatchRowOut(
                batch_id=batch.id,
                batch_number=batch.batch_number,
                product_id=balance.product_id,
                product_name=product_name,
                warehouse_id=wid,
                warehouse_name=wname,
                expiry_date=batch.expiry_date,
                days_to_expiry=days,
                on_hand=balance.on_hand,
                reserved=balance.reserved,
                available=balance.on_hand - balance.reserved,
                is_expired=days is not None and days < 0,
            )
        )
    return result


# --- Adjustments ------------------------------------------------------------
class AdjustmentRequest(BaseModel):
    warehouse_id: uuid.UUID
    product_id: uuid.UUID
    # Signed: positive adds stock, negative removes it. Never zero.
    signed_quantity: Decimal
    reason: str = Field(min_length=3, max_length=300)
    movement_type: MovementType = MovementType.ADJUSTMENT


class AdjustmentResponse(BaseModel):
    movement_id: uuid.UUID
    applied_quantity: Decimal


_ADJUSTMENT_TYPES = {
    MovementType.ADJUSTMENT,
    MovementType.RECONCILIATION,
    MovementType.DAMAGE,
    MovementType.EXPIRY,
}


@router.post("/adjustments", response_model=AdjustmentResponse, status_code=201)
async def create_adjustment(
    payload: AdjustmentRequest,
    user: CurrentUser = Depends(require_permission("inventory.adjust")),
    session: AsyncSession = Depends(db_session),
) -> AdjustmentResponse:
    """Post a signed stock correction with a mandatory reason (audited)."""
    if payload.movement_type not in _ADJUSTMENT_TYPES:
        raise BusinessRuleError(
            "Only adjustment, reconciliation, damage or expiry movements can be posted here.",
            code="unsupported_movement_type",
        )
    # DAMAGE/EXPIRY only ever remove stock, so a positive figure is a slip.
    signed = payload.signed_quantity
    if payload.movement_type in {MovementType.DAMAGE, MovementType.EXPIRY} and signed > 0:
        signed = -signed

    posted = await InventoryService(session).adjust(
        organization_id=user.organization_id,
        warehouse_id=payload.warehouse_id,
        product_id=payload.product_id,
        signed_quantity=signed,
        movement_type=payload.movement_type,
        reason=payload.reason,
        branch_id=user.default_branch_id,
        created_by=user.user_id,
    )
    await session.commit()
    return AdjustmentResponse(
        movement_id=posted[0].movement_id,
        applied_quantity=sum((p.base_quantity for p in posted), Decimal("0")),
    )


# --- Transfers --------------------------------------------------------------
class TransferRequest(BaseModel):
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    product_id: uuid.UUID
    base_quantity: Decimal = Field(gt=0)


class TransferResponse(BaseModel):
    transferred: Decimal


@router.post("/transfers", response_model=TransferResponse, status_code=201)
async def create_transfer(
    payload: TransferRequest,
    user: CurrentUser = Depends(require_permission("stock.transfer")),
    session: AsyncSession = Depends(db_session),
) -> TransferResponse:
    """Move stock between two warehouses as a paired OUT/IN in one transaction."""
    if payload.from_warehouse_id == payload.to_warehouse_id:
        raise BusinessRuleError("Source and destination warehouses must differ.")
    await InventoryService(session).transfer(
        organization_id=user.organization_id,
        from_warehouse_id=payload.from_warehouse_id,
        to_warehouse_id=payload.to_warehouse_id,
        product_id=payload.product_id,
        base_quantity=payload.base_quantity,
        created_by=user.user_id,
    )
    await session.commit()
    return TransferResponse(transferred=payload.base_quantity)
