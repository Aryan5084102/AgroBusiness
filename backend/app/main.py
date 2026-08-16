"""FastAPI application factory for AgriFlow ERP.

Keeps wiring (middleware, CORS, routers, lifecycle) in one place. Business logic
lives in feature modules under ``app/modules`` (added from Phase 1 onward).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import CorrelationIdMiddleware, register_exception_handlers
from app.core.redis import close_redis


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown lifecycle hooks."""
    logger = get_logger("lifespan")
    logger.info("startup", version=__version__)
    yield
    await close_redis()
    logger.info("shutdown")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    configure_logging(json_logs=settings.is_production)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # A deployed service whose only allowed origins are local ones is nearly
    # always a forgotten CORS_ORIGINS. It fails invisibly: the browser drops the
    # response, the frontend reports a generic network error, and the server
    # logs a perfectly ordinary request. Say so at startup instead.
    if settings.environment in ("staging", "production") and all(
        "localhost" in origin or "127.0.0.1" in origin for origin in settings.cors_origins
    ):
        get_logger("startup").warning(
            "cors_origins_look_local",
            cors_origins=settings.cors_origins,
            environment=settings.environment,
            hint="Set CORS_ORIGINS to the frontend's origin, or browsers will block every request.",
        )

    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"service": settings.app_name, "version": __version__}

    return app


app = create_app()
