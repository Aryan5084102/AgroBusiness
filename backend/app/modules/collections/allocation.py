"""Payment allocation — pure domain logic.

Allocate a received amount across a customer's outstanding invoices, oldest
first (FIFO). Never allocates more than an invoice's outstanding balance; any
amount beyond total outstanding is returned as ``unallocated`` (an advance).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from app.common.money import Money


@dataclass(frozen=True)
class OutstandingInvoice:
    invoice_id: uuid.UUID
    outstanding: Decimal


@dataclass(frozen=True)
class InvoiceAllocation:
    invoice_id: uuid.UUID
    amount: Decimal


@dataclass(frozen=True)
class AllocationResult:
    allocations: list[InvoiceAllocation]
    allocated_total: Decimal
    unallocated: Decimal


def allocate_payment(amount: Decimal, invoices: list[OutstandingInvoice]) -> AllocationResult:
    """Allocate ``amount`` across ``invoices`` (already oldest-first) FIFO."""
    if amount <= 0:
        raise ValueError("Payment amount must be positive.")

    remaining = Money(amount)
    allocations: list[InvoiceAllocation] = []
    for inv in invoices:
        if remaining <= 0:
            break
        if inv.outstanding <= 0:
            continue
        take = min(inv.outstanding, remaining)
        allocations.append(InvoiceAllocation(invoice_id=inv.invoice_id, amount=Money(take)))
        remaining = Money(remaining - take)

    allocated_total = Money(sum((a.amount for a in allocations), Decimal("0")))
    return AllocationResult(
        allocations=allocations,
        allocated_total=allocated_total,
        unallocated=Money(remaining),
    )
