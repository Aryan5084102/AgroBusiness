"""Wholesale service: quotations, sales orders, credit control, dispatch→invoice.

Order confirmation validates the customer's credit limit, then reserves stock.
Dispatch releases the reservation, deducts stock via FEFO, and produces an
immutable wholesale invoice (on credit) reusing the sales-invoice model.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.money import Money
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.modules.accounting.service import AccountingService, JournalLine
from app.modules.catalogue.models import Product
from app.modules.customers.models import Customer
from app.modules.inventory.models import MovementType
from app.modules.inventory.service import InventoryService
from app.modules.numbering.service import NumberingService
from app.modules.pricing.engine import PriceInput, price_line
from app.modules.sales.models import (
    PaymentStatus,
    SaleChannel,
    SalesInvoice,
    SalesInvoiceItem,
)
from app.modules.sales.order_models import (
    SalesOrder,
    SalesOrderItem,
    SalesOrderStatus,
)


@dataclass
class OrderLineInput:
    product_id: uuid.UUID
    base_quantity: Decimal
    discount_percent: Decimal = Decimal("0")


@dataclass
class OrderResult:
    sales_order_id: uuid.UUID
    order_number: str
    status: SalesOrderStatus
    grand_total: Decimal
    warnings: list[str] = field(default_factory=list)


@dataclass
class DispatchResult:
    sales_order_id: uuid.UUID
    sales_invoice_id: uuid.UUID
    invoice_number: str
    grand_total: Decimal


class WholesaleService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._numbering = NumberingService(session)
        self._inventory = InventoryService(session)
        self._accounting = AccountingService(session)

    async def customer_outstanding(self, customer_id: uuid.UUID) -> Decimal:
        """Unpaid balance across the customer's non-paid invoices."""
        result = await self._session.execute(
            select(
                func.coalesce(
                    func.sum(SalesInvoice.grand_total - SalesInvoice.paid_amount),
                    0,
                )
            ).where(
                SalesInvoice.customer_id == customer_id,
                SalesInvoice.payment_status != PaymentStatus.PAID,
            )
        )
        return Decimal(str(result.scalar()))

    async def create_order(
        self,
        *,
        organization_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        customer_id: uuid.UUID,
        order_date: date,
        lines: list[OrderLineInput],
        branch_id: uuid.UUID | None = None,
        salesperson_id: uuid.UUID | None = None,
        is_quotation: bool = False,
        credit_override_approved: bool = False,
        as_of: date | None = None,
    ) -> OrderResult:
        if not lines:
            raise NotFoundError("An order needs at least one line.")
        customer = await self._session.get(Customer, customer_id)
        if customer is None or customer.organization_id != organization_id:
            raise NotFoundError("Unknown customer.")

        products = await self._load_products(organization_id, [ln.product_id for ln in lines])
        doc_type = "sales_order" if not is_quotation else "quotation"
        order_number = await self._numbering.next_number(
            organization_id=organization_id,
            document_type=doc_type,
            branch_id=branch_id,
        )
        status = SalesOrderStatus.QUOTATION if is_quotation else SalesOrderStatus.CONFIRMED
        order = SalesOrder(
            organization_id=organization_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            customer_id=customer_id,
            salesperson_id=salesperson_id,
            order_number=order_number,
            status=status,
            order_date=order_date,
            credit_override_approved=credit_override_approved,
        )
        self._session.add(order)
        await self._session.flush()

        subtotal = Decimal("0.00")
        tax_total = Decimal("0.00")
        grand_total = Decimal("0.00")
        warnings: list[str] = []
        priced_lines: list[tuple[OrderLineInput, object]] = []

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
                    # Wholesale channel: prefer wholesale price when set.
                    min_wholesale_quantity=Decimal("1"),
                    gst_percent=product.gst_rate,
                    discount_percent=line.discount_percent,
                )
            )
            warnings.extend(priced.warnings)
            priced_lines.append((line, priced))
            self._session.add(
                SalesOrderItem(
                    sales_order_id=order.id,
                    product_id=line.product_id,
                    base_quantity=line.base_quantity,
                    unit_price=priced.unit_price,
                    price_source=priced.source.value,
                    discount_percent=line.discount_percent,
                    taxable_value=priced.net_amount,
                    gst_rate=product.gst_rate,
                    tax_amount=priced.tax_amount,
                    line_total=priced.total_amount,
                )
            )
            subtotal += priced.net_amount
            tax_total += priced.tax_amount
            grand_total += priced.total_amount

        order.subtotal = Money(subtotal)
        order.tax_total = Money(tax_total)
        order.grand_total = Money(grand_total)

        if not is_quotation:
            await self._enforce_credit_limit(
                customer=customer,
                order_total=order.grand_total,
                override=credit_override_approved,
            )
            # Reserve stock per line (raises if unavailable).
            for line, _ in priced_lines:
                await self._inventory.reserve(
                    organization_id=organization_id,
                    warehouse_id=warehouse_id,
                    product_id=line.product_id,
                    base_quantity=line.base_quantity,
                    as_of=as_of,
                )
            await self._set_reserved_quantities(order.id)

        await self._session.flush()
        return OrderResult(
            sales_order_id=order.id,
            order_number=order.order_number,
            status=order.status,
            grand_total=order.grand_total,
            warnings=warnings,
        )

    async def dispatch_and_invoice(
        self,
        *,
        organization_id: uuid.UUID,
        sales_order_id: uuid.UUID,
        invoice_date: date,
        created_by: uuid.UUID | None = None,
        as_of: date | None = None,
    ) -> DispatchResult:
        order = await self._session.get(SalesOrder, sales_order_id)
        if order is None or order.organization_id != organization_id:
            raise NotFoundError("Unknown sales order.")
        if order.status != SalesOrderStatus.CONFIRMED:
            raise BusinessRuleError(
                "Only a confirmed order can be dispatched.",
                code="order_not_dispatchable",
            )

        items = list(
            (
                await self._session.execute(
                    select(SalesOrderItem).where(SalesOrderItem.sales_order_id == sales_order_id)
                )
            )
            .scalars()
            .all()
        )

        invoice_number = await self._numbering.next_number(
            organization_id=organization_id,
            document_type="sales_invoice",
            branch_id=order.branch_id,
        )
        invoice = SalesInvoice(
            organization_id=organization_id,
            branch_id=order.branch_id,
            warehouse_id=order.warehouse_id,
            customer_id=order.customer_id,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            channel=SaleChannel.WHOLESALE,
            subtotal=order.subtotal,
            tax_total=order.tax_total,
            grand_total=order.grand_total,
            paid_amount=Decimal("0.00"),
            payment_status=PaymentStatus.CREDIT,
            created_by=created_by,
        )
        self._session.add(invoice)
        await self._session.flush()

        for item in items:
            # Release the reservation, then actually deduct stock (FEFO).
            await self._inventory.release_reservation(
                warehouse_id=order.warehouse_id,
                product_id=item.product_id,
                base_quantity=item.base_quantity,
            )
            await self._inventory.issue_fefo(
                organization_id=organization_id,
                warehouse_id=order.warehouse_id,
                product_id=item.product_id,
                base_quantity=item.base_quantity,
                movement_type=MovementType.WHOLESALE_SALE,
                branch_id=order.branch_id,
                source_document_type="sales_invoice",
                source_document_id=invoice.id,
                created_by=created_by,
                as_of=as_of,
            )
            item.dispatched_quantity = item.base_quantity
            self._session.add(
                SalesInvoiceItem(
                    sales_invoice_id=invoice.id,
                    product_id=item.product_id,
                    base_quantity=item.base_quantity,
                    unit_price=item.unit_price,
                    price_source=item.price_source,
                    discount_percent=item.discount_percent,
                    taxable_value=item.taxable_value,
                    gst_rate=item.gst_rate,
                    tax_amount=item.tax_amount,
                    line_total=item.line_total,
                )
            )

        order.status = SalesOrderStatus.INVOICED
        order.sales_invoice_id = invoice.id
        await self._session.flush()

        # Wholesale always ships on credit: Dr Accounts Receivable, Cr sales + GST.
        if invoice.grand_total > 0:
            lines = [
                JournalLine(account_code="AR", debit=Money(invoice.grand_total)),
                JournalLine(account_code="SALES", credit=Money(invoice.subtotal)),
            ]
            if invoice.tax_total > 0:
                lines.append(
                    JournalLine(account_code="GST_OUTPUT", credit=Money(invoice.tax_total))
                )
            await self._accounting.post(
                organization_id=organization_id,
                entry_date=invoice.invoice_date,
                lines=lines,
                narration=f"Wholesale invoice {invoice.invoice_number}",
                branch_id=order.branch_id,
                source_document_type="sales_invoice",
                source_document_id=invoice.id,
                created_by=created_by,
            )

        return DispatchResult(
            sales_order_id=order.id,
            sales_invoice_id=invoice.id,
            invoice_number=invoice.invoice_number,
            grand_total=invoice.grand_total,
        )

    async def _enforce_credit_limit(
        self, *, customer: Customer, order_total: Decimal, override: bool
    ) -> None:
        if override or customer.credit_limit <= 0:
            # No limit configured, or an authorised override was supplied.
            return
        outstanding = await self.customer_outstanding(customer.id)
        projected = outstanding + order_total
        if projected > customer.credit_limit:
            raise BusinessRuleError(
                "Credit limit exceeded. Approval required to proceed.",
                code="credit_limit_exceeded",
            )

    async def _set_reserved_quantities(self, order_id: uuid.UUID) -> None:
        items = (
            (
                await self._session.execute(
                    select(SalesOrderItem).where(SalesOrderItem.sales_order_id == order_id)
                )
            )
            .scalars()
            .all()
        )
        for item in items:
            item.reserved_quantity = item.base_quantity

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
