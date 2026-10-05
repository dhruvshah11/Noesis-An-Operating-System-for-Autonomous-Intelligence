"""
Unit tests for :mod:`astra.config` + :class:`Settings`.

Focus on the "interesting" validation logic — not on verifying that
Pydantic can parse env vars (that's upstream's job).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from noesis.config import Settings


def test_settings_defaults_for_tests(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """With SECRET_KEY set (minimum viable), settings must parse cleanly."""
    monkeypatch.setenv("SECRET_KEY", "abc")
    s = Settings()
    assert s.app_name == "Noesis"
    assert s.app_env == "development"
    # LLMSettings field is named ``default_provider`` (not ``llm_default_provider``).
    assert s.default_provider == "openai"


def test_debug_forbidden_in_production(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Production environments must refuse DEBUG=true."""
    monkeypatch.setenv("SECRET_KEY", "abc")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEBUG", "true")
    with pytest.raises(ValidationError, match="DEBUG must be False"):
        Settings()


def test_temperature_clamped() -> None:
    """Test Field(ge=0, le=2) directly on construction — avoids pydantic-settings'
    own coercion of environment strings, which raises SettingsError instead of
    the underlying ValidationError we care about for the API contract."""
    with pytest.raises(ValidationError):
        # Invalid: temperature > 2.0
        Settings(  # type: ignore[call-arg]
            secret_key="test-key",
            temperature=5.0,
        )
    # Also test invalid negative.
    with pytest.raises(ValidationError):
        Settings(  # type: ignore[call-arg]
            secret_key="test-key",
            temperature=-1.0,
        )
    # Edge values pass.
    s = Settings(  # type: ignore[call-arg]
        secret_key="test-key",
        temperature=0.0,
        max_tokens=1,
    )
    assert s.temperature == 0.0
    s2 = Settings(  # type: ignore[call-arg]
        secret_key="test-key",
        temperature=2.0,
        max_tokens=1_000_000,
    )
    assert s2.temperature == 2.0


def test_cors_origins_csv_parsing(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """CSV CORS env string is split, whitespace-trimmed, and blanks are dropped.

    Duplicates are also removed by the post-validator dedupe."""
    monkeypatch.setenv("SECRET_KEY", "abc")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.com, http://b.com,, http://c.com, http://a.com")
    s = Settings()
    assert s.cors_origins == ["http://a.com", "http://b.com", "http://c.com"]


def test_cors_origins_json_list_parses(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """BeforeValidator also accepts JSON array literals."""
    monkeypatch.setenv("SECRET_KEY", "abc")
    monkeypatch.setenv("CORS_ORIGINS", '["https://x.com","https://y.com"]')
    s = Settings()
    assert s.cors_origins == ["https://x.com", "https://y.com"]
