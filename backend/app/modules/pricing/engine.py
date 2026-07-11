"""Centralised pricing engine — the single authority for line pricing.

Resolution priority (highest first):
  1. contract / customer-specific price
  2. customer price-list price
  3. quantity-slab price
  4. wholesale price (when qty >= min wholesale qty)
  5. retail price
  6. MRP fallback

The engine also computes a decimal-safe line total with discount and tax, and
surfaces margin/discount warnings. It never mutates inputs and does no I/O, so it
is exhaustively property-testable and reused by POS, wholesale and returns alike.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from decimal import Decimal

from app.common.money import (
    Money,
    apply_percentage_discount,
    split_tax_from_inclusive,
    tax_on_exclusive,
)


class PriceSource(str, enum.Enum):
    CONTRACT = "contract"
    CUSTOMER_PRICE_LIST = "customer_price_list"
    QUANTITY_SLAB = "quantity_slab"
    WHOLESALE = "wholesale"
    RETAIL = "retail"
    MRP = "mrp"


@dataclass(frozen=True)
class QuantitySlab:
    min_quantity: Decimal
    unit_price: Decimal


@dataclass(frozen=True)
class PriceInput:
    quantity: Decimal
    retail_price: Decimal
    mrp: Decimal
    wholesale_price: Decimal | None = None
    min_wholesale_quantity: Decimal | None = None
    contract_price: Decimal | None = None
    price_list_price: Decimal | None = None
    quantity_slabs: tuple[QuantitySlab, ...] = ()
    gst_percent: Decimal = Decimal("0")
    tax_inclusive: bool = False
    discount_percent: Decimal = Decimal("0")
    cost_price: Decimal | None = None
    min_margin_percent: Decimal | None = None
    max_discount_percent: Decimal | None = None


@dataclass(frozen=True)
class PriceResult:
    unit_price: Decimal
    source: PriceSource
    quantity: Decimal
    gross_before_discount: Decimal
    discount_amount: Decimal
    net_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    warnings: list[str] = field(default_factory=list)


def _best_slab(slabs: tuple[QuantitySlab, ...], quantity: Decimal) -> Decimal | None:
    eligible = [s for s in slabs if quantity >= s.min_quantity]
    if not eligible:
        return None
    # The slab with the highest satisfied threshold wins (deepest volume tier).
    return max(eligible, key=lambda s: s.min_quantity).unit_price


def resolve_unit_price(data: PriceInput) -> tuple[Decimal, PriceSource]:
    """Resolve the unit price by priority, returning (price, source)."""
    if data.contract_price is not None:
        return Money(data.contract_price), PriceSource.CONTRACT
    if data.price_list_price is not None:
        return Money(data.price_list_price), PriceSource.CUSTOMER_PRICE_LIST

    slab_price = _best_slab(data.quantity_slabs, data.quantity)
    if slab_price is not None:
        return Money(slab_price), PriceSource.QUANTITY_SLAB

    if (
        data.wholesale_price is not None
        and data.min_wholesale_quantity is not None
        and data.quantity >= data.min_wholesale_quantity
    ):
        return Money(data.wholesale_price), PriceSource.WHOLESALE

    if data.retail_price > 0:
        return Money(data.retail_price), PriceSource.RETAIL
    return Money(data.mrp), PriceSource.MRP


def price_line(data: PriceInput) -> PriceResult:
    """Resolve price and compute a decimal-safe, tax-aware line total."""
    if data.quantity <= 0:
        raise ValueError("Quantity must be positive.")

    unit_price, source = resolve_unit_price(data)
    warnings: list[str] = []

    gross = Money(unit_price * data.quantity)
    net_before_tax = apply_percentage_discount(gross, data.discount_percent)
    discount_amount = Money(gross - net_before_tax)

    if data.tax_inclusive:
        net_amount, tax_amount = split_tax_from_inclusive(net_before_tax, data.gst_percent)
    else:
        net_amount = net_before_tax
        tax_amount = tax_on_exclusive(net_before_tax, data.gst_percent)

    total_amount = Money(net_amount + tax_amount)

    # Advisory checks (do not block; the caller decides based on permissions).
    if data.max_discount_percent is not None and data.discount_percent > data.max_discount_percent:
        warnings.append(
            f"Discount {data.discount_percent}% exceeds max " f"{data.max_discount_percent}%."
        )
    if data.cost_price is not None and data.min_margin_percent is not None:
        effective_unit = net_amount / data.quantity if data.quantity else Decimal("0")
        min_price = Money(
            data.cost_price * (Decimal("100") + data.min_margin_percent) / Decimal("100")
        )
        if effective_unit < min_price:
            warnings.append("Effective price is below the minimum margin threshold.")

    return PriceResult(
        unit_price=unit_price,
        source=source,
        quantity=data.quantity,
        gross_before_discount=gross,
        discount_amount=discount_amount,
        net_amount=net_amount,
        tax_amount=tax_amount,
        total_amount=total_amount,
        warnings=warnings,
    )
