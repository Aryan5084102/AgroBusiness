"""Reporting endpoints (RBAC: report.view)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import CurrentUser
from app.core.deps import db_session, require_permission
from app.modules.reports.service import ReportsService

router = APIRouter(tags=["reports"])


class DashboardResponse(BaseModel):
    as_of: date
    sales_today_total: Decimal
    retail_today_total: Decimal
    wholesale_today_total: Decimal
    collected_today_total: Decimal
    receivables_outstanding: Decimal
    low_stock_product_count: int


class GstBucketOut(BaseModel):
    gst_rate: Decimal
    taxable_value: Decimal
    tax_amount: Decimal


class GstSummaryResponse(BaseModel):
    buckets: list[GstBucketOut]
    total_taxable: Decimal
    total_tax: Decimal


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    user: CurrentUser = Depends(require_permission("report.view")),
    session: AsyncSession = Depends(db_session),
) -> DashboardResponse:
    summary = await ReportsService(session).dashboard(
        organization_id=user.organization_id,
        as_of=datetime.now(tz=timezone.utc).date(),
    )
    return DashboardResponse(**summary.__dict__)


@router.get("/gst-summary", response_model=GstSummaryResponse)
async def gst_summary(
    date_from: date = Query(...),
    date_to: date = Query(...),
    user: CurrentUser = Depends(require_permission("report.view")),
    session: AsyncSession = Depends(db_session),
) -> GstSummaryResponse:
    summary = await ReportsService(session).gst_summary(
        organization_id=user.organization_id, date_from=date_from, date_to=date_to
    )
    return GstSummaryResponse(
        buckets=[GstBucketOut(**b.__dict__) for b in summary.buckets],
        total_taxable=summary.total_taxable,
        total_tax=summary.total_tax,
    )
