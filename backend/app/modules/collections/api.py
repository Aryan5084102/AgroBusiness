"""Collections endpoint: receive a customer payment (RBAC: payment.receive)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import CurrentUser
from app.core.deps import db_session, require_permission
from app.modules.collections.service import CollectionsService
from app.modules.payments.models import PaymentMethod

router = APIRouter(tags=["collections"])


class ReceivePaymentRequest(BaseModel):
    customer_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    method: PaymentMethod
    reference: str | None = None


class ReceivePaymentResponse(BaseModel):
    payment_id: uuid.UUID
    allocated_total: Decimal
    unallocated: Decimal
    settled_invoice_ids: list[uuid.UUID]


@router.post("/payments", response_model=ReceivePaymentResponse, status_code=201)
async def receive_payment(
    payload: ReceivePaymentRequest,
    user: CurrentUser = Depends(require_permission("payment.receive")),
    session: AsyncSession = Depends(db_session),
) -> ReceivePaymentResponse:
    service = CollectionsService(session)
    result = await service.receive_payment(
        organization_id=user.organization_id,
        customer_id=payload.customer_id,
        amount=payload.amount,
        method=payload.method,
        payment_date=datetime.now(tz=timezone.utc).date(),
        reference=payload.reference,
        created_by=user.user_id,
    )
    await session.commit()
    return ReceivePaymentResponse(
        payment_id=result.payment_id,
        allocated_total=result.allocated_total,
        unallocated=result.unallocated,
        settled_invoice_ids=result.settled_invoice_ids,
    )
