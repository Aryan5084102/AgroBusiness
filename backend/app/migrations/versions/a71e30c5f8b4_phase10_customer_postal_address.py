"""phase10 customer postal address

Adds ``customers.address`` — the postal address printed in the "billed to"
block of a tax invoice. ``village`` is kept as the short local identifier the
counter recognises, so this is purely additive and nullable: existing customers
carry on with a null address until someone fills one in.

Revision ID: a71e30c5f8b4
Revises: c9f1a70b34d2
Create Date: 2026-08-25 20:05:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a71e30c5f8b4"
down_revision: str | None = "c9f1a70b34d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("address", sa.String(length=400), nullable=True))


def downgrade() -> None:
    op.drop_column("customers", "address")
