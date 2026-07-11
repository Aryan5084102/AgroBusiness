"""Decimal-safe money utilities. No float ever touches money."""

from app.common.money.decimal import (
    ZERO,
    Money,
    allocate,
    apply_percentage_discount,
    quantize_money,
    split_tax_from_inclusive,
    tax_on_exclusive,
)

__all__ = [
    "ZERO",
    "Money",
    "allocate",
    "apply_percentage_discount",
    "quantize_money",
    "split_tax_from_inclusive",
    "tax_on_exclusive",
]
