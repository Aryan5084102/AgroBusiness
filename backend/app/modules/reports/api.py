"""Reporting endpoints (RBAC: ``report.view``; profit figures need
``report.view_profit``). Registers can also be streamed as CSV for Excel."""

from __future__ import annotations

import csv
import io
import uuid
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import CurrentUser
from app.core.deps import db_session, require_permission
from app.modules.reports.service import RegisterRow, ReportsService
from app.modules.sales.models import SaleChannel

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


# --- Registers --------------------------------------------------------------
class RegisterRowOut(BaseModel):
    entry_date: date
    document_number: str
    party: str
    category: str
    taxable_value: Decimal
    tax_amount: Decimal
    total: Decimal
    settled: Decimal
    status: str


class RegisterResponse(BaseModel):
    rows: list[RegisterRowOut]
    total_taxable: Decimal
    total_tax: Decimal
    grand_total: Decimal


def _register_response(rows: Sequence[RegisterRow]) -> RegisterResponse:
    return RegisterResponse(
        rows=[RegisterRowOut(**r.__dict__) for r in rows],
        total_taxable=sum((r.taxable_value for r in rows), Decimal("0.00")),
        total_tax=sum((r.tax_amount for r in rows), Decimal("0.00")),
        grand_total=sum((r.total for r in rows), Decimal("0.00")),
    )


@router.get("/sales-register", response_model=RegisterResponse)
async def sales_register(
    date_from: date = Query(...),
    date_to: date = Query(...),
    channel: SaleChannel | None = Query(default=None),
    user: CurrentUser = Depends(require_permission("report.view")),
    session: AsyncSession = Depends(db_session),
) -> RegisterResponse:
    rows = await ReportsService(session).sales_register(
        organization_id=user.organization_id,
        date_from=date_from,
        date_to=date_to,
        channel=channel,
    )
    return _register_response(rows)


@router.get("/purchase-register", response_model=RegisterResponse)
async def purchase_register(
    date_from: date = Query(...),
    date_to: date = Query(...),
    user: CurrentUser = Depends(require_permission("report.view")),
    session: AsyncSession = Depends(db_session),
) -> RegisterResponse:
    rows = await ReportsService(session).purchase_register(
        organization_id=user.organization_id, date_from=date_from, date_to=date_to
    )
    return _register_response(rows)


# --- Stock valuation --------------------------------------------------------
class StockValuationRowOut(BaseModel):
    product_id: uuid.UUID
    product_name: str
    sku: str
    on_hand: Decimal
    min_stock: Decimal
    retail_price: Decimal
    stock_value: Decimal
    is_low: bool


class StockValuationResponse(BaseModel):
    rows: list[StockValuationRowOut]
    total_value: Decimal
    low_stock_count: int


@router.get("/stock-valuation", response_model=StockValuationResponse)
async def stock_valuation(
    user: CurrentUser = Depends(require_permission("report.view")),
    session: AsyncSession = Depends(db_session),
) -> StockValuationResponse:
    rows = await ReportsService(session).stock_valuation(organization_id=user.organization_id)
    return StockValuationResponse(
        rows=[StockValuationRowOut(**r.__dict__) for r in rows],
        total_value=sum((r.stock_value for r in rows), Decimal("0.00")),
        low_stock_count=sum(1 for r in rows if r.is_low),
    )


# --- Dashboard extras -------------------------------------------------------
class TopProductOut(BaseModel):
    product_id: uuid.UUID
    product_name: str
    sku: str
    quantity_sold: Decimal
    revenue: Decimal


@router.get("/top-products", response_model=list[TopProductOut])
async def top_products(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=50),
    user: CurrentUser = Depends(require_permission("report.view")),
    session: AsyncSession = Depends(db_session),
) -> list[TopProductOut]:
    today = datetime.now(tz=timezone.utc).date()
    rows = await ReportsService(session).top_products(
        organization_id=user.organization_id,
        date_from=today - timedelta(days=days - 1),
        date_to=today,
        limit=limit,
    )
    return [TopProductOut(**r.__dict__) for r in rows]


class TrendPointOut(BaseModel):
    day: date
    revenue: Decimal
    invoice_count: int


@router.get("/sales-trend", response_model=list[TrendPointOut])
async def sales_trend(
    days: int = Query(default=14, ge=2, le=180),
    user: CurrentUser = Depends(require_permission("report.view")),
    session: AsyncSession = Depends(db_session),
) -> list[TrendPointOut]:
    """Daily revenue for the last N days, gaps filled with zero."""
    today = datetime.now(tz=timezone.utc).date()
    start = today - timedelta(days=days - 1)
    points = await ReportsService(session).sales_trend(
        organization_id=user.organization_id, date_from=start, date_to=today
    )
    by_day = {p.day: p for p in points}
    filled: list[TrendPointOut] = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        point = by_day.get(day)
        filled.append(
            TrendPointOut(
                day=day,
                revenue=point.revenue if point else Decimal("0.00"),
                invoice_count=point.invoice_count if point else 0,
            )
        )
    return filled


# --- CSV export -------------------------------------------------------------
_CSV_HEADERS = [
    "Date",
    "Document",
    "Party",
    "Category",
    "Taxable value",
    "Tax",
    "Total",
    "Settled",
    "Status",
]


@router.get("/export/{register}")
async def export_register(
    register: str,
    date_from: date = Query(...),
    date_to: date = Query(...),
    user: CurrentUser = Depends(require_permission("report.view")),
    session: AsyncSession = Depends(db_session),
) -> StreamingResponse:
    """Download a register as CSV (opens directly in Excel)."""
    service = ReportsService(session)
    if register == "sales":
        rows = await service.sales_register(
            organization_id=user.organization_id, date_from=date_from, date_to=date_to
        )
    elif register == "purchases":
        rows = await service.purchase_register(
            organization_id=user.organization_id, date_from=date_from, date_to=date_to
        )
    else:
        from app.core.exceptions import NotFoundError

        raise NotFoundError(f"Unknown register: {register}")

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_CSV_HEADERS)
    for row in rows:
        writer.writerow(
            [
                row.entry_date.isoformat(),
                row.document_number,
                row.party,
                row.category,
                f"{row.taxable_value:.2f}",
                f"{row.tax_amount:.2f}",
                f"{row.total:.2f}",
                f"{row.settled:.2f}",
                row.status,
            ]
        )
    buffer.seek(0)
    filename = f"{register}-register-{date_from}-to-{date_to}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
