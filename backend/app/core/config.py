"""Application configuration with strict environment-variable validation.

Settings are loaded once and cached. Missing or malformed required variables
fail fast at startup rather than surfacing as runtime errors later.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit

from pydantic import Field, PostgresDsn, RedisDsn, TypeAdapter, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Validate DSN shape at load time while keeping the stored type as ``str`` for
# ergonomic use with SQLAlchemy / redis clients.
_postgres_adapter = TypeAdapter(PostgresDsn)
_redis_adapter = TypeAdapter(RedisDsn)

# libpq spells its TLS options `sslmode=` / `channel_binding=`; the asyncpg
# driver takes `ssl=` and nothing else. SQLAlchemy's asyncpg dialect forwards the
# URL query straight to ``asyncpg.connect()``, whose signature has no **kwargs —
# so a leftover libpq parameter becomes `TypeError: connect() got an unexpected
# keyword argument 'sslmode'`, raised on the first query, well after startup
# validation has passed and /live has gone green. Every hosted Postgres (Neon,
# Supabase, Aiven, Render's *external* URL) appends at least one of them, so
# translate the string rather than expect anyone to hand-edit it.
_LIBPQ_TO_ASYNCPG = {"sslmode": "ssl"}
_LIBPQ_UNSUPPORTED = frozenset({"channel_binding"})


def _normalise_asyncpg_query(url: str) -> str:
    """Rewrite libpq connection parameters into the ones asyncpg accepts."""
    base, separator, query = url.partition("?")
    if not separator:
        return url

    params = parse_qsl(query, keep_blank_values=True)
    present = {key for key, _ in params}
    cleaned: list[tuple[str, str]] = []
    for key, value in params:
        if key in _LIBPQ_UNSUPPORTED:
            continue
        target = _LIBPQ_TO_ASYNCPG.get(key)
        if target is not None:
            # An explicit `ssl=` alongside `sslmode=` means someone already did
            # this by hand; keep theirs rather than emit the same key twice.
            if target in present:
                continue
            key = target
        cleaned.append((key, value))

    return f"{base}?{urlencode(cleaned)}" if cleaned else base


# Managed platforms each export a marker variable into the container. Their
# presence is the difference between "someone is running this locally with a
# half-filled .env" (fine) and "this is serving real traffic on development
# defaults" (never fine, and previously silent — /live returns 200 whether or
# not the database was ever configured, so the service looks healthy while every
# real endpoint 500s).
_HOSTED_PLATFORM_MARKERS = (
    "RENDER",  # Render (also sets RENDER_EXTERNAL_URL)
    "DYNO",  # Heroku
    "FLY_APP_NAME",  # Fly.io
    "RAILWAY_ENVIRONMENT",  # Railway
    "K_SERVICE",  # Google Cloud Run
)

_LOCAL_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1", ""})


def _is_hosted() -> bool:
    """Whether the process is running on a managed hosting platform."""
    return any(os.environ.get(marker) for marker in _HOSTED_PLATFORM_MARKERS)


def _host_of(url: str) -> str:
    """Hostname from a URL, lowercased and stripped of brackets/port."""
    return (urlsplit(url).hostname or "").lower()


def _is_local_url(url: str) -> bool:
    """Whether a URL points at the machine the process is running on."""
    return _host_of(url) in _LOCAL_HOSTNAMES


Environment = Literal["development", "test", "staging", "production"]


class Settings(BaseSettings):
    """Validated application settings sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Meta -------------------------------------------------------------
    # Unset on a laptop means development; unset on Render/Fly/Heroku means
    # someone forgot the variable, and "development" there disables JSON logging,
    # exposes /docs, and waves through the placeholder SECRET_KEY.
    environment: Environment = Field(
        default_factory=lambda: "staging" if _is_hosted() else "development"
    )
    debug: bool = False
    app_name: str = "AgriFlow ERP"
    api_v1_prefix: str = "/api/v1"

    # --- Datastores -------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://agriflow:agriflow@localhost:5432/agriflow",
    )
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- Security ---------------------------------------------------------
    secret_key: str = Field(default="dev-insecure-change-me", min_length=8)
    access_token_ttl_seconds: int = 900  # 15 minutes
    refresh_token_ttl_seconds: int = 60 * 60 * 24 * 14  # 14 days

    # Per-IP login throttle. A whole shop signs in through one router at opening
    # time, so this is deliberately generous — brute-force protection comes from
    # the per-account lockout, which counts failures for a single user.
    login_rate_limit: int = Field(default=60, ge=1)
    login_rate_window_seconds: int = Field(default=60, ge=1)

    # --- Auth cookies -----------------------------------------------------
    # Same-origin deployments (frontend proxied under the API's hostname) keep
    # the "lax" default. A frontend on its own domain — Vercel, Netlify, a
    # second Render service — is a cross-site caller, and browsers only attach
    # cookies to those requests when SameSite=None, which they in turn only
    # accept on Secure cookies. ``cookie_secure`` overrides the derived value
    # for the rare case of a non-HTTPS staging host.
    # ``None`` means "derive it" — see ``auth_cookie_samesite``. An explicit
    # value always wins, for the deployment shapes the derivation cannot see.
    cookie_samesite: Literal["lax", "strict", "none"] | None = None
    cookie_secure: bool | None = None

    # --- CORS -------------------------------------------------------------
    # NoDecode: keep pydantic-settings from JSON-decoding the env value so a
    # plain comma-separated string works (handled by ``_split_cors`` below).
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # --- Object storage ---------------------------------------------------
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "agriflow"
    s3_secret_key: str = "agriflow-secret"
    s3_bucket: str = "agriflow"
    s3_region: str = "us-east-1"

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        # Managed hosts (Render, Heroku, Fly) hand out `postgres://` or
        # `postgresql://` URLs. Both are valid DSNs but neither selects an async
        # driver, so SQLAlchemy would fail later with an opaque dialect error.
        # Normalise here so a copy-pasted connection string just works.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                value = "postgresql+asyncpg://" + value[len(prefix) :]
                break
        value = _normalise_asyncpg_query(value)
        _postgres_adapter.validate_python(value)
        return value

    @field_validator("redis_url")
    @classmethod
    def _validate_redis_url(cls, value: str) -> str:
        _redis_adapter.validate_python(value)
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, value: object) -> object:
        """Accept a comma-separated string or a JSON/list for CORS origins."""
        if isinstance(value, str) and not value.startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def auth_cookie_samesite(self) -> Literal["lax", "strict", "none"]:
        """The SameSite attribute to put on auth cookies.

        Needing CORS at all *is* the signal: a same-origin frontend is served
        under the API's hostname and never appears in ``CORS_ORIGINS``. So a
        configured non-local origin means every request is cross-site, and
        browsers only attach cookies to those when SameSite=None. Getting this
        wrong fails quietly — login returns 200 with a user payload, the browser
        discards the cookie, and the next request 401s.
        """
        if self.cookie_samesite is not None:
            return self.cookie_samesite
        if any(not _is_local_url(origin) for origin in self.cors_origins):
            return "none"
        return "lax"

    @property
    def auth_cookie_secure(self) -> bool:
        """Whether auth cookies carry the ``Secure`` attribute.

        SameSite=None is meaningless without it — browsers drop such cookies
        outright — so it is forced on there regardless of environment.

        Hosted platforms terminate TLS and serve only over HTTPS, so auth
        cookies there get ``Secure`` whether the environment is called staging
        or production. Without this a demo deployment sends session cookies that
        a downgraded request would happily replay over plaintext.
        """
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.auth_cookie_samesite == "none" or self.is_production or _is_hosted()

    def enforce_production_safety(self) -> None:
        """Reject insecure or unconfigured defaults before serving traffic."""
        if self.is_production and self.secret_key == "dev-insecure-change-me":
            raise RuntimeError("SECRET_KEY must be set to a strong value in production.")
        # Browsers reject SameSite=None cookies that are not Secure, which would
        # break every login with no server-side error to show for it.
        if self.auth_cookie_samesite == "none" and not self.auth_cookie_secure:
            raise RuntimeError("COOKIE_SAMESITE=none requires COOKIE_SECURE=true (HTTPS).")
        self._enforce_hosted_configuration()

    def _enforce_hosted_configuration(self) -> None:
        """Refuse to boot on a hosting platform while still on dev defaults.

        ``docker-entrypoint.sh`` already guards the Docker path, but a service
        created with a native runtime never runs it. Without this the process
        starts happily, ``/api/v1/live`` returns 200, and the misconfiguration
        only shows up as a 500 on the first real request.

        Only settings with no workable default are fatal. ``CORS_ORIGINS`` is
        deliberately not among them: the frontend proxies ``/api/*`` through its
        own origin (see ``frontend/next.config.mjs``), so a browser never makes a
        cross-origin request and an unset value blocks nothing. It stays a
        startup warning for deployments that do call the API cross-origin.
        """
        if not _is_hosted():
            return

        problems: list[str] = []

        if _is_local_url(self.database_url) and os.environ.get("ALLOW_LOCALHOST_DB") != "true":
            problems.append(
                f"DATABASE_URL points at {_host_of(self.database_url) or 'localhost'!r}. "
                "A container's localhost is itself, not your database. Set it to the "
                "managed Postgres connection string (Neon/Supabase/Render Internal URL). "
                "Set ALLOW_LOCALHOST_DB=true only if you really do mean the local host."
            )

        if self.secret_key == "dev-insecure-change-me":
            problems.append(
                "SECRET_KEY is still the public placeholder, so auth tokens are forgeable. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )

        if problems:
            listed = "\n".join(f"  {n}. {problem}" for n, problem in enumerate(problems, 1))
            raise RuntimeError(
                "Refusing to start: this looks like a hosted deployment, but required "
                f"configuration is missing.\n{listed}\n"
                "  Set these on the service and redeploy. See docs/DEPLOYMENT.md."
            )


@lru_cache
def get_settings() -> Settings:
    """Return a cached, validated Settings instance."""
    settings = Settings()
    settings.enforce_production_safety()
    return settings
