"""Auth request/response schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.common.schemas.types import Email


class LoginRequest(BaseModel):
    email: Email
    password: str = Field(min_length=1)


class UserProfile(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    organization_id: uuid.UUID
    is_owner: bool
    permissions: list[str]
    branch_ids: list[uuid.UUID]


class LoginResponse(BaseModel):
    """Returned on login/refresh. Tokens are delivered via HTTP-only cookies."""

    user: UserProfile
    access_expires_in: int
