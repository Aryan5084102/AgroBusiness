"""Tests for hierarchical unit conversion."""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.common.units import UnitConversion, to_base_quantity, to_display_quantity
from hypothesis import given
from hypothesis import strategies as st

factors = st.integers(min_value=1, max_value=100000).map(Decimal)
quantities = st.decimals(min_value=0, max_value=100000, places=3, allow_nan=False)


def test_carton_to_bottles() -> None:
    carton = UnitConversion(unit_code="carton", base_factor=Decimal(20))
    assert to_base_quantity(Decimal(3), carton) == Decimal(60)


def test_bag_of_grams() -> None:
    bag = UnitConversion(unit_code="bag", base_factor=Decimal(50000))
    assert to_base_quantity(Decimal(2), bag) == Decimal(100000)


def test_rejects_non_positive_factor() -> None:
    with pytest.raises(ValueError):
        UnitConversion(unit_code="bad", base_factor=Decimal(0))


def test_rejects_negative_quantity() -> None:
    unit = UnitConversion(unit_code="u", base_factor=Decimal(1))
    with pytest.raises(ValueError):
        to_base_quantity(Decimal(-1), unit)


def test_display_rejects_negative_base() -> None:
    unit = UnitConversion(unit_code="u", base_factor=Decimal(1))
    with pytest.raises(ValueError):
        to_display_quantity(Decimal(-1), unit)


@given(qty=st.integers(min_value=0, max_value=10000).map(Decimal), factor=factors)
def test_round_trip_is_stable_for_whole_units(qty: Decimal, factor: Decimal) -> None:
    unit = UnitConversion(unit_code="u", base_factor=factor)
    base = to_base_quantity(qty, unit)
    assert to_display_quantity(base, unit) == qty


@given(base=quantities, factor=factors)
def test_display_never_overstates_stock(base: Decimal, factor: Decimal) -> None:
    unit = UnitConversion(unit_code="u", base_factor=factor)
    display = to_display_quantity(base, unit)
    # Converting the displayed amount back must not exceed the real base stock.
    assert to_base_quantity(display, unit) <= base
