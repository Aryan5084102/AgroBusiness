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


class TestCookieSameSiteDerivation:
    """SameSite is derived from whether the frontend is a cross-site caller.

    The failure this prevents is silent: with `lax` on a cross-domain frontend,
    `/auth/login` returns 200 and a user payload, the browser drops the cookie,
    and the very next request 401s.
    """

    def _settings(self, **kwargs: object) -> Settings:
        return Settings(database_url="postgresql://u:p@db.example.com/agriflow", **kwargs)

    def test_remote_origin_implies_cross_site(self) -> None:
        settings = self._settings(cors_origins=["https://agrobusiness-frontend.vercel.app"])
        assert settings.auth_cookie_samesite == "none"
        # SameSite=None is discarded by browsers unless Secure is also set.
        assert settings.auth_cookie_secure is True

    def test_local_origin_stays_lax(self) -> None:
        assert self._settings(cors_origins=["http://localhost:3000"]).auth_cookie_samesite == "lax"

    def test_explicit_value_wins(self) -> None:
        settings = self._settings(
            cors_origins=["https://app.example.com"], cookie_samesite="lax"
        )
        assert settings.auth_cookie_samesite == "lax"


class TestHostedConfigurationGuard:
    """A hosted service on development defaults must fail loudly, not serve 500s."""

    def _hosted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RENDER", "true")

    def test_localhost_database_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._hosted(monkeypatch)
        settings = Settings(
            database_url="postgresql://u:p@localhost:5432/agriflow",
            cors_origins=["https://app.vercel.app"],
            secret_key="a-real-secret-value",
        )
        with pytest.raises(RuntimeError, match="DATABASE_URL points at"):
            settings.enforce_production_safety()

    def test_unset_cors_is_not_fatal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The frontend proxies /api/* same-origin, so CORS_ORIGINS blocks nothing.

        Making it fatal would refuse a perfectly working deployment over a
        variable the browser never exercises.
        """
        self._hosted(monkeypatch)
        settings = Settings(
            database_url="postgresql://u:p@db.example.com/agriflow",
            cors_origins=["http://localhost:3000"],
            secret_key="a-real-secret-value",
        )
        settings.enforce_production_safety()
        # Same-origin means no cross-site cookie delivery either.
        assert settings.auth_cookie_samesite == "lax"
        # ...but a hosted deployment is HTTPS, so the cookie is still Secure.
        assert settings.auth_cookie_secure is True

    def test_local_development_cookies_are_not_secure(self) -> None:
        """`Secure` on http://localhost would stop the cookie being stored at all."""
        settings = Settings(database_url="postgresql://u:p@localhost/agriflow")
        assert settings.auth_cookie_secure is False

    def test_placeholder_secret_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._hosted(monkeypatch)
        settings = Settings(
            database_url="postgresql://u:p@db.example.com/agriflow",
            secret_key="dev-insecure-change-me",
        )
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            settings.enforce_production_safety()

    def test_every_problem_is_reported_at_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fixing one variable per redeploy is a slow way to find two bugs."""
        self._hosted(monkeypatch)
        settings = Settings(
            database_url="postgresql://u:p@localhost:5432/agriflow",
            secret_key="dev-insecure-change-me",
        )
        with pytest.raises(RuntimeError) as excinfo:
            settings.enforce_production_safety()
        message = str(excinfo.value)
        assert "1. DATABASE_URL" in message
        assert "2. SECRET_KEY" in message

    def test_fully_configured_service_boots(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._hosted(monkeypatch)
        settings = Settings(
            database_url="postgresql://u:p@ep-x.neon.tech/agriflow?sslmode=require",
            cors_origins=["https://agrobusiness-frontend.vercel.app"],
            secret_key="a-real-secret-value",
            environment="staging",
        )
        settings.enforce_production_safety()
        assert settings.auth_cookie_samesite == "none"

    def test_localhost_database_allowed_explicitly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`docker run --network host` against the host's Postgres is legitimate."""
        self._hosted(monkeypatch)
        monkeypatch.setenv("ALLOW_LOCALHOST_DB", "true")
        settings = Settings(
            database_url="postgresql://u:p@localhost:5432/agriflow",
            cors_origins=["https://app.vercel.app"],
            secret_key="a-real-secret-value",
        )
        settings.enforce_production_safety()

    def test_laptop_is_left_alone(self) -> None:
        """No platform marker: dev defaults are exactly what you want."""
        Settings(
            database_url="postgresql://u:p@localhost:5432/agriflow"
        ).enforce_production_safety()

    def test_environment_defaults_to_staging_when_hosted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        self._hosted(monkeypatch)
        # _env_file=None: a developer's local .env pins ENVIRONMENT=development,
        # and a hosted container has no .env at all — this asserts the container.
        settings = Settings(
            _env_file=None, database_url="postgresql://u:p@db.example.com/x"
        )
        assert settings.environment == "staging"
