"""Unit + property tests for the pricing engine (≥95% target module)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.modules.pricing.engine import (
    PriceInput,
    PriceSource,
    QuantitySlab,
    price_line,
    resolve_unit_price,
)
from hypothesis import given
from hypothesis import strategies as st


def _base(**kw: object) -> PriceInput:
    defaults: dict[str, object] = {
        "quantity": Decimal("1"),
        "retail_price": Decimal("100.00"),
        "mrp": Decimal("120.00"),
    }
    defaults.update(kw)
    return PriceInput(**defaults)  # type: ignore[arg-type]


def test_priority_contract_wins() -> None:
    data = _base(
        contract_price=Decimal("80.00"),
        price_list_price=Decimal("85.00"),
        wholesale_price=Decimal("90.00"),
        min_wholesale_quantity=Decimal("1"),
    )
    price, source = resolve_unit_price(data)
    assert source is PriceSource.CONTRACT
    assert price == Decimal("80.00")


def test_price_list_beats_slab_and_wholesale() -> None:
    data = _base(
        price_list_price=Decimal("85.00"),
        quantity_slabs=(QuantitySlab(Decimal("1"), Decimal("70.00")),),
    )
    _, source = resolve_unit_price(data)
    assert source is PriceSource.CUSTOMER_PRICE_LIST


def test_deepest_slab_wins() -> None:
    data = _base(
        quantity=Decimal("50"),
        quantity_slabs=(
            QuantitySlab(Decimal("10"), Decimal("95.00")),
            QuantitySlab(Decimal("40"), Decimal("88.00")),
        ),
    )
    price, source = resolve_unit_price(data)
    assert source is PriceSource.QUANTITY_SLAB
    assert price == Decimal("88.00")


def test_wholesale_applies_above_min_qty() -> None:
    data = _base(
        quantity=Decimal("10"),
        wholesale_price=Decimal("90.00"),
        min_wholesale_quantity=Decimal("5"),
    )
    _, source = resolve_unit_price(data)
    assert source is PriceSource.WHOLESALE


def test_mrp_fallback_when_no_retail() -> None:
    data = _base(retail_price=Decimal("0"))
    _, source = resolve_unit_price(data)
    assert source is PriceSource.MRP


def test_exclusive_tax_line_total() -> None:
    result = price_line(
        _base(quantity=Decimal("2"), retail_price=Decimal("100.00"), gst_percent=Decimal("18"))
    )
    assert result.net_amount == Decimal("200.00")
    assert result.tax_amount == Decimal("36.00")
    assert result.total_amount == Decimal("236.00")


def test_inclusive_tax_splits_out_of_total() -> None:
    result = price_line(
        _base(
            quantity=Decimal("1"),
            retail_price=Decimal("118.00"),
            gst_percent=Decimal("18"),
            tax_inclusive=True,
        )
    )
    assert result.net_amount + result.tax_amount == result.total_amount
    assert result.total_amount == Decimal("118.00")


def test_discount_and_margin_warning() -> None:
    result = price_line(
        _base(
            retail_price=Decimal("100.00"),
            discount_percent=Decimal("50"),
            max_discount_percent=Decimal("10"),
            cost_price=Decimal("80.00"),
            min_margin_percent=Decimal("10"),
        )
    )
    assert result.discount_amount == Decimal("50.00")
    assert any("Discount" in w for w in result.warnings)
    assert any("margin" in w for w in result.warnings)


def test_zero_quantity_rejected() -> None:
    with pytest.raises(ValueError):
        price_line(_base(quantity=Decimal("0")))


@given(
    quantity=st.integers(min_value=1, max_value=1000).map(Decimal),
    unit=st.decimals(min_value=Decimal("1"), max_value=Decimal("10000"), places=2),
    gst=st.sampled_from([Decimal(r) for r in ("0", "5", "12", "18", "28")]),
    discount=st.decimals(min_value=0, max_value=100, places=2, allow_nan=False),
)
def test_totals_are_consistent(
    quantity: Decimal, unit: Decimal, gst: Decimal, discount: Decimal
) -> None:
    result = price_line(
        _base(
            quantity=quantity,
            retail_price=unit,
            gst_percent=gst,
            discount_percent=discount,
        )
    )
    # Net + tax always reconstitutes the total, exactly.
    assert result.net_amount + result.tax_amount == result.total_amount
    # Discount never makes the net exceed the gross.
    assert result.net_amount <= result.gross_before_discount + result.tax_amount
    assert result.discount_amount >= Decimal("0")
