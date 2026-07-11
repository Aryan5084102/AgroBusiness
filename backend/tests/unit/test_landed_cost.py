"""Unit + property tests for landed-cost computation."""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.modules.purchases.landed_cost import (
    PurchaseLineInput,
    compute_landed_cost,
)
from hypothesis import given
from hypothesis import strategies as st


def _line(line_id: str, qty: str, rate: str, free: str = "0", **kw: object) -> PurchaseLineInput:
    return PurchaseLineInput(
        line_id=line_id,
        billed_quantity=Decimal(qty),
        free_quantity=Decimal(free),
        unit_rate=Decimal(rate),
        **kw,  # type: ignore[arg-type]
    )


def test_simple_landed_cost_no_overhead() -> None:
    result = compute_landed_cost([_line("a", "10", "100")])
    assert result.goods_value == Decimal("1000.00")
    assert result.total_overhead == Decimal("0.00")
    assert result.lines[0].landed_unit_cost == Decimal("100.0000")


def test_free_quantity_lowers_unit_cost() -> None:
    # Buy 10 at 100, get 2 free -> 1000 spread over 12 units.
    result = compute_landed_cost([_line("a", "10", "100", free="2")])
    assert result.lines[0].total_units == Decimal("12")
    assert result.lines[0].landed_unit_cost == Decimal("83.3333")


def test_discounts_reduce_net_value() -> None:
    result = compute_landed_cost([_line("a", "10", "100", trade_discount_percent=Decimal("10"))])
    # 1000 - 10% = 900.
    assert result.lines[0].net_line_value == Decimal("900.00")


def test_overhead_apportioned_by_value() -> None:
    lines = [_line("a", "10", "100"), _line("b", "10", "300")]
    # goods = 1000 + 3000 = 4000; freight 400 splits 1:3 -> 100 / 300.
    result = compute_landed_cost(lines, freight=Decimal("400"))
    by_id = {ln.line_id: ln for ln in result.lines}
    assert by_id["a"].allocated_overhead == Decimal("100.00")
    assert by_id["b"].allocated_overhead == Decimal("300.00")
    assert result.grand_total == Decimal("4400.00")


def test_empty_lines_rejected() -> None:
    with pytest.raises(ValueError):
        compute_landed_cost([])


def test_non_positive_billed_qty_rejected() -> None:
    with pytest.raises(ValueError):
        compute_landed_cost([_line("a", "0", "100")])


line_strategy = st.builds(
    _line,
    line_id=st.uuids().map(str),
    qty=st.integers(min_value=1, max_value=500).map(str),
    rate=st.integers(min_value=1, max_value=5000).map(str),
    free=st.integers(min_value=0, max_value=20).map(str),
)


@given(
    lines=st.lists(line_strategy, min_size=1, max_size=6),
    freight=st.integers(min_value=0, max_value=10000).map(Decimal),
    loading=st.integers(min_value=0, max_value=5000).map(Decimal),
)
def test_overhead_allocation_has_no_leakage(
    lines: list[PurchaseLineInput], freight: Decimal, loading: Decimal
) -> None:
    result = compute_landed_cost(lines, freight=freight, loading=loading)
    # Allocated overhead sums exactly to the total overhead (no rounding leak).
    allocated = sum((ln.allocated_overhead for ln in result.lines), Decimal("0"))
    assert allocated == result.total_overhead
    # Grand total = goods value + overhead.
    assert result.grand_total == result.goods_value + result.total_overhead
