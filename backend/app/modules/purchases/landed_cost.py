"""Landed-cost computation — pure domain logic.

Landed cost is the true per-unit cost of received goods after trade/cash
discounts, free (bonus) quantities, and apportioned overheads (freight, loading,
other charges). Overheads are allocated across lines by taxable value using the
no-leakage largest-remainder method from the money kernel.

The entered purchase rate is preserved separately by the caller; this module
computes the *effective* landed cost so margins and valuation are correct.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.common.money import Money, allocate, apply_percentage_discount


@dataclass(frozen=True)
class PurchaseLineInput:
    """One received line before overhead apportionment.

    ``billed_quantity`` is charged; ``free_quantity`` is received at no cost. The
    landed cost per unit is spread across billed + free units (the free stock is
    real inventory and must carry a cost for valuation).
    """

    line_id: str
    billed_quantity: Decimal
    free_quantity: Decimal
    unit_rate: Decimal
    trade_discount_percent: Decimal = Decimal("0")
    cash_discount_percent: Decimal = Decimal("0")


@dataclass(frozen=True)
class LandedCostLine:
    line_id: str
    net_line_value: Decimal
    allocated_overhead: Decimal
    total_landed_value: Decimal
    total_units: Decimal
    landed_unit_cost: Decimal


@dataclass(frozen=True)
class LandedCostResult:
    lines: list[LandedCostLine]
    goods_value: Decimal
    total_overhead: Decimal
    grand_total: Decimal


def _net_line_value(line: PurchaseLineInput) -> Decimal:
    gross = Money(line.unit_rate * line.billed_quantity)
    after_trade = apply_percentage_discount(gross, line.trade_discount_percent)
    after_cash = apply_percentage_discount(after_trade, line.cash_discount_percent)
    return after_cash


def compute_landed_cost(
    lines: list[PurchaseLineInput],
    *,
    freight: Decimal = Decimal("0"),
    loading: Decimal = Decimal("0"),
    other_charges: Decimal = Decimal("0"),
) -> LandedCostResult:
    """Compute per-line landed unit cost after discounts + apportioned overheads."""
    if not lines:
        raise ValueError("At least one purchase line is required.")
    for line in lines:
        if line.billed_quantity <= 0:
            raise ValueError("Billed quantity must be positive.")
        if line.free_quantity < 0:
            raise ValueError("Free quantity cannot be negative.")

    net_values = [_net_line_value(line) for line in lines]
    goods_value = Money(sum(net_values, Decimal("0")))
    total_overhead = Money(freight + loading + other_charges)

    # Apportion overheads across lines weighted by net taxable value (no leakage).
    overhead_shares = allocate(total_overhead, net_values)

    result_lines: list[LandedCostLine] = []
    for line, net_value, overhead in zip(lines, net_values, overhead_shares, strict=True):
        total_units = line.billed_quantity + line.free_quantity
        total_landed = Money(net_value + overhead)
        # Divide by ALL received units (billed + free) so free stock carries cost.
        unit_cost = (total_landed / total_units).quantize(Decimal("0.0001"))
        result_lines.append(
            LandedCostLine(
                line_id=line.line_id,
                net_line_value=net_value,
                allocated_overhead=overhead,
                total_landed_value=total_landed,
                total_units=total_units,
                landed_unit_cost=unit_cost,
            )
        )

    return LandedCostResult(
        lines=result_lines,
        goods_value=goods_value,
        total_overhead=total_overhead,
        grand_total=Money(goods_value + total_overhead),
    )
