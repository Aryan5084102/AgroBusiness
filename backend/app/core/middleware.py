"""HTTP middleware: correlation ids, security headers, exception mapping.

The correlation id is read from the inbound ``X-Request-ID`` header when present
(so it can be propagated across services) or generated per request. It is bound
into the structlog context and echoed back on the response.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.exceptions import AppError, build_error_body
from app.core.logging import get_logger

logger = get_logger("http")

CORRELATION_HEADER = "X-Request-ID"

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-XSS-Protection": "0",
}


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Attach a correlation id to every request and bind it to log context."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get(CORRELATION_HEADER) or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            path=request.url.path,
            method=request.method,
        )
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = correlation_id
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response


def register_exception_handlers(app: FastAPI) -> None:
    """Map application and unexpected errors to the standard error envelope."""

    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", None)
        logger.info(
            "app_error",
            code=exc.code,
            status=exc.status_code,
            message=exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_body(
                code=exc.code,
                message=exc.message,
                correlation_id=correlation_id,
                field_errors=exc.field_errors,
            ),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", None)
        # Log the full error internally; never leak details to the client.
        logger.exception("unhandled_exception", error=str(exc))
        return JSONResponse(
            status_code=500,
            content=build_error_body(
                code="internal_error",
                message="An unexpected error occurred. Please try again.",
                correlation_id=correlation_id,
            ),
        )
