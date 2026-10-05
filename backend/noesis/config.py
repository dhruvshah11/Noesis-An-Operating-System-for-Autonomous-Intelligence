"""
Centralised configuration for Noesis.

All settings flow through this module: environment variables take
precedence over `.env` files via Pydantic Settings. Nothing else in
the codebase should read ``os.environ`` directly.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_cors_list(v: Any) -> list[str]:
    """Parse a CORS origin value from the environment.

    Pydantic-Settings normally tries to JSON-decode ``list[...]`` env vars
    first, which fails on plain CSV strings.  We intercept *before* that
    conversion with :class:`BeforeValidator` so both JSON and CSV (and
    already-parsed lists) are accepted.
    """
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str):
        stripped = v.strip()
        if not stripped:
            return []
        # Try JSON first so ["a","b"] literals still work; fall back to CSV.
        try:
            import json

            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except (ValueError, TypeError):
            pass
        return [origin.strip() for origin in stripped.split(",") if origin.strip()]
    return list(v) if v else []


class LLMSettings(BaseSettings):
    """Provider-agnostic LLM configuration knobs."""

    default_provider: Literal["openai", "anthropic", "gemini", "ollama", "openrouter", "llamacpp"] = "openai"
    fallback_provider: Literal["openai", "anthropic", "gemini", "ollama", "openrouter", "llamacpp"] = "ollama"
    default_model: str = "gpt-4o-mini"
    temperature: Annotated[float, Field(ge=0.0, le=2.0)] = 0.2
    max_tokens: Annotated[int, Field(ge=1, le=1_000_000)] = 4096
    embedding_provider: Literal["openai", "ollama"] = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: Annotated[int, Field(ge=64, le=16_384)] = 1536
    timeout: Annotated[float, Field(ge=1.0, le=600.0)] = 120.0


class DatabaseSettings(BaseSettings):
    """Relational / vector / cache connection settings."""

    database_url: str = "sqlite+aiosqlite:///./data/noesis.db"
    qdrant_url: AnyHttpUrl = AnyHttpUrl("http://localhost:6333")
    qdrant_api_key: SecretStr | None = None
    qdrant_collection_prefix: str = "noesis"
    redis_url: str = "redis://localhost:6379/0"

    @field_validator("database_url")
    @classmethod
    def _validate_sqlite_path(cls, v: str) -> str:
        """Validate the SQLite DATABASE_URL *shape* only.

        We deliberately avoid side effects (e.g. ``os.makedirs``) inside a
        validator: validators must be pure.  Directory creation happens in
        :func:`noesis.database.sql.init_database` once application startup is
        confirmed — this avoids spurious ``data/`` folders being created in
        tests that construct Settings objects with throwaway URLs.
        """
        if not v:
            raise ValueError("DATABASE_URL must be a non-empty string")
        return v


_DEV_INSECURE_SECRET_DEFAULT: str = "noesis-dev-insecure-default-change-me-before-production"


class SecuritySettings(BaseSettings):
    """Authentication, authorisation, and rate-limit knobs.

    ``secret_key`` intentionally carries a throwaway default so ``import noesis``
    and pytest collection never raise ``ValidationError`` in local development
    environments.  This placeholder is **explicitly rejected** by
    :class:`Settings` ``model_validator`` for ``staging`` / ``production``
    deployments, guaranteeing no real workload ever ships with a leaked
    well-known secret.
    """

    secret_key: SecretStr = SecretStr(_DEV_INSECURE_SECRET_DEFAULT)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: Annotated[int, Field(ge=1, le=525_600)] = 1440  # 24h
    rate_limit_per_minute: Annotated[int, Field(ge=1, le=10_000)] = 60
    claim_suites_hmac_secret: SecretStr = SecretStr("dev-only-insecure-secret-change-in-prod")


class ProviderCredentials(BaseSettings):
    """API credentials for each supported LLM provider.

    Each credential is optional at startup so the app can boot with a
    subset of providers. The ``LLM Provider Factory`` validates that a
    credential exists *at request time* for the selected provider.
    """

    openai_api_key: SecretStr | None = None
    openai_base_url: AnyHttpUrl | None = None
    openai_org_id: str | None = None

    anthropic_api_key: SecretStr | None = None
    anthropic_base_url: AnyHttpUrl | None = None

    google_api_key: SecretStr | None = None

    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: AnyHttpUrl = AnyHttpUrl("https://openrouter.ai/api/v1")

    ollama_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:11434")
    ollama_model: str = "llama3.1:8b"

    llamacpp_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8080")
    llamacpp_model: str = "llama-3"


class Settings(LLMSettings, DatabaseSettings, SecuritySettings, ProviderCredentials):
    """Root settings object — merge of every domain above."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "Noesis"
    app_version: str = "0.1.0"
    app_host: str = "0.0.0.0"
    app_port: Annotated[int, Field(ge=1, le=65535)] = 8000
    debug: bool = False
    eval_root: str = "docs/eval"

    # NB: declared as ``Any`` (not ``list[str]``) so pydantic-settings EnvSource
    # skips its automatic complex-type JSON parsing attempt, which would fail on
    # plain CSV strings like ``"http://a, http://b"``.  ``_parse_cors_list``
    # normalises the value into a ``list[str]`` afterwards.
    cors_origins: Any = Field(default_factory=lambda: ["http://localhost:3000"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_field(cls, v: Any) -> list[str]:
        return _parse_cors_list(v)

    @field_validator("cors_origins")
    @classmethod
    def _dedupe_and_clean_cors(cls, v: Any) -> list[str]:
        raw = _parse_cors_list(v)
        seen: set[str] = set()
        result: list[str] = []
        for origin in raw:
            if origin not in seen:
                seen.add(origin)
                result.append(origin)
        return result

    @model_validator(mode="after")
    def _debug_for_dev_only(self) -> Settings:
        if self.app_env in {"staging", "production"} and self.debug:
            raise ValueError("DEBUG must be False in staging/production environments")
        # Security guard: CORS wildcard origins cannot be combined with
        # allow_credentials=True (browsers reject this anyway, but we catch
        # it here at startup with a clear error).
        cleaned = _parse_cors_list(self.cors_origins)
        if "*" in cleaned:
            raise ValueError(
                "CORS_ORIGINS cannot include '*' when allow_credentials=True. "
                "Please enumerate exact origins (e.g. http://localhost:3000) or "
                "run behind a reverse proxy that injects credentials-safe headers."
            )
        # Security guard: refuse to boot staging/production with the built-in
        # throwaway dev secret.  Operators MUST set SECRET_KEY explicitly.
        if self.app_env in {"staging", "production"}:
            actual = self.secret_key.get_secret_value()
            if actual == _DEV_INSECURE_SECRET_DEFAULT:
                raise ValueError(
                    "SECRET_KEY must be explicitly set for staging/production "
                    "environments (the dev default is not permitted).  Use a long "
                    "random string, e.g. `python -c 'import secrets; print(secrets.token_urlsafe(64))'`."
                )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton :class:`Settings` instance (cached)."""
    return Settings()  # type: ignore[call-arg]
