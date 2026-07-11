"""Health, liveness and readiness probes.

- ``/live``  : the process is up (no dependency checks) — for k8s liveness.
- ``/ready`` : dependencies (Postgres, Redis) are reachable — for readiness.
- ``/health``: a human-friendly aggregate used by the frontend status page.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import get_sessionmaker
from app.core.redis import get_redis

router = APIRouter(tags=["health"])


class ComponentStatus(BaseModel):
    name: str
    status: Literal["up", "down"]
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    environment: str
    version: str
    components: list[ComponentStatus]


async def _check_database() -> ComponentStatus:
    try:
        factory = get_sessionmaker()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        return ComponentStatus(name="database", status="up")
    except Exception as exc:
        return ComponentStatus(name="database", status="down", detail=str(exc)[:200])


async def _check_redis() -> ComponentStatus:
    try:
        await get_redis().ping()
        return ComponentStatus(name="redis", status="up")
    except Exception as exc:
        return ComponentStatus(name="redis", status="down", detail=str(exc)[:200])


@router.get("/live", summary="Liveness probe")
async def live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/ready", summary="Readiness probe")
async def ready() -> HealthResponse:
    return await _aggregate()


@router.get("/health", response_model=HealthResponse, summary="Aggregate health")
async def health() -> HealthResponse:
    return await _aggregate()


async def _aggregate() -> HealthResponse:
    from app import __version__

    settings = get_settings()
    components = [await _check_database(), await _check_redis()]
    overall = "ok" if all(c.status == "up" for c in components) else "degraded"
    return HealthResponse(
        status=overall,
        environment=settings.environment,
        version=__version__,
        components=components,
    )
