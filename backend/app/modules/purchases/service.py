"""Purchase service: purchase orders, goods receipt, purchase invoices.

Goods receipt is the integration point with inventory: each received line posts a
PURCHASE_RECEIPT movement to the append-only ledger (via InventoryService) and
records the computed landed unit cost. Purchase invoices are guarded against
duplicate supplier bills.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.inventory.models import Batch, MovementType
from app.modules.inventory.service import InventoryService
from app.modules.numbering.service import NumberingService
from app.modules.purchases.landed_cost import PurchaseLineInput, compute_landed_cost
from app.modules.purchases.models import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseInvoice,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
)


@dataclass
class POLineInput:
    product_id: uuid.UUID
    ordered_base_quantity: Decimal
    unit_rate: Decimal
    trade_discount_percent: Decimal = Decimal("0")
    gst_rate: Decimal = Decimal("0")


@dataclass
class ReceiptLineInput:
    purchase_order_item_id: uuid.UUID | None
    product_id: uuid.UUID
    received_base_quantity: Decimal
    unit_rate: Decimal
    free_base_quantity: Decimal = Decimal("0")
    trade_discount_percent: Decimal = Decimal("0")
    batch_number: str | None = None
    expiry_date: date | None = None
    manufacture_date: date | None = None


@dataclass
class ReceiptCharges:
    freight: Decimal = Decimal("0")
    loading: Decimal = Decimal("0")
    other_charges: Decimal = Decimal("0")


@dataclass
class GoodsReceiptResult:
    goods_receipt_id: uuid.UUID
    grn_number: str
    landed_unit_costs: dict[str, Decimal] = field(default_factory=dict)


class PurchaseService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._numbering = NumberingService(session)
        self._inventory = InventoryService(session)

    async def create_purchase_order(
        self,
        *,
        organization_id: uuid.UUID,
        supplier_id: uuid.UUID,
        order_date: date,
        lines: list[POLineInput],
        branch_id: uuid.UUID | None = None,
        expected_date: date | None = None,
        charges: ReceiptCharges | None = None,
    ) -> PurchaseOrder:
        if not lines:
            raise NotFoundError("A purchase order needs at least one line.")
        charges = charges or ReceiptCharges()
        po_number = await self._numbering.next_number(
            organization_id=organization_id,
            document_type="purchase_order",
            branch_id=branch_id,
        )
        po = PurchaseOrder(
            organization_id=organization_id,
            branch_id=branch_id,
            supplier_id=supplier_id,
            po_number=po_number,
            status=PurchaseOrderStatus.CONFIRMED,
            order_date=order_date,
            expected_date=expected_date,
            freight=charges.freight,
            loading=charges.loading,
            other_charges=charges.other_charges,
        )
        self._session.add(po)
        await self._session.flush()
        for line in lines:
            self._session.add(
                PurchaseOrderItem(
                    purchase_order_id=po.id,
                    product_id=line.product_id,
                    ordered_base_quantity=line.ordered_base_quantity,
                    unit_rate=line.unit_rate,
                    trade_discount_percent=line.trade_discount_percent,
                    gst_rate=line.gst_rate,
                )
            )
        await self._session.flush()
        return po

    async def receive_goods(
        self,
        *,
        organization_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        supplier_id: uuid.UUID,
        receipt_date: date,
        lines: list[ReceiptLineInput],
        purchase_order_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
        charges: ReceiptCharges | None = None,
        created_by: uuid.UUID | None = None,
    ) -> GoodsReceiptResult:
        """Receive stock: create GRN, capture batches, post ledger movements."""
        if not lines:
            raise NotFoundError("A goods receipt needs at least one line.")
        charges = charges or ReceiptCharges()

        grn_number = await self._numbering.next_number(
            organization_id=organization_id,
            document_type="goods_receipt",
            branch_id=branch_id,
        )
        grn = GoodsReceipt(
            organization_id=organization_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            supplier_id=supplier_id,
            purchase_order_id=purchase_order_id,
            grn_number=grn_number,
            receipt_date=receipt_date,
        )
        self._session.add(grn)
        await self._session.flush()

        # Compute landed unit cost per line (discounts + apportioned overheads).
        cost_inputs = [
            PurchaseLineInput(
                line_id=str(index),
                billed_quantity=line.received_base_quantity,
                free_quantity=line.free_base_quantity,
                unit_rate=line.unit_rate,
                trade_discount_percent=line.trade_discount_percent,
            )
            for index, line in enumerate(lines)
        ]
        landed = compute_landed_cost(
            cost_inputs,
            freight=charges.freight,
            loading=charges.loading,
            other_charges=charges.other_charges,
        )
        landed_by_line = {ln.line_id: ln.landed_unit_cost for ln in landed.lines}

        result = GoodsReceiptResult(goods_receipt_id=grn.id, grn_number=grn_number)
        for index, line in enumerate(lines):
            batch_id = await self._resolve_batch(organization_id=organization_id, line=line)
            total_qty = line.received_base_quantity + line.free_base_quantity
            posted = await self._inventory.post_movement(
                organization_id=organization_id,
                warehouse_id=warehouse_id,
                product_id=line.product_id,
                movement_type=MovementType.PURCHASE_RECEIPT,
                base_quantity=total_qty,
                batch_id=batch_id,
                branch_id=branch_id,
                source_document_type="goods_receipt",
                source_document_id=grn.id,
                created_by=created_by,
            )
            unit_cost = landed_by_line[str(index)]
            self._session.add(
                GoodsReceiptItem(
                    goods_receipt_id=grn.id,
                    product_id=line.product_id,
                    batch_id=batch_id,
                    stock_movement_id=posted.movement_id,
                    received_base_quantity=line.received_base_quantity,
                    free_base_quantity=line.free_base_quantity,
                    unit_rate=line.unit_rate,
                    landed_unit_cost=unit_cost,
                )
            )
            result.landed_unit_costs[str(line.product_id)] = unit_cost
            if line.purchase_order_item_id is not None:
                await self._apply_po_receipt(line.purchase_order_item_id, total_qty)

        await self._session.flush()
        if purchase_order_id is not None:
            await self._refresh_po_status(purchase_order_id)
        return result

    async def record_purchase_invoice(
        self,
        *,
        organization_id: uuid.UUID,
        supplier_id: uuid.UUID,
        supplier_invoice_number: str,
        invoice_date: date,
        goods_value: Decimal,
        tax_amount: Decimal,
        goods_receipt_id: uuid.UUID | None = None,
    ) -> PurchaseInvoice:
        invoice = PurchaseInvoice(
            organization_id=organization_id,
            supplier_id=supplier_id,
            goods_receipt_id=goods_receipt_id,
            supplier_invoice_number=supplier_invoice_number,
            invoice_date=invoice_date,
            goods_value=goods_value,
            tax_amount=tax_amount,
            total_amount=goods_value + tax_amount,
        )
        self._session.add(invoice)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                "This supplier invoice number is already recorded.",
                code="duplicate_supplier_invoice",
            ) from exc
        return invoice

    async def _resolve_batch(
        self, *, organization_id: uuid.UUID, line: ReceiptLineInput
    ) -> uuid.UUID | None:
        if not line.batch_number:
            return None
        existing = (
            (
                await self._session.execute(
                    select(Batch).where(
                        Batch.product_id == line.product_id,
                        Batch.batch_number == line.batch_number,
                    )
                )
            )
            .scalars()
            .first()
        )
        if existing is not None:
            return existing.id
        batch = Batch(
            organization_id=organization_id,
            product_id=line.product_id,
            batch_number=line.batch_number,
            expiry_date=line.expiry_date,
            manufacture_date=line.manufacture_date,
        )
        self._session.add(batch)
        await self._session.flush()
        return batch.id

    async def _apply_po_receipt(self, po_item_id: uuid.UUID, quantity: Decimal) -> None:
        item = await self._session.get(PurchaseOrderItem, po_item_id)
        if item is not None:
            item.received_base_quantity = item.received_base_quantity + quantity

    async def _refresh_po_status(self, purchase_order_id: uuid.UUID) -> None:
        po = await self._session.get(PurchaseOrder, purchase_order_id)
        if po is None:
            return
        items = (
            (
                await self._session.execute(
                    select(PurchaseOrderItem).where(
                        PurchaseOrderItem.purchase_order_id == purchase_order_id
                    )
                )
            )
            .scalars()
            .all()
        )
        if items and all(i.received_base_quantity >= i.ordered_base_quantity for i in items):
            po.status = PurchaseOrderStatus.RECEIVED
        elif any(i.received_base_quantity > 0 for i in items):
            po.status = PurchaseOrderStatus.PARTIALLY_RECEIVED
