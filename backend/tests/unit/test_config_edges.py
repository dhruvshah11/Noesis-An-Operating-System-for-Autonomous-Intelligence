"""Coverage-boosting tests for noesis.config uncovered branches."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from noesis.config import Settings, _parse_cors_list


def test_parse_cors_list_empty_string_returns_empty() -> None:
    """Line 31 branch: empty stripped string → []."""
    assert _parse_cors_list("") == []
    assert _parse_cors_list("   ") == []


def test_parse_cors_list_none_and_falsy_returns_empty() -> None:
    """Line 42 branch: non-list, non-str falsy → []."""
    assert _parse_cors_list(None) == []
    assert _parse_cors_list(False) == []


def test_database_url_empty_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Line 80 branch: DATABASE_URL empty → ValueError."""
    monkeypatch.setenv("SECRET_KEY", "abc")
    monkeypatch.setenv("DATABASE_URL", "")
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings()


def test_cors_wildcard_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Line 181 branch: CORS_ORIGINS contains '*' → ValueError."""
    monkeypatch.setenv("SECRET_KEY", "abc")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.com, *")
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings()


def test_staging_requires_explicit_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lines 189-191: staging/prod with default dev secret → ValueError."""
    monkeypatch.setenv("APP_ENV", "staging")
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings()
