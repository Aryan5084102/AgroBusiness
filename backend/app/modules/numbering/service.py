"""Atomic document-number issuance."""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.numbering.models import NumberSequence
from app.modules.organizations.models import Branch


def _advisory_lock_key(
    organization_id: uuid.UUID, branch_id: uuid.UUID | None, document_type: str
) -> int:
    """Stable 64-bit signed key for a per-scope transaction advisory lock."""
    raw = f"{organization_id}:{branch_id}:{document_type}".encode()
    return int.from_bytes(hashlib.md5(raw).digest()[:8], "big", signed=True)


# Default prefixes per document type.
_DEFAULT_PREFIXES = {
    "purchase_order": "PO",
    "goods_receipt": "GRN",
    "purchase_invoice": "PINV",
    "sales_invoice": "INV",
    "sales_order": "SO",
    "quotation": "QTN",
    "payment": "PAY",
    "repair_job": "JOB",
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
        """Issue the next formatted number for a document type.

        Serialised with a transaction-level advisory lock keyed by
        (org, branch, document_type). This covers the first-use race where the
        sequence row does not yet exist (so a plain SELECT FOR UPDATE has nothing
        to lock), which would otherwise let two concurrent documents share a
        number. The lock releases automatically at transaction end.
        """
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": _advisory_lock_key(organization_id, branch_id, document_type)},
        )
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
                prefix=await self._prefix_for(document_type, branch_id),
                next_value=1,
            )
            self._session.add(seq)
            await self._session.flush()

        value = seq.next_value
        seq.next_value = value + 1
        await self._session.flush()
        return f"{seq.prefix}-{value:0{seq.padding}d}"

    async def _prefix_for(self, document_type: str, branch_id: uuid.UUID | None) -> str:
        """Build a prefix that keeps numbers unique across the organization.

        Sequences count per branch, but document numbers are unique per *org*
        (that is what a tax authority expects to see). Without the branch code in
        the prefix, the second branch's first invoice would collide with the
        first branch's — so branch-scoped sequences carry the branch code.
        """
        base = _DEFAULT_PREFIXES.get(document_type, document_type.upper()[:6])
        if branch_id is None:
            return base
        branch = await self._session.get(Branch, branch_id)
        if branch is None:
            return base
        # Keep within the column's 20 chars: e.g. "MAIN-INV".
        return f"{branch.code[:11]}-{base}"
