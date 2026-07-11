"""Branch-specific document number sequences (PO, GRN, invoices, ...).

One row per (organization, branch, document_type). The next number is issued by
locking the row (SELECT ... FOR UPDATE) and incrementing, guaranteeing no gaps
or collisions under concurrency.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class NumberSequence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "number_sequences"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "branch_id",
            "document_type",
            name="uq_number_sequence_scope",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE")
    )
    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    prefix: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    next_value: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    padding: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
