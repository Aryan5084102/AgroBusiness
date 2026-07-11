"""Collections service: receive a customer payment and settle invoices.

Allocates the receipt FIFO across the customer's outstanding invoices, updates
each invoice's paid amount + status, and posts the double-entry journal
(Dr Cash/Bank/UPI, Cr Accounts Receivable).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.money import Money
from app.core.exceptions import BusinessRuleError
from app.modules.accounting.service import (
    PAYMENT_METHOD_ACCOUNT,
    AccountingService,
    JournalLine,
)
from app.modules.collections.allocation import (
    OutstandingInvoice,
    allocate_payment,
)
from app.modules.payments.models import (
    Payment,
    PaymentAllocation,
    PaymentDirection,
    PaymentMethod,
)
from app.modules.sales.models import PaymentStatus, SalesInvoice


@dataclass
class CollectionResult:
    payment_id: uuid.UUID
    allocated_total: Decimal
    unallocated: Decimal
    settled_invoice_ids: list[uuid.UUID] = field(default_factory=list)


class CollectionsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._accounting = AccountingService(session)

    async def receive_payment(
        self,
        *,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        amount: Decimal,
        method: PaymentMethod,
        payment_date: date,
        branch_id: uuid.UUID | None = None,
        reference: str | None = None,
        created_by: uuid.UUID | None = None,
    ) -> CollectionResult:
        if amount <= 0:
            raise BusinessRuleError("Payment amount must be positive.")

        payment = Payment(
            organization_id=organization_id,
            branch_id=branch_id,
            customer_id=customer_id,
            direction=PaymentDirection.INBOUND,
            method=method,
            amount=Money(amount),
            reference=reference,
            created_by=created_by,
        )
        self._session.add(payment)
        await self._session.flush()

        invoices = await self._outstanding_invoices(organization_id, customer_id)
        result = allocate_payment(
            amount,
            [
                OutstandingInvoice(invoice_id=i.id, outstanding=i.grand_total - i.paid_amount)
                for i in invoices
            ],
        )

        settled: list[uuid.UUID] = []
        invoice_map = {i.id: i for i in invoices}
        for alloc in result.allocations:
            invoice = invoice_map[alloc.invoice_id]
            invoice.paid_amount = Money(invoice.paid_amount + alloc.amount)
            invoice.payment_status = (
                PaymentStatus.PAID
                if invoice.paid_amount >= invoice.grand_total
                else PaymentStatus.PARTIAL
            )
            if invoice.payment_status == PaymentStatus.PAID:
                settled.append(invoice.id)
            self._session.add(
                PaymentAllocation(
                    payment_id=payment.id,
                    sales_invoice_id=invoice.id,
                    amount=alloc.amount,
                )
            )

        # Double-entry: money in (asset up), receivable down.
        debit_account = PAYMENT_METHOD_ACCOUNT.get(method.value, "CASH")
        await self._accounting.post(
            organization_id=organization_id,
            entry_date=payment_date,
            branch_id=branch_id,
            narration=f"Collection from customer {customer_id}",
            source_document_type="payment",
            source_document_id=payment.id,
            created_by=created_by,
            lines=[
                JournalLine(account_code=debit_account, debit=Money(amount)),
                JournalLine(account_code="AR", credit=Money(amount)),
            ],
        )

        await self._session.flush()
        return CollectionResult(
            payment_id=payment.id,
            allocated_total=result.allocated_total,
            unallocated=result.unallocated,
            settled_invoice_ids=settled,
        )

    async def customer_ledger_balance(
        self, organization_id: uuid.UUID, customer_id: uuid.UUID
    ) -> Decimal:
        invoices = await self._outstanding_invoices(organization_id, customer_id)
        return Money(sum((i.grand_total - i.paid_amount for i in invoices), Decimal("0")))

    async def _outstanding_invoices(
        self, organization_id: uuid.UUID, customer_id: uuid.UUID
    ) -> list[SalesInvoice]:
        result = await self._session.execute(
            select(SalesInvoice)
            .where(
                SalesInvoice.organization_id == organization_id,
                SalesInvoice.customer_id == customer_id,
                SalesInvoice.payment_status != PaymentStatus.PAID,
            )
            .order_by(SalesInvoice.invoice_date, SalesInvoice.created_at)
            .with_for_update()
        )
        return list(result.scalars().all())
