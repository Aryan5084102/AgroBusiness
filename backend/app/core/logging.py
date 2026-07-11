"""Structured logging configuration using structlog.

Emits JSON in production for log aggregation and a colourised console renderer
in development. A processor injects the request correlation id when present.
Sensitive keys are redacted so tokens and passwords never reach the logs.
"""

from __future__ import annotations

import logging
import sys
from typing import cast

import structlog
from structlog.typing import EventDict, WrappedLogger

_SENSITIVE_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "authorization",
    "secret_key",
}


def _redact_sensitive(_logger: WrappedLogger, _method: str, event_dict: EventDict) -> EventDict:
    """Mask values for keys that must never be logged in clear text."""
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "***redacted***"
    return event_dict


def configure_logging(*, json_logs: bool, level: str = "INFO") -> None:
    """Configure structlog and the stdlib logging bridge once at startup."""
    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redact_sensitive,
    ]

    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
