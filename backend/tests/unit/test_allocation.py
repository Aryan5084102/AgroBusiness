"""Unit + property tests for FIFO payment allocation."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from app.modules.collections.allocation import (
    OutstandingInvoice,
    allocate_payment,
)
from hypothesis import given
from hypothesis import strategies as st


def _inv(amount: str) -> OutstandingInvoice:
    return OutstandingInvoice(invoice_id=uuid.uuid4(), outstanding=Decimal(amount))


def test_allocates_oldest_first() -> None:
    a, b = _inv("100.00"), _inv("100.00")
    result = allocate_payment(Decimal("150.00"), [a, b])
    assert result.allocations[0].invoice_id == a.invoice_id
    assert result.allocations[0].amount == Decimal("100.00")
    assert result.allocations[1].invoice_id == b.invoice_id
    assert result.allocations[1].amount == Decimal("50.00")
    assert result.unallocated == Decimal("0.00")


def test_overpayment_leaves_unallocated_advance() -> None:
    result = allocate_payment(Decimal("500.00"), [_inv("100.00")])
    assert result.allocated_total == Decimal("100.00")
    assert result.unallocated == Decimal("400.00")


def test_rejects_non_positive_amount() -> None:
    with pytest.raises(ValueError):
        allocate_payment(Decimal("0"), [_inv("100")])


@given(
    amount=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("100000"), places=2),
    outstandings=st.lists(
        st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10000"), places=2),
        min_size=1,
        max_size=8,
    ),
)
def test_allocation_never_exceeds_outstanding_or_amount(
    amount: Decimal, outstandings: list[Decimal]
) -> None:
    invoices = [OutstandingInvoice(invoice_id=uuid.uuid4(), outstanding=o) for o in outstandings]
    result = allocate_payment(amount, invoices)
    by_id = {i.invoice_id: i.outstanding for i in invoices}
    # No single allocation exceeds that invoice's outstanding.
    for a in result.allocations:
        assert a.amount <= by_id[a.invoice_id]
    total_out = sum(outstandings, Decimal("0"))
    # Allocated total is exactly min(amount, total outstanding).
    assert result.allocated_total == min(amount, total_out)
    assert result.allocated_total + result.unallocated == amount
