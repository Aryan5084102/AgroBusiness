"""Unit conversion between packaging units and the smallest base unit.

Stock is stored internally in the base unit (e.g. grams, millilitres, pieces).
A product may be purchased in one unit (carton) and sold in another (bottle);
both convert through a factor expressing "how many base units in one of me".

Example: base = bottle. carton factor = 20  → 3 cartons = 60 bottles.
         base = gram.   bag factor = 50000 → 2 bags   = 100000 g.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal


@dataclass(frozen=True)
class UnitConversion:
    """A named unit and how many base units it contains.

    ``factor`` must be a positive Decimal. Quantities are Decimal to avoid float
    drift; base quantities are integers when the base unit is indivisible, but we
    keep Decimal to support divisible bases (e.g. litres to 3 dp).
    """

    unit_code: str
    base_factor: Decimal

    def __post_init__(self) -> None:
        if self.base_factor <= 0:
            raise ValueError("base_factor must be positive.")


def to_base_quantity(quantity: Decimal, conversion: UnitConversion) -> Decimal:
    """Convert a quantity expressed in ``conversion``'s unit into base units."""
    if quantity < 0:
        raise ValueError("Quantity cannot be negative.")
    return quantity * conversion.base_factor


def to_display_quantity(
    base_quantity: Decimal,
    conversion: UnitConversion,
    *,
    fractional_digits: int = 3,
) -> Decimal:
    """Convert base units back into ``conversion``'s unit for display.

    Rounds DOWN so displayed sellable quantity never overstates real stock.
    """
    if base_quantity < 0:
        raise ValueError("Base quantity cannot be negative.")
    quantum = Decimal(1).scaleb(-fractional_digits)
    return (base_quantity / conversion.base_factor).quantize(quantum, rounding=ROUND_DOWN)
