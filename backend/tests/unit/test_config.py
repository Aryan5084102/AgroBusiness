"""Connection-string normalisation.

These cases are the exact strings the hosted Postgres providers put on their
dashboards. Each one used to reach ``asyncpg.connect()`` unchanged and fail
there, not here — the driver's signature takes no ``**kwargs``, so an unknown
keyword is a TypeError on the first query rather than a startup error.
"""

from __future__ import annotations

import pytest
from app.core.config import Settings


def _url(value: str) -> str:
    return Settings(database_url=value).database_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Neon: sslmode plus the libpq 14 parameter asyncpg has never accepted.
        (
            "postgresql://u:p@ep-cool-dawn-123.us-east-2.aws.neon.tech/agriflow"
            "?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@ep-cool-dawn-123.us-east-2.aws.neon.tech/agriflow"
            "?ssl=require",
        ),
        # Supabase / Aiven / Render's external URL: sslmode on its own.
        (
            "postgresql://u:p@db.abcdefgh.supabase.co:5432/postgres?sslmode=require",
            "postgresql+asyncpg://u:p@db.abcdefgh.supabase.co:5432/postgres?ssl=require",
        ),
        # Heroku-style scheme, verify-full: the value is passed through as-is,
        # only the key is renamed.
        (
            "postgres://u:p@host.example.com:5432/db?sslmode=verify-full",
            "postgresql+asyncpg://u:p@host.example.com:5432/db?ssl=verify-full",
        ),
        # Stripping the only parameter must not leave a dangling "?".
        (
            "postgresql://u:p@host.example.com/db?channel_binding=require",
            "postgresql+asyncpg://u:p@host.example.com/db",
        ),
    ],
)
def test_libpq_params_are_rewritten_for_asyncpg(raw: str, expected: str) -> None:
    assert _url(raw) == expected


def test_explicit_ssl_wins_over_sslmode() -> None:
    """A hand-edited `ssl=` is authoritative; `sslmode=` must not duplicate it."""
    result = _url("postgresql://u:p@host.example.com/db?ssl=verify-full&sslmode=require")
    assert result == "postgresql+asyncpg://u:p@host.example.com/db?ssl=verify-full"


def test_unrelated_query_parameters_survive() -> None:
    """Only the libpq TLS spellings are touched — asyncpg's own tuning is not."""
    result = _url(
        "postgresql://u:p@host.example.com/db"
        "?sslmode=require&prepared_statement_cache_size=0"
    )
    assert result == (
        "postgresql+asyncpg://u:p@host.example.com/db"
        "?ssl=require&prepared_statement_cache_size=0"
    )


def test_internal_url_without_query_is_untouched() -> None:
    """Render's internal URL has no query string and needs no TLS parameters."""
    result = _url("postgresql://agriflow:secret@dpg-abc123-a/agriflow")
    assert result == "postgresql+asyncpg://agriflow:secret@dpg-abc123-a/agriflow"
