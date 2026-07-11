"""Property-based and example tests for the money kernel (≥95% target module)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.common.money import (
    Money,
    allocate,
    apply_percentage_discount,
    split_tax_from_inclusive,
    tax_on_exclusive,
)
from hypothesis import given
from hypothesis import strategies as st

money_amounts = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1000000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
gst_rates = st.sampled_from([Decimal(r) for r in ("0", "5", "12", "18", "28")])


def test_money_rejects_float() -> None:
    with pytest.raises(TypeError):
        Money(1.5)


def test_money_quantizes_half_up() -> None:
    assert Money("10.005") == Decimal("10.01")
    assert Money("10.004") == Decimal("10.00")


@given(gross=money_amounts, gst=gst_rates)
def test_inclusive_split_reconstitutes_gross(gross: Decimal, gst: Decimal) -> None:
    net, tax = split_tax_from_inclusive(gross, gst)
    assert net + tax == gross
    assert net >= 0
    assert tax >= 0


@given(base=money_amounts, gst=gst_rates)
def test_exclusive_tax_is_non_negative(base: Decimal, gst: Decimal) -> None:
    assert tax_on_exclusive(base, gst) >= 0


@given(
    amount=money_amounts,
    percent=st.decimals(min_value=0, max_value=100, places=2, allow_nan=False),
)
def test_discount_never_exceeds_amount(amount: Decimal, percent: Decimal) -> None:
    discounted = apply_percentage_discount(amount, percent)
    assert Decimal("0") <= discounted <= amount


@given(
    total=money_amounts,
    weights=st.lists(
        st.integers(min_value=0, max_value=1000).map(Decimal),
        min_size=1,
        max_size=8,
    ),
)
def test_allocate_sums_to_total(total: Decimal, weights: list[Decimal]) -> None:
    shares = allocate(total, weights)
    assert sum(shares) == total
    assert len(shares) == len(weights)
    assert all(s >= 0 for s in shares)


def test_discount_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        apply_percentage_discount(Decimal("100.00"), Decimal("150"))
    with pytest.raises(ValueError):
        apply_percentage_discount(Decimal("100.00"), Decimal("-1"))


def test_tax_rejects_negative_rate() -> None:
    with pytest.raises(ValueError):
        tax_on_exclusive(Decimal("100.00"), Decimal("-5"))
    with pytest.raises(ValueError):
        split_tax_from_inclusive(Decimal("100.00"), Decimal("-5"))


def test_allocate_rejects_empty_and_negative_weights() -> None:
    with pytest.raises(ValueError):
        allocate(Decimal("10.00"), [])
    with pytest.raises(ValueError):
        allocate(Decimal("10.00"), [Decimal(1), Decimal(-1)])


def test_allocate_all_zero_weights_puts_total_on_first() -> None:
    shares = allocate(Decimal("10.00"), [Decimal(0), Decimal(0)])
    assert shares == [Decimal("10.00"), Decimal("0.00")]


def test_allocate_distributes_leftover_pennies() -> None:
    # 10.00 split three ways cannot divide evenly; pennies must still sum.
    shares = allocate(Decimal("10.00"), [Decimal(1), Decimal(1), Decimal(1)])
    assert sum(shares) == Decimal("10.00")
    assert sorted(shares) == [Decimal("3.33"), Decimal("3.33"), Decimal("3.34")]
