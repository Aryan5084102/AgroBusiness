"""Foundation tests: app boots, root and health endpoints respond correctly."""

from __future__ import annotations

from httpx import AsyncClient


async def test_root_returns_service_metadata(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "AgriFlow ERP"
    assert "version" in body


async def test_liveness_probe(client: AsyncClient) -> None:
    response = await client.get("/api/v1/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


async def test_health_reports_degraded_without_dependencies(
    client: AsyncClient,
) -> None:
    """Without Postgres/Redis the aggregate health is degraded, not a 500."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    component_names = {c["name"] for c in body["components"]}
    assert {"database", "redis"} <= component_names


async def test_correlation_id_header_is_echoed(client: AsyncClient) -> None:
    response = await client.get("/api/v1/live", headers={"X-Request-ID": "abc123"})
    assert response.headers["X-Request-ID"] == "abc123"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
