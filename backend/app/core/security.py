"""Password hashing (Argon2id) and JWT access/refresh token handling.

Access tokens are short-lived and carry identity + tenant + permission claims.
Refresh tokens are opaque-random, stored hashed server-side, and rotated on use;
this module only issues/verifies the signed access token and hashes secrets.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

_password_hasher = PasswordHasher()

ACCESS_TOKEN_TYPE = "access"


def hash_password(plain: str) -> str:
    """Hash a password with Argon2id."""
    return _password_hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against its Argon2 hash (constant-time inside argon2)."""
    try:
        return _password_hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def needs_rehash(hashed: str) -> bool:
    """True when the stored hash uses outdated parameters and should be upgraded."""
    return _password_hasher.check_needs_rehash(hashed)


def generate_refresh_token() -> str:
    """Return a high-entropy opaque refresh token (URL-safe)."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Deterministic SHA-256 hash for storing/looking up opaque tokens.

    Refresh tokens are random and high-entropy, so a fast hash is appropriate and
    lets us index the column for O(1) lookup on refresh.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_access_token(
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    branch_ids: list[uuid.UUID],
    permissions: list[str],
    session_id: uuid.UUID,
    is_owner: bool = False,
) -> str:
    """Create a signed access token embedding tenant + permission claims."""
    settings = get_settings()
    issued = _now()
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "org": str(organization_id),
        "branches": [str(b) for b in branch_ids],
        "perms": permissions,
        "owner": is_owner,
        "sid": str(session_id),
        "type": ACCESS_TOKEN_TYPE,
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(seconds=settings.access_token_ttl_seconds)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed access token. Raises jwt exceptions on failure."""
    settings = get_settings()
    payload: dict[str, Any] = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise jwt.InvalidTokenError("Not an access token.")
    return payload
