"""
Pytest plugin + shared fixtures.

Keep this file small; every milestone adds fixtures to the appropriate
``tests/unit/conftest.py`` or ``tests/integration/conftest.py`` below it.

Test marker semantics (registered in pyproject.toml):
    unit        — pure Python, no network / external services (fast, always runs)
    integration — needs DB/Qdrant/Redis up (slower, runs in CI if services are up)
    e2e         — full system (manual trigger + staging env only)
    slow        — anything over ~1s; excluded by default on local dev
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from noesis.config import Settings

# ---------------------------------------------------------------------------
# Async event loop: scope=session avoids re-creating the loop per module.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
def event_loop_policy() -> Iterator[asyncio.AbstractEventLoopPolicy]:  # pragma: no cover
    """Return the default event loop policy (overrides pytest-asyncio default)."""
    yield asyncio.DefaultEventLoopPolicy()


# ---------------------------------------------------------------------------
# Minimal test Settings — in-memory SQLite, no external provider keys required.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
def test_settings(monkeypatch) -> Settings:  # type: ignore[no-untyped-def]
    """Isolated test settings.  Real provider keys are never needed for unit tests."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-change-me-for-tests-only")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("QDRANT_URL", "http://localhost:6333")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("DEBUG", "true")

    from noesis.config import get_settings

    get_settings.cache_clear()
    return get_settings()


@pytest_asyncio.fixture
async def in_memory_sql(test_settings: Settings) -> AsyncIterator[AsyncSession]:
    """In-memory SQLite session + schema created per-test."""
    from noesis.database.sql import Base

    engine = create_async_engine(test_settings.database_url, echo=False, future=True)
    TestSession = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSession() as sess:
        yield sess

    await engine.dispose()


@pytest_asyncio.fixture
def test_client(test_settings: Settings) -> Iterator[TestClient]:
    """``TestClient`` against the real FastAPI app wired with test settings.

    Uses the context-manager form of ``TestClient`` so FastAPI's lifespan
    actually runs (container, kernel start, init_database).  This is
    required for any endpoint that reads ``app.state.kernel``.
    """
    from noesis.api.main import create_app
    from noesis.database import sql as _sql

    # Ensure singleton engine / session factory state from a prior test
    # (same process) doesn't leak state between tests.
    _sql._engine = None
    _sql._session_factory = None

    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
