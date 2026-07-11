"""Sales service: finalize a retail invoice atomically.

Flow per finalization:
  1. Idempotency check (replay returns the same invoice, never a duplicate).
  2. Resolve each line's price via the pricing engine (backend is the authority).
  3. Deduct stock via FEFO (posts movements linked to this invoice).
  4. Persist an immutable invoice with a per-line pricing snapshot.
  5. Record payments; derive payment status. Walk-in sales must be fully paid.

The whole thing runs in the caller's transaction: any failure (e.g. insufficient
stock) rolls the entire invoice back — no partial invoices, no phantom stock.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.money import Money
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.modules.catalogue.models import Product
from app.modules.idempotency.service import IdempotencyService
from app.modules.inventory.models import MovementType
from app.modules.inventory.service import InventoryService
from app.modules.numbering.service import NumberingService
from app.modules.payments.models import (
    Payment,
    PaymentAllocation,
    PaymentDirection,
    PaymentMethod,
)
from app.modules.pricing.engine import PriceInput, price_line
from app.modules.sales.models import (
    PaymentStatus,
    SaleChannel,
    SalesInvoice,
    SalesInvoiceItem,
)


@dataclass
class SaleLineInput:
    product_id: uuid.UUID
    base_quantity: Decimal
    discount_percent: Decimal = Decimal("0")


@dataclass
class PaymentInput:
    method: PaymentMethod
    amount: Decimal
    reference: str | None = None


@dataclass
class SaleResult:
    invoice_id: uuid.UUID
    invoice_number: str
    grand_total: Decimal
    paid_amount: Decimal
    payment_status: PaymentStatus
    replayed: bool = False
    warnings: list[str] = field(default_factory=list)


class SalesService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._numbering = NumberingService(session)
        self._inventory = InventoryService(session)
        self._idempotency = IdempotencyService(session)

    async def create_retail_invoice(
        self,
        *,
        organization_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        invoice_date: date,
        lines: list[SaleLineInput],
        payments: list[PaymentInput],
        customer_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
        created_by: uuid.UUID | None = None,
        idempotency_key: str | None = None,
        as_of: date | None = None,
    ) -> SaleResult:
        if not lines:
            raise NotFoundError("An invoice needs at least one line.")

        # 1. Idempotency: replaying a key returns the original invoice.
        if idempotency_key is not None:
            existing = await self._idempotency.find(
                organization_id=organization_id, key=idempotency_key
            )
            if existing is not None and existing.entity_id is not None:
                invoice = await self._session.get(SalesInvoice, existing.entity_id)
                if invoice is not None:
                    return SaleResult(
                        invoice_id=invoice.id,
                        invoice_number=invoice.invoice_number,
                        grand_total=invoice.grand_total,
                        paid_amount=invoice.paid_amount,
                        payment_status=invoice.payment_status,
                        replayed=True,
                    )

        products = await self._load_products(organization_id, [ln.product_id for ln in lines])

        invoice_number = await self._numbering.next_number(
            organization_id=organization_id,
            document_type="sales_invoice",
            branch_id=branch_id,
        )
        invoice = SalesInvoice(
            organization_id=organization_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            customer_id=customer_id,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            channel=SaleChannel.RETAIL,
            created_by=created_by,
        )
        self._session.add(invoice)
        await self._session.flush()

        subtotal = Decimal("0.00")
        discount_total = Decimal("0.00")
        tax_total = Decimal("0.00")
        grand_total = Decimal("0.00")
        warnings: list[str] = []

        # 2 + 3. Price each line and deduct stock (FEFO).
        for line in lines:
            if line.base_quantity <= 0:
                raise BusinessRuleError("Line quantity must be positive.")
            product = products[line.product_id]
            priced = price_line(
                PriceInput(
                    quantity=line.base_quantity,
                    retail_price=product.retail_price,
                    mrp=product.mrp,
                    wholesale_price=product.wholesale_price,
                    gst_percent=product.gst_rate,
                    discount_percent=line.discount_percent,
                )
            )
            warnings.extend(priced.warnings)

            # Deduct stock; movements are linked to this invoice.
            await self._inventory.issue_fefo(
                organization_id=organization_id,
                warehouse_id=warehouse_id,
                product_id=line.product_id,
                base_quantity=line.base_quantity,
                movement_type=MovementType.RETAIL_SALE,
                branch_id=branch_id,
                source_document_type="sales_invoice",
                source_document_id=invoice.id,
                created_by=created_by,
                as_of=as_of,
            )

            self._session.add(
                SalesInvoiceItem(
                    sales_invoice_id=invoice.id,
                    product_id=line.product_id,
                    base_quantity=line.base_quantity,
                    unit_price=priced.unit_price,
                    price_source=priced.source.value,
                    discount_percent=line.discount_percent,
                    discount_amount=priced.discount_amount,
                    taxable_value=priced.net_amount,
                    gst_rate=product.gst_rate,
                    tax_amount=priced.tax_amount,
                    line_total=priced.total_amount,
                )
            )
            subtotal += priced.net_amount
            discount_total += priced.discount_amount
            tax_total += priced.tax_amount
            grand_total += priced.total_amount

        # 4. Finalize invoice totals.
        invoice.subtotal = Money(subtotal)
        invoice.discount_total = Money(discount_total)
        invoice.tax_total = Money(tax_total)
        invoice.grand_total = Money(grand_total)

        # 5. Payments + status.
        paid_amount = Money(sum((p.amount for p in payments), Decimal("0")))
        if paid_amount > invoice.grand_total:
            raise BusinessRuleError("Paid amount exceeds the invoice total.")
        if customer_id is None and paid_amount < invoice.grand_total:
            raise BusinessRuleError(
                "Walk-in sales must be paid in full.", code="walk_in_credit_not_allowed"
            )

        for p in payments:
            payment = Payment(
                organization_id=organization_id,
                branch_id=branch_id,
                customer_id=customer_id,
                direction=PaymentDirection.INBOUND,
                method=p.method,
                amount=Money(p.amount),
                reference=p.reference,
                created_by=created_by,
            )
            self._session.add(payment)
            await self._session.flush()
            self._session.add(
                PaymentAllocation(
                    payment_id=payment.id,
                    sales_invoice_id=invoice.id,
                    amount=Money(p.amount),
                )
            )

        invoice.paid_amount = paid_amount
        invoice.payment_status = self._derive_status(paid_amount, invoice.grand_total)
        await self._session.flush()

        if idempotency_key is not None:
            await self._idempotency.record(
                organization_id=organization_id,
                key=idempotency_key,
                endpoint="sales.create_retail_invoice",
                entity_type="sales_invoice",
                entity_id=invoice.id,
            )

        return SaleResult(
            invoice_id=invoice.id,
            invoice_number=invoice.invoice_number,
            grand_total=invoice.grand_total,
            paid_amount=invoice.paid_amount,
            payment_status=invoice.payment_status,
            warnings=warnings,
        )

    @staticmethod
    def _derive_status(paid: Decimal, total: Decimal) -> PaymentStatus:
        if paid >= total and total > 0:
            return PaymentStatus.PAID
        if paid > 0:
            return PaymentStatus.PARTIAL
        return PaymentStatus.CREDIT

    async def _load_products(
        self, organization_id: uuid.UUID, product_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, Product]:
        result = await self._session.execute(
            select(Product).where(
                Product.organization_id == organization_id,
                Product.id.in_(product_ids),
            )
        )
        products = {p.id: p for p in result.scalars().all()}
        missing = set(product_ids) - set(products)
        if missing:
            raise NotFoundError(f"Unknown product(s): {', '.join(str(m) for m in missing)}")
        return products
