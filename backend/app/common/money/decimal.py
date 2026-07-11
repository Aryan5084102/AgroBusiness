"""Decimal money primitives.

All monetary amounts are :class:`decimal.Decimal` quantised to 2 places using
banker-free ``ROUND_HALF_UP`` (the convention Indian retail invoices expect).
Tax and discount helpers are centralised so no page re-implements the maths.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import TypeAlias

Numeric: TypeAlias = Decimal | int | str

CURRENCY_QUANTUM = Decimal("0.01")
RATE_QUANTUM = Decimal("0.0001")
ZERO = Decimal("0.00")


def Money(value: Numeric) -> Decimal:
    """Coerce a value to a currency-quantised Decimal.

    Floats are rejected: constructing a Decimal from float introduces binary
    rounding error, which is exactly what this module exists to prevent.
    """
    if isinstance(value, float):
        raise TypeError("Refusing to build Money from float; pass Decimal/str/int.")
    return quantize_money(Decimal(value))


def quantize_money(amount: Decimal) -> Decimal:
    """Round to 2 decimal places, half-up."""
    return amount.quantize(CURRENCY_QUANTUM, rounding=ROUND_HALF_UP)


def quantize_rate(rate: Decimal) -> Decimal:
    """Round a ratio/percentage-derived factor to 4 places."""
    return rate.quantize(RATE_QUANTUM, rounding=ROUND_HALF_UP)


def apply_percentage_discount(amount: Decimal, percent: Decimal) -> Decimal:
    """Return ``amount`` reduced by ``percent`` (0-100), quantised to currency."""
    if percent < 0 or percent > 100:
        raise ValueError("Discount percent must be between 0 and 100.")
    factor = (Decimal(100) - percent) / Decimal(100)
    return quantize_money(amount * factor)


def tax_on_exclusive(amount: Decimal, gst_percent: Decimal) -> Decimal:
    """Tax amount for a tax-*exclusive* base value."""
    if gst_percent < 0:
        raise ValueError("GST percent cannot be negative.")
    return quantize_money(amount * gst_percent / Decimal(100))


def split_tax_from_inclusive(gross: Decimal, gst_percent: Decimal) -> tuple[Decimal, Decimal]:
    """Split a tax-*inclusive* gross into (net, tax).

    net = gross * 100 / (100 + gst);  tax = gross - net. Guarantees net + tax
    reconstitutes exactly to ``gross`` after quantisation.
    """
    if gst_percent < 0:
        raise ValueError("GST percent cannot be negative.")
    net = quantize_money(gross * Decimal(100) / (Decimal(100) + gst_percent))
    tax = quantize_money(gross - net)
    return net, tax


def allocate(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Split ``total`` across ``weights`` with no rounding leakage.

    Uses the largest-remainder method: each share is floored to currency and the
    leftover pennies are distributed to the largest fractional remainders. The
    returned shares always sum exactly to ``total``.
    """
    if not weights:
        raise ValueError("Cannot allocate across zero weights.")
    if any(w < 0 for w in weights):
        raise ValueError("Allocation weights must be non-negative.")

    weight_sum = sum(weights)
    if weight_sum == 0:
        # Degenerate: put everything on the first share.
        shares = [ZERO for _ in weights]
        shares[0] = quantize_money(total)
        return shares

    raw = [total * w / weight_sum for w in weights]
    floored = [r.quantize(CURRENCY_QUANTUM, rounding="ROUND_DOWN") for r in raw]
    remainder = quantize_money(total - sum(floored))

    # Number of pennies still to distribute.
    pennies = int((remainder / CURRENCY_QUANTUM).to_integral_value())
    fractional = sorted(
        range(len(weights)),
        key=lambda i: (raw[i] - floored[i]),
        reverse=True,
    )
    for k in range(pennies):
        floored[fractional[k % len(floored)]] += CURRENCY_QUANTUM
    return [quantize_money(s) for s in floored]
