"""Atomic document-number issuance."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.numbering.models import NumberSequence

# Default prefixes per document type.
_DEFAULT_PREFIXES = {
    "purchase_order": "PO",
    "goods_receipt": "GRN",
    "purchase_invoice": "PINV",
    "sales_invoice": "INV",
    "sales_order": "SO",
    "payment": "PAY",
}


class NumberingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def next_number(
        self,
        *,
        organization_id: uuid.UUID,
        document_type: str,
        branch_id: uuid.UUID | None = None,
    ) -> str:
        """Issue the next formatted number for a document type (locks the row)."""
        stmt = (
            select(NumberSequence)
            .where(
                NumberSequence.organization_id == organization_id,
                NumberSequence.document_type == document_type,
            )
            .with_for_update()
        )
        stmt = stmt.where(
            NumberSequence.branch_id == branch_id
            if branch_id is not None
            else NumberSequence.branch_id.is_(None)
        )
        seq = (await self._session.execute(stmt)).scalars().first()
        if seq is None:
            seq = NumberSequence(
                organization_id=organization_id,
                branch_id=branch_id,
                document_type=document_type,
                prefix=_DEFAULT_PREFIXES.get(document_type, document_type.upper()[:6]),
                next_value=1,
            )
            self._session.add(seq)
            await self._session.flush()

        value = seq.next_value
        seq.next_value = value + 1
        await self._session.flush()
        return f"{seq.prefix}-{value:0{seq.padding}d}"
