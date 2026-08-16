"""Authentication endpoints. Tokens are delivered as HTTP-only cookies."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.context import CurrentUser
from app.core.deps import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    db_session,
    get_current_user,
)
from app.core.ratelimit import login_rate_limiter
from app.modules.auth.schemas import LoginRequest, LoginResponse, UserProfile
from app.modules.auth.service import AuthService, IssuedTokens

router = APIRouter(tags=["auth"])


def _set_auth_cookies(response: Response, tokens: IssuedTokens) -> None:
    settings = get_settings()
    secure = settings.auth_cookie_secure
    samesite = settings.cookie_samesite
    response.set_cookie(
        ACCESS_COOKIE,
        tokens.access_token,
        max_age=settings.access_token_ttl_seconds,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        max_age=settings.refresh_token_ttl_seconds,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/",
    )


def _profile(tokens: IssuedTokens) -> UserProfile:
    return UserProfile(
        id=tokens.user_id,
        email=tokens.email,
        full_name=tokens.full_name,
        organization_id=tokens.organization_id,
        is_owner=tokens.is_owner,
        permissions=tokens.permissions,
        branch_ids=tokens.branch_ids,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(db_session),
) -> LoginResponse:
    # Per-IP rate limit on login (complements the per-account lockout).
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    login_rate_limiter.check(
        f"login:{client_ip}",
        limit=settings.login_rate_limit,
        window_seconds=settings.login_rate_window_seconds,
    )
    service = AuthService(session)
    tokens = await service.authenticate(
        email=payload.email,
        password=payload.password,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        correlation_id=getattr(request.state, "correlation_id", None),
    )
    await session.commit()
    _set_auth_cookies(response, tokens)
    return LoginResponse(user=_profile(tokens), access_expires_in=tokens.access_expires_in)


@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(db_session),
) -> LoginResponse:
    from app.core.exceptions import AuthenticationError

    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise AuthenticationError("No refresh token provided.")
    service = AuthService(session)
    tokens = await service.refresh(
        raw_refresh_token=raw,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        correlation_id=getattr(request.state, "correlation_id", None),
    )
    await session.commit()
    _set_auth_cookies(response, tokens)
    return LoginResponse(user=_profile(tokens), access_expires_in=tokens.access_expires_in)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(db_session),
) -> Response:
    service = AuthService(session)
    await service.logout(raw_refresh_token=request.cookies.get(REFRESH_COOKIE))
    await session.commit()
    # The clearing Set-Cookie must repeat the original attributes, or the
    # browser rejects it and the session survives logout on cross-site setups.
    settings = get_settings()
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.delete_cookie(
            name,
            path="/",
            httponly=True,
            secure=settings.auth_cookie_secure,
            samesite=settings.cookie_samesite,
        )
    response.status_code = 204
    return response


@router.get("/me", response_model=UserProfile)
async def me(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> UserProfile:
    from app.core.exceptions import AuthenticationError
    from app.modules.auth.repository import AuthRepository

    record = await AuthRepository(session).get_user(user.user_id)
    if record is None or not record.is_active:
        raise AuthenticationError("User is no longer active.")
    return UserProfile(
        id=user.user_id,
        email=record.email,
        full_name=record.full_name,
        organization_id=user.organization_id,
        is_owner=user.is_owner,
        permissions=sorted(user.permissions),
        branch_ids=user.branch_ids,
    )
