"""FEFO (First-Expiry-First-Out) batch allocation — pure domain logic.

Given the available batches for a product at a warehouse and a required quantity,
allocate from the earliest-expiring batch first. Batches already expired (as of
``as_of``) are excluded. Non-expiring batches (expiry is None) are consumed last.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class BatchAvailability:
    batch_id: uuid.UUID | None
    expiry_date: date | None
    available: Decimal


@dataclass(frozen=True)
class Allocation:
    batch_id: uuid.UUID | None
    quantity: Decimal


class InsufficientStockError(Exception):
    """Raised when available stock cannot satisfy the requested quantity."""

    def __init__(self, requested: Decimal, available: Decimal) -> None:
        super().__init__(f"Insufficient stock: requested {requested}, available {available}.")
        self.requested = requested
        self.available = available


def _sort_key(batch: BatchAvailability) -> tuple[int, date]:
    # Expiring batches first (ordered by date); non-expiring (None) sorted last.
    if batch.expiry_date is None:
        return (1, date.max)
    return (0, batch.expiry_date)


def allocate_fefo(
    batches: list[BatchAvailability],
    required: Decimal,
    *,
    as_of: date,
) -> list[Allocation]:
    """Allocate ``required`` base units across batches, earliest expiry first.

    Excludes batches expired on/before ``as_of``. Raises InsufficientStockError if
    the (non-expired) available quantity is less than ``required``.
    """
    if required <= 0:
        raise ValueError("Required quantity must be positive.")

    usable = [
        b for b in batches if b.available > 0 and (b.expiry_date is None or b.expiry_date > as_of)
    ]
    total_available = sum((b.available for b in usable), Decimal("0"))
    if total_available < required:
        raise InsufficientStockError(required, total_available)

    allocations: list[Allocation] = []
    remaining = required
    for batch in sorted(usable, key=_sort_key):
        if remaining <= 0:
            break
        take = min(batch.available, remaining)
        allocations.append(Allocation(batch_id=batch.batch_id, quantity=take))
        remaining -= take
    return allocations
