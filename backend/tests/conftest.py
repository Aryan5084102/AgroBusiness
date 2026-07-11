"""Shared pytest fixtures.

Unit tests (money/units/security) need no database. Integration tests use a real
Postgres database selected via ``TEST_DATABASE_URL`` (falls back to a local dev
instance). The schema is created from ``Base.metadata`` once per session and each
test runs against a clean set of tables.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

# Deterministic environment before importing the app/config.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-value")
_DEFAULT_TEST_DB = "postgresql+asyncpg://agriflow@127.0.0.1:5433/agriflow_test"
os.environ.setdefault("DATABASE_URL", os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_DB))


@pytest.fixture(autouse=True)
def _reset_login_rate_limiter() -> None:
    """The login limiter is process-global; reset it so tests don't bleed counts."""
    from app.core.ratelimit import login_rate_limiter

    login_rate_limiter._buckets.clear()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Async HTTP client bound to the ASGI app (no DB required)."""
    from app.main import create_app

    app = create_app()
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


def _has_database() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


@pytest.fixture
async def db_ready() -> AsyncIterator[None]:
    """Create all tables from metadata; drop them after the test for isolation.

    Each test gets a fresh NullPool engine bound to its own event loop (pytest-
    asyncio runs a new loop per test), avoiding cross-loop pool reuse errors.
    """
    import app.db_models  # noqa: F401
    from app.core import database
    from app.core.config import get_settings
    from app.core.database import Base
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(str(get_settings().database_url), poolclass=NullPool, future=True)
    database._engine = engine
    database._sessionmaker = async_sessionmaker(
        bind=engine, expire_on_commit=False, autoflush=False
    )
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:  # pragma: no cover - surfaces a clear skip reason
        await engine.dispose()
        database._engine = None
        database._sessionmaker = None
        pytest.skip(f"Postgres test database unavailable: {exc}")
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    database._engine = None
    database._sessionmaker = None


@pytest.fixture
async def api(db_ready: None) -> AsyncIterator[AsyncClient]:
    """HTTP client against the app with a fresh database schema."""
    from app.main import create_app

    app = create_app()
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
