"""Declarative mixins shared by business tables.

- ``UUIDPrimaryKeyMixin``  : UUID v4 primary key (no sequential leakage).
- ``TimestampMixin``       : created_at / updated_at (timezone-aware).
- ``AuditMixin``           : created_by / updated_by user references.
- ``TenantMixin``          : organization_id / branch_id for isolation.
- ``VersionMixin``         : optimistic-locking version counter.
- ``SoftDeleteMixin``      : deleted_at for records where soft delete is allowed.

Immutable ledger/financial rows deliberately do NOT use ``SoftDeleteMixin``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AuditMixin:
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class TenantMixin:
    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )


class VersionMixin:
    """Optimistic locking. SQLAlchemy bumps this and checks it on UPDATE.

    ``__mapper_args__`` is a ``declared_attr`` so each mapped subclass binds
    ``version_id_col`` to its own copy of the column (the correct mixin pattern).
    """

    version_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    @declared_attr.directive
    def __mapper_args__(cls) -> dict[str, Any]:
        return {"version_id_col": cls.version_id}


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
