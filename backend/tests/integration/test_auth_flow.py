"""Phase 1 integration tests against a real Postgres database.

Covers: provisioning, login (+ lockout), access to a protected route, RBAC
enforcement, refresh-token rotation, refresh-reuse detection, logout, and tenant
isolation between two organizations.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from app.core.database import get_sessionmaker
from app.main import create_app
from app.modules.organizations.service import OrganizationProvisioningService
from httpx import ASGITransport, AsyncClient

OWNER_EMAIL = "owner@agriflow.local"
OWNER_PW = "OwnerPass123"


async def _provision(org_name: str, owner_email: str) -> None:
    factory = get_sessionmaker()
    async with factory() as session:
        await OrganizationProvisioningService(session).provision(
            org_name=org_name,
            owner_email=owner_email,
            owner_password=OWNER_PW,
            owner_name="Owner",
        )
        await session.commit()


@pytest.fixture
async def app_client(api: AsyncClient) -> AsyncIterator[AsyncClient]:
    # ``api`` already gives a fresh schema; provision a default org for tests.
    await _provision("Acme Agri", OWNER_EMAIL)
    yield api


async def test_login_sets_cookies_and_returns_owner_profile(
    app_client: AsyncClient,
) -> None:
    resp = await app_client.post(
        "/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PW}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["is_owner"] is True
    assert "audit.view" in body["user"]["permissions"]
    assert "access_token" in resp.cookies
    assert "refresh_token" in resp.cookies


async def test_wrong_password_is_rejected(app_client: AsyncClient) -> None:
    resp = await app_client.post(
        "/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": "wrong"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "authentication_error"


async def test_account_locks_after_five_failures(app_client: AsyncClient) -> None:
    for _ in range(5):
        await app_client.post(
            "/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": "wrong"}
        )
    # 6th attempt, even with the correct password, is locked out.
    resp = await app_client.post(
        "/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PW}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "account_locked"


async def test_me_requires_auth(app_client: AsyncClient) -> None:
    resp = await app_client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_owner_can_list_users_and_create_one(app_client: AsyncClient) -> None:
    await app_client.post("/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PW})
    listing = await app_client.get("/api/v1/users")
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    created = await app_client.post(
        "/api/v1/users",
        json={
            "email": "counter@agriflow.local",
            "password": "CounterPass1",
            "full_name": "Counter Staff",
            "role_code": "counter_sales",
        },
    )
    assert created.status_code == 201, created.text


async def test_counter_staff_cannot_manage_users(app_client: AsyncClient) -> None:
    # Owner creates a counter user.
    await app_client.post("/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PW})
    await app_client.post(
        "/api/v1/users",
        json={
            "email": "counter@agriflow.local",
            "password": "CounterPass1",
            "full_name": "Counter Staff",
            "role_code": "counter_sales",
        },
    )
    await app_client.post("/api/v1/auth/logout")

    # Log in as the counter user (fresh client to drop cookies).
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as counter:
        await counter.post(
            "/api/v1/auth/login",
            json={"email": "counter@agriflow.local", "password": "CounterPass1"},
        )
        resp = await counter.get("/api/v1/users")
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "permission_denied"


async def test_refresh_rotates_token(app_client: AsyncClient) -> None:
    login = await app_client.post(
        "/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PW}
    )
    first_refresh = login.cookies["refresh_token"]
    resp = await app_client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    assert app_client.cookies["refresh_token"] != first_refresh


async def test_refresh_reuse_is_detected_and_revokes_session(
    app_client: AsyncClient,
) -> None:
    login = await app_client.post(
        "/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PW}
    )
    stolen = login.cookies["refresh_token"]

    # Legitimate rotation consumes the first token.
    await app_client.post("/api/v1/auth/refresh")

    # Replaying the stolen (now used) token from a separate client must be
    # detected and rejected (cookie set on the client instance, not per-request).
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies={"refresh_token": stolen}
    ) as attacker:
        resp = await attacker.post("/api/v1/auth/refresh")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "token_reuse"

    # And the session is dead: the previously-issued new token no longer refreshes.
    followup = await app_client.post("/api/v1/auth/refresh")
    assert followup.status_code == 401


async def test_tenant_isolation_between_orgs(app_client: AsyncClient) -> None:
    # Second org with its own owner.
    await _provision("Rival Agri", "owner2@rival.local")

    await app_client.post("/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PW})
    listing = await app_client.get("/api/v1/users")
    emails = {u["email"] for u in listing.json()}
    # Org 1 owner must not see org 2's users.
    assert OWNER_EMAIL in emails
    assert "owner2@rival.local" not in emails
