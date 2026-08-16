"""Inventory service: post movements to the ledger and update balances atomically.

All stock changes go through :meth:`post_movement`, keeping the ledger the single
source of truth. Outbound issue uses FEFO across batches and refuses to oversell
(the DB also enforces ``on_hand >= 0`` as a backstop).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessRuleError
from app.modules.inventory.fefo import (
    Allocation,
    InsufficientStockError,
    allocate_fefo,
)
from app.modules.inventory.models import (
    MovementType,
    StockMovement,
    movement_direction,
)
from app.modules.inventory.repository import InventoryRepository


@dataclass
class PostedMovement:
    movement_id: uuid.UUID
    batch_id: uuid.UUID | None
    base_quantity: Decimal


class InventoryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = InventoryRepository(session)

    async def post_movement(
        self,
        *,
        organization_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        product_id: uuid.UUID,
        movement_type: MovementType,
        base_quantity: Decimal,
        batch_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
        source_document_type: str | None = None,
        source_document_id: uuid.UUID | None = None,
        reason: str | None = None,
        created_by: uuid.UUID | None = None,
        signed_quantity: Decimal | None = None,
    ) -> PostedMovement:
        """Post a single ledger movement and apply its balance delta.

        ``base_quantity`` is the positive magnitude; direction is derived from the
        movement type. For ADJUSTMENT/RECONCILIATION pass ``signed_quantity``.
        """
        direction = movement_direction(movement_type)
        if direction == 0:
            if signed_quantity is None or signed_quantity == 0:
                raise BusinessRuleError("Adjustment movements require a non-zero signed quantity.")
            delta = signed_quantity
        else:
            if base_quantity <= 0:
                raise BusinessRuleError("Quantity must be positive.")
            delta = base_quantity * direction

        # Guard against overselling this specific balance row (locked).
        if delta < 0:
            balance = await self._repo.get_balance(
                warehouse_id=warehouse_id, product_id=product_id, batch_id=batch_id
            )
            on_hand = balance.on_hand if balance else Decimal("0")
            if on_hand + delta < 0:
                raise BusinessRuleError(
                    "Insufficient stock for this movement.",
                    code="insufficient_stock",
                )

        movement = StockMovement(
            organization_id=organization_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            batch_id=batch_id,
            movement_type=movement_type,
            base_quantity=delta,
            source_document_type=source_document_type,
            source_document_id=source_document_id,
            reason=reason,
            created_by=created_by,
        )
        await self._repo.add_movement(movement)
        await self._repo.upsert_balance_delta(
            organization_id=organization_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            batch_id=batch_id,
            delta=delta,
        )
        return PostedMovement(movement_id=movement.id, batch_id=batch_id, base_quantity=delta)

    async def receive(
        self,
        *,
        organization_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        product_id: uuid.UUID,
        base_quantity: Decimal,
        batch_id: uuid.UUID | None = None,
        movement_type: MovementType = MovementType.PURCHASE_RECEIPT,
        **kwargs: object,
    ) -> PostedMovement:
        return await self.post_movement(
            organization_id=organization_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            movement_type=movement_type,
            base_quantity=base_quantity,
            batch_id=batch_id,
            **kwargs,  # type: ignore[arg-type]
        )

    async def available(
        self,
        *,
        warehouse_id: uuid.UUID,
        product_id: uuid.UUID,
        as_of: date | None = None,
    ) -> Decimal:
        """Sellable quantity now: sum of non-expired (on_hand - reserved) per batch."""
        as_of = as_of or datetime.now(tz=timezone.utc).date()
        rows = await self._repo.batch_availability(
            warehouse_id=warehouse_id, product_id=product_id, lock=False
        )
        return sum(
            (
                b.available
                for b in rows
                if b.available > 0 and (b.expiry_date is None or b.expiry_date > as_of)
            ),
            Decimal("0"),
        )

    async def issue_fefo(
        self,
        *,
        organization_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        product_id: uuid.UUID,
        base_quantity: Decimal,
        movement_type: MovementType = MovementType.RETAIL_SALE,
        branch_id: uuid.UUID | None = None,
        source_document_type: str | None = None,
        source_document_id: uuid.UUID | None = None,
        created_by: uuid.UUID | None = None,
        as_of: date | None = None,
    ) -> list[PostedMovement]:
        """Deduct ``base_quantity`` using FEFO; one ledger movement per batch."""
        as_of = as_of or datetime.now(tz=timezone.utc).date()
        availability = await self._repo.batch_availability(
            warehouse_id=warehouse_id, product_id=product_id
        )
        try:
            allocations: list[Allocation] = allocate_fefo(availability, base_quantity, as_of=as_of)
        except InsufficientStockError as exc:
            raise BusinessRuleError(str(exc), code="insufficient_stock") from exc

        posted: list[PostedMovement] = []
        for alloc in allocations:
            posted.append(
                await self.post_movement(
                    organization_id=organization_id,
                    warehouse_id=warehouse_id,
                    product_id=product_id,
                    movement_type=movement_type,
                    base_quantity=alloc.quantity,
                    batch_id=alloc.batch_id,
                    branch_id=branch_id,
                    source_document_type=source_document_type,
                    source_document_id=source_document_id,
                    created_by=created_by,
                )
            )
        return posted

    async def adjust(
        self,
        *,
        organization_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        product_id: uuid.UUID,
        signed_quantity: Decimal,
        movement_type: MovementType,
        reason: str,
        branch_id: uuid.UUID | None = None,
        created_by: uuid.UUID | None = None,
        as_of: date | None = None,
    ) -> list[PostedMovement]:
        """Post a stock correction, taking any reduction from batches FEFO.

        Batch-tracked stock lives on per-batch balance rows, so a bare negative
        movement against the un-batched row would fail even when the product is
        clearly on the shelf. Reductions therefore allocate across batches the
        same way a sale does; additions land on the un-batched row (a specific
        batch is established when goods are received, not when a count is fixed).
        """
        if signed_quantity == 0:
            raise BusinessRuleError("Adjustment quantity cannot be zero.")
        direction = movement_direction(movement_type)
        magnitude = abs(signed_quantity)

        if signed_quantity > 0:
            if direction < 0:
                raise BusinessRuleError(
                    f"{movement_type.value} can only reduce stock.",
                    code="movement_direction_mismatch",
                )
            return [
                await self.post_movement(
                    organization_id=organization_id,
                    warehouse_id=warehouse_id,
                    product_id=product_id,
                    movement_type=movement_type,
                    base_quantity=magnitude,
                    branch_id=branch_id,
                    reason=reason,
                    created_by=created_by,
                    signed_quantity=magnitude if direction == 0 else None,
                )
            ]

        as_of = as_of or datetime.now(tz=timezone.utc).date()
        availability = await self._repo.batch_availability(
            warehouse_id=warehouse_id, product_id=product_id
        )
        try:
            allocations = allocate_fefo(availability, magnitude, as_of=as_of)
        except InsufficientStockError as exc:
            raise BusinessRuleError(str(exc), code="insufficient_stock") from exc

        return [
            await self.post_movement(
                organization_id=organization_id,
                warehouse_id=warehouse_id,
                product_id=product_id,
                movement_type=movement_type,
                base_quantity=alloc.quantity,
                batch_id=alloc.batch_id,
                branch_id=branch_id,
                reason=reason,
                created_by=created_by,
                signed_quantity=-alloc.quantity if direction == 0 else None,
            )
            for alloc in allocations
        ]

    async def reserve(
        self,
        *,
        organization_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        product_id: uuid.UUID,
        base_quantity: Decimal,
        as_of: date | None = None,
    ) -> None:
        """Reserve available stock (FEFO) by increasing ``reserved`` per batch.

        Does not move stock — it makes it unavailable to other orders. Raises when
        available (on_hand - reserved) cannot cover the request.
        """
        if base_quantity <= 0:
            raise BusinessRuleError("Reservation quantity must be positive.")
        as_of = as_of or datetime.now(tz=timezone.utc).date()
        availability = await self._repo.batch_availability(
            warehouse_id=warehouse_id, product_id=product_id
        )
        try:
            allocations = allocate_fefo(availability, base_quantity, as_of=as_of)
        except InsufficientStockError as exc:
            raise BusinessRuleError(str(exc), code="insufficient_stock_to_reserve") from exc
        for alloc in allocations:
            await self._repo.adjust_reserved(
                warehouse_id=warehouse_id,
                product_id=product_id,
                batch_id=alloc.batch_id,
                delta=alloc.quantity,
            )

    async def release_reservation(
        self,
        *,
        warehouse_id: uuid.UUID,
        product_id: uuid.UUID,
        base_quantity: Decimal,
    ) -> None:
        """Release a previously-made reservation (earliest-expiry batches first)."""
        if base_quantity <= 0:
            raise BusinessRuleError("Release quantity must be positive.")
        reserved = await self._repo.reserved_balances(
            warehouse_id=warehouse_id, product_id=product_id
        )
        remaining = base_quantity
        for bal in sorted(
            reserved,
            key=lambda b: (b.expiry_date is None, b.expiry_date or date.max),
        ):
            if remaining <= 0:
                break
            take = min(bal.available, remaining)
            await self._repo.adjust_reserved(
                warehouse_id=warehouse_id,
                product_id=product_id,
                batch_id=bal.batch_id,
                delta=-take,
            )
            remaining -= take
        if remaining > 0:
            raise BusinessRuleError("Release exceeds the reserved quantity.", code="over_release")

    async def transfer(
        self,
        *,
        organization_id: uuid.UUID,
        from_warehouse_id: uuid.UUID,
        to_warehouse_id: uuid.UUID,
        product_id: uuid.UUID,
        base_quantity: Decimal,
        batch_id: uuid.UUID | None = None,
        created_by: uuid.UUID | None = None,
    ) -> None:
        """Move stock between warehouses as a paired OUT/IN in one transaction."""
        await self.post_movement(
            organization_id=organization_id,
            warehouse_id=from_warehouse_id,
            product_id=product_id,
            movement_type=MovementType.TRANSFER_OUT,
            base_quantity=base_quantity,
            batch_id=batch_id,
            created_by=created_by,
        )
        await self.post_movement(
            organization_id=organization_id,
            warehouse_id=to_warehouse_id,
            product_id=product_id,
            movement_type=MovementType.TRANSFER_IN,
            base_quantity=base_quantity,
            batch_id=batch_id,
            created_by=created_by,
        )
