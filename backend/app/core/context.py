"""Authenticated request context derived from the access token.

Tenant identifiers ALWAYS come from here (the verified token), never from the
request body/query. Services accept a ``CurrentUser`` and scope every query to
``organization_id`` and the permitted branches.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CurrentUser:
    user_id: uuid.UUID
    organization_id: uuid.UUID
    session_id: uuid.UUID
    is_owner: bool
    branch_ids: list[uuid.UUID] = field(default_factory=list)
    permissions: frozenset[str] = field(default_factory=frozenset)

    def has_permission(self, code: str) -> bool:
        # Owners implicitly hold every permission.
        return self.is_owner or code in self.permissions

    def can_access_branch(self, branch_id: uuid.UUID) -> bool:
        return self.is_owner or branch_id in self.branch_ids
