"""Domain and API exception hierarchy plus a consistent error envelope.

Every error surfaced to a client uses the same shape:

    {"error": {"code", "message", "field_errors", "correlation_id"}}

Internal details and stack traces are never included in the client payload.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error. Subclasses map to HTTP status codes.

    ``code`` is a stable machine-readable identifier the frontend can branch on;
    ``message`` is a safe, human-readable summary.
    """

    status_code: int = 400
    code: str = "app_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        field_errors: dict[str, list[str]] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.field_errors = field_errors or {}
        self.details = details or {}


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_error"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    """Optimistic-locking failures, duplicate documents, number collisions."""

    status_code = 409
    code = "conflict"


class BusinessRuleError(AppError):
    """A valid request that violates a domain rule (e.g. credit limit, expiry)."""

    status_code = 422
    code = "business_rule_violation"


def build_error_body(
    *,
    code: str,
    message: str,
    correlation_id: str | None,
    field_errors: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Assemble the standard client error envelope."""
    return {
        "error": {
            "code": code,
            "message": message,
            "field_errors": field_errors or {},
            "correlation_id": correlation_id,
        }
    }
