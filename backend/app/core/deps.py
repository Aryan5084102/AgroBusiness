"""FastAPI dependencies: DB session, current user, and permission guards."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Callable, Coroutine
from typing import Any

import jwt
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import CurrentUser
from app.core.database import get_session
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"


async def db_session() -> AsyncGenerator[AsyncSession, Any]:
    async for session in get_session():
        yield session


def _extract_token(request: Request) -> str:
    token = request.cookies.get(ACCESS_COOKIE)
    if token:
        return token
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header.removeprefix("Bearer ").strip()
    raise AuthenticationError("Authentication required.")


def get_current_user(request: Request) -> CurrentUser:
    """Decode the access token into a verified CurrentUser (no DB hit)."""
    token = _extract_token(request)
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Session expired.", code="token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid authentication token.") from exc

    try:
        return CurrentUser(
            user_id=uuid.UUID(payload["sub"]),
            organization_id=uuid.UUID(payload["org"]),
            session_id=uuid.UUID(payload["sid"]),
            is_owner=bool(payload.get("owner", False)),
            branch_ids=[uuid.UUID(b) for b in payload.get("branches", [])],
            permissions=frozenset(payload.get("perms", [])),
        )
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Malformed authentication token.") from exc


def require_permission(
    code: str,
) -> Callable[[CurrentUser], Coroutine[Any, Any, CurrentUser]]:
    """Dependency factory enforcing an action-level permission on a route."""

    async def _guard(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.has_permission(code):
            raise PermissionDeniedError(
                f"You do not have permission: {code}", code="permission_denied"
            )
        return user

    return _guard
