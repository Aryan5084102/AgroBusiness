"""Organization structure endpoints: profile, branches and warehouses.

Reads only need a session (every authenticated user picks a warehouse in the POS
or inventory screens); writes require ``settings.manage``.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import CurrentUser
from app.core.deps import db_session, get_current_user, require_permission
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.organizations.models import Branch, Organization, Warehouse, WarehouseType

router = APIRouter(tags=["organizations"])


# --- Profile ----------------------------------------------------------------
class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    legal_name: str | None
    gstin: str | None
    address: str | None
    currency: str


class UpdateOrganizationRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    legal_name: str | None = Field(default=None, max_length=200)
    gstin: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=500)


def _to_org_out(org: Organization) -> OrganizationOut:
    return OrganizationOut(
        id=org.id,
        name=org.name,
        legal_name=org.legal_name,
        gstin=org.gstin,
        address=org.address,
        currency=org.currency,
    )


@router.get("/profile", response_model=OrganizationOut)
async def get_profile(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> OrganizationOut:
    """Business identity used on invoices and in the app header."""
    org = await session.get(Organization, user.organization_id)
    if org is None:
        raise NotFoundError("Unknown organization.")
    return _to_org_out(org)


@router.patch("/profile", response_model=OrganizationOut)
async def update_profile(
    payload: UpdateOrganizationRequest,
    user: CurrentUser = Depends(require_permission("settings.manage")),
    session: AsyncSession = Depends(db_session),
) -> OrganizationOut:
    org = await session.get(Organization, user.organization_id)
    if org is None:
        raise NotFoundError("Unknown organization.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(org, field, value)
    await session.commit()
    return _to_org_out(org)


# --- Branches ---------------------------------------------------------------
class BranchOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    address: str | None
    is_active: bool
    warehouse_count: int


class CreateBranchRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=20)
    address: str | None = Field(default=None, max_length=500)


@router.get("/branches", response_model=list[BranchOut])
async def list_branches(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> list[BranchOut]:
    counts = (
        select(Warehouse.branch_id, func.count().label("total"))
        .where(Warehouse.organization_id == user.organization_id)
        .group_by(Warehouse.branch_id)
        .subquery()
    )
    rows = await session.execute(
        select(Branch, func.coalesce(counts.c.total, 0))
        .outerjoin(counts, counts.c.branch_id == Branch.id)
        .where(Branch.organization_id == user.organization_id)
        .order_by(Branch.name)
    )
    return [
        BranchOut(
            id=b.id,
            name=b.name,
            code=b.code,
            address=b.address,
            is_active=b.is_active,
            warehouse_count=int(count),
        )
        for b, count in rows.all()
    ]


@router.post("/branches", response_model=BranchOut, status_code=201)
async def create_branch(
    payload: CreateBranchRequest,
    user: CurrentUser = Depends(require_permission("settings.manage")),
    session: AsyncSession = Depends(db_session),
) -> BranchOut:
    existing = await session.scalar(
        select(func.count())
        .select_from(Branch)
        .where(Branch.organization_id == user.organization_id, Branch.code == payload.code)
    )
    if existing:
        raise ConflictError(f"A branch with code {payload.code} already exists.")
    branch = Branch(
        organization_id=user.organization_id,
        name=payload.name,
        code=payload.code,
        address=payload.address,
    )
    session.add(branch)
    await session.commit()
    return BranchOut(
        id=branch.id,
        name=branch.name,
        code=branch.code,
        address=branch.address,
        is_active=branch.is_active,
        warehouse_count=0,
    )


# --- Warehouses -------------------------------------------------------------
class WarehouseOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    type: WarehouseType
    branch_id: uuid.UUID | None
    branch_name: str | None
    is_active: bool


class CreateWarehouseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=20)
    type: WarehouseType = WarehouseType.SHOP
    branch_id: uuid.UUID | None = None


@router.get("/warehouses", response_model=list[WarehouseOut])
async def list_warehouses(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> list[WarehouseOut]:
    result = await session.execute(
        select(Warehouse, Branch.name)
        .outerjoin(Branch, Branch.id == Warehouse.branch_id)
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
            branch_name=branch_name,
            is_active=w.is_active,
        )
        for w, branch_name in result.all()
    ]


@router.post("/warehouses", response_model=WarehouseOut, status_code=201)
async def create_warehouse(
    payload: CreateWarehouseRequest,
    user: CurrentUser = Depends(require_permission("settings.manage")),
    session: AsyncSession = Depends(db_session),
) -> WarehouseOut:
    existing = await session.scalar(
        select(func.count())
        .select_from(Warehouse)
        .where(
            Warehouse.organization_id == user.organization_id,
            Warehouse.code == payload.code,
        )
    )
    if existing:
        raise ConflictError(f"A warehouse with code {payload.code} already exists.")
    warehouse = Warehouse(
        organization_id=user.organization_id,
        branch_id=payload.branch_id,
        name=payload.name,
        code=payload.code,
        type=payload.type,
    )
    session.add(warehouse)
    await session.commit()
    return WarehouseOut(
        id=warehouse.id,
        name=warehouse.name,
        code=warehouse.code,
        type=warehouse.type,
        branch_id=warehouse.branch_id,
        branch_name=None,
        is_active=warehouse.is_active,
    )
