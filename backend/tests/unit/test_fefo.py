"""Unit + property tests for FEFO batch allocation."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from app.modules.inventory.fefo import (
    BatchAvailability,
    InsufficientStockError,
    allocate_fefo,
)
from hypothesis import given
from hypothesis import strategies as st

TODAY = date(2026, 7, 11)


def _batch(days_to_expiry: int | None, qty: str) -> BatchAvailability:
    expiry = (
        None if days_to_expiry is None else date.fromordinal(TODAY.toordinal() + days_to_expiry)
    )
    return BatchAvailability(batch_id=uuid.uuid4(), expiry_date=expiry, available=Decimal(qty))


def test_allocates_earliest_expiry_first() -> None:
    near = _batch(10, "5")
    far = _batch(90, "20")
    allocations = allocate_fefo([far, near], Decimal("7"), as_of=TODAY)
    # Near-expiry batch fully consumed first, remainder from far.
    assert allocations[0].batch_id == near.batch_id
    assert allocations[0].quantity == Decimal("5")
    assert allocations[1].batch_id == far.batch_id
    assert allocations[1].quantity == Decimal("2")


def test_excludes_expired_batches() -> None:
    expired = _batch(-1, "100")
    good = _batch(30, "10")
    allocations = allocate_fefo([expired, good], Decimal("10"), as_of=TODAY)
    assert len(allocations) == 1
    assert allocations[0].batch_id == good.batch_id


def test_non_expiring_batches_consumed_last() -> None:
    perpetual = _batch(None, "100")
    expiring = _batch(5, "3")
    allocations = allocate_fefo([perpetual, expiring], Decimal("4"), as_of=TODAY)
    assert allocations[0].batch_id == expiring.batch_id
    assert allocations[1].batch_id == perpetual.batch_id


def test_raises_when_insufficient() -> None:
    with pytest.raises(InsufficientStockError):
        allocate_fefo([_batch(30, "3")], Decimal("10"), as_of=TODAY)


def test_rejects_non_positive_request() -> None:
    with pytest.raises(ValueError):
        allocate_fefo([_batch(30, "3")], Decimal("0"), as_of=TODAY)


@given(
    quantities=st.lists(
        st.integers(min_value=1, max_value=1000).map(Decimal), min_size=1, max_size=6
    ),
    request_fraction=st.integers(min_value=1, max_value=100),
)
def test_allocations_sum_to_request(quantities: list[Decimal], request_fraction: int) -> None:
    batches = [
        BatchAvailability(
            batch_id=uuid.uuid4(),
            expiry_date=date.fromordinal(TODAY.toordinal() + 10 + i),
            available=q,
        )
        for i, q in enumerate(quantities)
    ]
    total = sum(quantities, Decimal("0"))
    required = (total * request_fraction / 100).quantize(Decimal("0.001"))
    if required <= 0:
        return
    allocations = allocate_fefo(batches, required, as_of=TODAY)
    assert sum((a.quantity for a in allocations), Decimal("0")) == required
    # Never allocate more from a batch than it holds.
    by_id = {b.batch_id: b.available for b in batches}
    for a in allocations:
        assert a.quantity <= by_id[a.batch_id]
