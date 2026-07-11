"""Data access for inventory: balances and batch availability."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.fefo import BatchAvailability
from app.modules.inventory.models import Batch, StockBalance, StockMovement


class InventoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_balance(
        self,
        *,
        warehouse_id: uuid.UUID,
        product_id: uuid.UUID,
        batch_id: uuid.UUID | None,
    ) -> StockBalance | None:
        stmt = select(StockBalance).where(
            StockBalance.warehouse_id == warehouse_id,
            StockBalance.product_id == product_id,
        )
        stmt = stmt.where(
            StockBalance.batch_id == batch_id
            if batch_id is not None
            else StockBalance.batch_id.is_(None)
        )
        # Lock the row during finalization to serialise concurrent deductions.
        stmt = stmt.with_for_update()
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def add_movement(self, movement: StockMovement) -> None:
        self._session.add(movement)
        await self._session.flush()

    async def upsert_balance_delta(
        self,
        *,
        organization_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        product_id: uuid.UUID,
        batch_id: uuid.UUID | None,
        delta: Decimal,
    ) -> StockBalance:
        balance = await self.get_balance(
            warehouse_id=warehouse_id, product_id=product_id, batch_id=batch_id
        )
        if balance is None:
            balance = StockBalance(
                organization_id=organization_id,
                warehouse_id=warehouse_id,
                product_id=product_id,
                batch_id=batch_id,
                on_hand=Decimal("0"),
                reserved=Decimal("0"),
            )
            self._session.add(balance)
        balance.on_hand = balance.on_hand + delta
        await self._session.flush()
        return balance

    async def batch_availability(
        self, *, warehouse_id: uuid.UUID, product_id: uuid.UUID
    ) -> list[BatchAvailability]:
        stmt = (
            select(StockBalance, Batch.expiry_date)
            .outerjoin(Batch, Batch.id == StockBalance.batch_id)
            .where(
                StockBalance.warehouse_id == warehouse_id,
                StockBalance.product_id == product_id,
                StockBalance.on_hand > StockBalance.reserved,
            )
            .with_for_update(of=StockBalance)
        )
        rows = await self._session.execute(stmt)
        return [
            BatchAvailability(
                batch_id=balance.batch_id,
                expiry_date=expiry,
                available=balance.on_hand - balance.reserved,
            )
            for balance, expiry in rows.all()
        ]

    async def adjust_reserved(
        self,
        *,
        warehouse_id: uuid.UUID,
        product_id: uuid.UUID,
        batch_id: uuid.UUID | None,
        delta: Decimal,
    ) -> None:
        balance = await self.get_balance(
            warehouse_id=warehouse_id, product_id=product_id, batch_id=batch_id
        )
        if balance is None:
            raise ValueError("Cannot adjust reservation on a missing balance row.")
        balance.reserved = balance.reserved + delta
        await self._session.flush()

    async def reserved_balances(
        self, *, warehouse_id: uuid.UUID, product_id: uuid.UUID
    ) -> list[BatchAvailability]:
        """Balances that currently hold a reservation, earliest expiry first."""
        stmt = (
            select(StockBalance, Batch.expiry_date)
            .outerjoin(Batch, Batch.id == StockBalance.batch_id)
            .where(
                StockBalance.warehouse_id == warehouse_id,
                StockBalance.product_id == product_id,
                StockBalance.reserved > 0,
            )
            .with_for_update(of=StockBalance)
        )
        rows = await self._session.execute(stmt)
        return [
            BatchAvailability(
                batch_id=balance.batch_id, expiry_date=expiry, available=balance.reserved
            )
            for balance, expiry in rows.all()
        ]
