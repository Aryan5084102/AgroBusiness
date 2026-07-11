"""Compliance document metadata (licences, certificates, invoices, images).

The object-storage key is stored server-side and never exposed; downloads go
through a signed-URL abstraction (added with the storage integration). Soft
deletion + restore is supported for compliance records.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class Document(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "documents"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(120))
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    expiry_date: Mapped[date | None] = mapped_column(Date, index=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
