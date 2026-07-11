"""Supplier endpoints (tenant-scoped, RBAC-guarded)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import CurrentUser
from app.core.deps import db_session, require_permission
from app.modules.suppliers.models import Supplier

router = APIRouter(tags=["suppliers"])


class SupplierOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    is_active: bool


class CreateSupplierRequest(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    gstin: str | None = None
    phone: str | None = None
    credit_period_days: int = 0


@router.get("", response_model=list[SupplierOut])
async def list_suppliers(
    user: CurrentUser = Depends(require_permission("purchase.view")),
    session: AsyncSession = Depends(db_session),
) -> list[SupplierOut]:
    result = await session.execute(
        select(Supplier).where(Supplier.organization_id == user.organization_id)
    )
    return [
        SupplierOut(id=s.id, code=s.code, name=s.name, is_active=s.is_active)
        for s in result.scalars().all()
    ]


@router.post("", response_model=SupplierOut, status_code=201)
async def create_supplier(
    payload: CreateSupplierRequest,
    user: CurrentUser = Depends(require_permission("purchase.create")),
    session: AsyncSession = Depends(db_session),
) -> SupplierOut:
    supplier = Supplier(
        organization_id=user.organization_id,
        code=payload.code,
        name=payload.name,
        gstin=payload.gstin,
        phone=payload.phone,
        credit_period_days=payload.credit_period_days,
    )
    session.add(supplier)
    await session.commit()
    return SupplierOut(
        id=supplier.id, code=supplier.code, name=supplier.name, is_active=supplier.is_active
    )
