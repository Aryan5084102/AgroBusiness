"""Authentication service.

Responsibilities:
- Verify credentials with Argon2, enforce account lockout after repeated failures.
- Issue a session + rotating refresh token and a short-lived access token.
- On refresh: rotate the token; detect reuse of an already-used/revoked token and
  revoke the whole session (defends against stolen refresh tokens).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    needs_rehash,
    verify_password,
)
from app.modules.audit.service import AuditService
from app.modules.auth.models import RefreshToken, Session
from app.modules.auth.repository import AuthRepository

MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15


@dataclass
class IssuedTokens:
    access_token: str
    refresh_token: str
    access_expires_in: int
    user_id: uuid.UUID
    organization_id: uuid.UUID
    is_owner: bool
    permissions: list[str]
    branch_ids: list[uuid.UUID]
    full_name: str
    email: str


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AuthRepository(session)
        self._audit = AuditService(session)

    async def authenticate(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None,
        user_agent: str | None,
        correlation_id: str | None,
    ) -> IssuedTokens:
        user = await self._repo.get_user_by_email(None, email)
        now = _now()

        # Uniform failure to avoid leaking whether the email exists.
        if user is None:
            raise AuthenticationError("Invalid email or password.")

        if user.locked_until is not None and user.locked_until > now:
            await self._audit.record(
                action="login.locked",
                organization_id=user.organization_id,
                actor_user_id=user.id,
                ip_address=ip_address,
                correlation_id=correlation_id,
            )
            # Commit here: the endpoint's commit never runs on the raised error,
            # but the audit record must persist.
            await self._session.commit()
            raise AuthenticationError(
                "Account temporarily locked. Try again later.", code="account_locked"
            )

        if not user.is_active or not verify_password(password, user.hashed_password):
            user.failed_login_count += 1
            if user.failed_login_count >= MAX_FAILED_LOGINS:
                user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
                user.failed_login_count = 0
            await self._audit.record(
                action="login.failed",
                organization_id=user.organization_id,
                actor_user_id=user.id,
                ip_address=ip_address,
                correlation_id=correlation_id,
            )
            # Persist the incremented failure counter / lockout despite raising.
            await self._session.commit()
            raise AuthenticationError("Invalid email or password.")

        # Success: opportunistically upgrade weak hashes, reset counters.
        if needs_rehash(user.hashed_password):
            user.hashed_password = hash_password(password)
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now

        tokens = await self._issue_session(
            user_id=user.id,
            organization_id=user.organization_id,
            is_owner=user.is_owner,
            full_name=user.full_name,
            email=user.email,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self._audit.record(
            action="login.success",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id,
        )
        return tokens

    async def refresh(
        self,
        *,
        raw_refresh_token: str,
        ip_address: str | None,
        user_agent: str | None,
        correlation_id: str | None,
    ) -> IssuedTokens:
        now = _now()
        token_hash = hash_token(raw_refresh_token)
        stored = await self._repo.get_refresh_by_hash(token_hash)

        if stored is None:
            raise AuthenticationError("Invalid refresh token.")

        # Reuse detection: a used or revoked token being presented again means the
        # token was leaked. Revoke the entire session.
        if stored.used_at is not None or stored.revoked_at is not None:
            await self._repo.revoke_session_tokens(stored.session_id, now)
            session = await self._repo.get_session(stored.session_id)
            if session is not None:
                session.revoked_at = now
            await self._audit.record(
                action="token.reuse_detected",
                organization_id=session.organization_id if session else None,
                actor_user_id=stored.user_id,
                ip_address=ip_address,
                correlation_id=correlation_id,
            )
            # Persist the session revocation despite raising.
            await self._session.commit()
            raise AuthenticationError(
                "Refresh token reuse detected. Session revoked.",
                code="token_reuse",
            )

        if stored.expires_at <= now:
            raise AuthenticationError("Refresh token expired.", code="token_expired")

        session = await self._repo.get_session(stored.session_id)
        if session is None or session.revoked_at is not None:
            raise AuthenticationError("Session is no longer valid.")

        user = await self._repo.get_user(stored.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("User is no longer active.")

        # Rotate: mark current used, mint a new refresh token in the same session.
        stored.used_at = now
        new_raw = generate_refresh_token()
        settings = get_settings()
        new_token = RefreshToken(
            session_id=session.id,
            user_id=user.id,
            token_hash=hash_token(new_raw),
            created_at=now,
            expires_at=now + timedelta(seconds=settings.refresh_token_ttl_seconds),
        )
        await self._repo.add_refresh_token(new_token)
        stored.replaced_by_id = new_token.id
        session.last_seen_at = now

        permissions = await self._repo.get_user_permissions(user.id)
        branch_ids = await self._repo.get_user_branch_ids(user.id)
        access = create_access_token(
            user_id=user.id,
            organization_id=user.organization_id,
            branch_ids=branch_ids,
            permissions=permissions,
            session_id=session.id,
            is_owner=user.is_owner,
        )
        await self._session.flush()
        return IssuedTokens(
            access_token=access,
            refresh_token=new_raw,
            access_expires_in=settings.access_token_ttl_seconds,
            user_id=user.id,
            organization_id=user.organization_id,
            is_owner=user.is_owner,
            permissions=permissions,
            branch_ids=branch_ids,
            full_name=user.full_name,
            email=user.email,
        )

    async def logout(self, *, raw_refresh_token: str | None) -> None:
        if not raw_refresh_token:
            return
        now = _now()
        stored = await self._repo.get_refresh_by_hash(hash_token(raw_refresh_token))
        if stored is None:
            return
        await self._repo.revoke_session_tokens(stored.session_id, now)
        session = await self._repo.get_session(stored.session_id)
        if session is not None:
            session.revoked_at = now
        await self._session.flush()

    async def _issue_session(
        self,
        *,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        is_owner: bool,
        full_name: str,
        email: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> IssuedTokens:
        now = _now()
        settings = get_settings()
        session = Session(
            user_id=user_id,
            organization_id=organization_id,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=now,
            last_seen_at=now,
        )
        await self._repo.create_session(session)

        raw_refresh = generate_refresh_token()
        refresh = RefreshToken(
            session_id=session.id,
            user_id=user_id,
            token_hash=hash_token(raw_refresh),
            created_at=now,
            expires_at=now + timedelta(seconds=settings.refresh_token_ttl_seconds),
        )
        await self._repo.add_refresh_token(refresh)

        permissions = await self._repo.get_user_permissions(user_id)
        branch_ids = await self._repo.get_user_branch_ids(user_id)
        access = create_access_token(
            user_id=user_id,
            organization_id=organization_id,
            branch_ids=branch_ids,
            permissions=permissions,
            session_id=session.id,
            is_owner=is_owner,
        )
        return IssuedTokens(
            access_token=access,
            refresh_token=raw_refresh,
            access_expires_in=settings.access_token_ttl_seconds,
            user_id=user_id,
            organization_id=organization_id,
            is_owner=is_owner,
            permissions=permissions,
            branch_ids=branch_ids,
            full_name=full_name,
            email=email,
        )
