"""Organization structure endpoints (warehouses list for the POS/inventory UI)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import CurrentUser
from app.core.deps import db_session, get_current_user
from app.modules.organizations.models import Warehouse, WarehouseType

router = APIRouter(tags=["organizations"])


class WarehouseOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    type: WarehouseType
    branch_id: uuid.UUID | None
    is_active: bool


@router.get("/warehouses", response_model=list[WarehouseOut])
async def list_warehouses(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> list[WarehouseOut]:
    result = await session.execute(
        select(Warehouse)
        .where(
            Warehouse.organization_id == user.organization_id,
            Warehouse.is_active.is_(True),
        )
        .order_by(Warehouse.name)
    )
    return [
        WarehouseOut(
            id=w.id,
            name=w.name,
            code=w.code,
            type=w.type,
            branch_id=w.branch_id,
            is_active=w.is_active,
        )
        for w in result.scalars().all()
    ]
