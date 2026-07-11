"""Unit tests for password hashing and access-token handling (no DB)."""

from __future__ import annotations

import uuid

import jwt
import pytest
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("CorrectHorse1")
    assert hashed != "CorrectHorse1"
    assert verify_password("CorrectHorse1", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_refresh_tokens_are_unique_and_hashable() -> None:
    a, b = generate_refresh_token(), generate_refresh_token()
    assert a != b
    assert hash_token(a) == hash_token(a)
    assert hash_token(a) != hash_token(b)


def test_access_token_carries_claims() -> None:
    uid, org, sid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    token = create_access_token(
        user_id=uid,
        organization_id=org,
        branch_ids=[],
        permissions=["sales.create"],
        session_id=sid,
        is_owner=True,
    )
    decoded = decode_access_token(token)
    assert decoded["sub"] == str(uid)
    assert decoded["org"] == str(org)
    assert decoded["owner"] is True
    assert "sales.create" in decoded["perms"]


def test_refresh_token_is_not_an_access_token() -> None:
    # A token of the wrong type must be rejected by decode_access_token.
    from app.core.config import get_settings

    settings = get_settings()
    bad = jwt.encode({"type": "refresh"}, settings.secret_key, algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(bad)
