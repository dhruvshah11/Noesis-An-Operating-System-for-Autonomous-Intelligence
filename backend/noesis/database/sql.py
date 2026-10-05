"""
SQLAlchemy async engine and session management.

Uses the SQLAlchemy 2.0 async API (``async_sessionmaker`` +
``AsyncEngine``).  The same code runs against SQLite in development and
PostgreSQL in production — only ``DATABASE_URL`` changes.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from noesis.config import get_settings
from noesis.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

log = get_logger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all ORM models in Noesis."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def sql_engine() -> AsyncEngine:
    """Return the singleton :class:`AsyncEngine`, creating it on first use."""
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.database_url
        connect_args: dict = {}
        is_sqlite = url.startswith("sqlite")
        if is_sqlite:
            # SQLite async requires ``check_same_thread=False`` plus we turn
            # on WAL to avoid blocking readers during writes.
            connect_args["check_same_thread"] = False
        engine_kwargs: dict[str, Any] = {
            "echo": settings.debug,
            "future": True,
            "connect_args": connect_args,
        }
        if not is_sqlite:
            # SQLite's StaticPool doesn't accept pool_size / max_overflow —
            # skip those for SQLite and keep them for Postgres / MySQL.
            engine_kwargs["pool_pre_ping"] = True
            engine_kwargs["pool_size"] = 5
            engine_kwargs["max_overflow"] = 10
        _engine = create_async_engine(url, **engine_kwargs)
        log.info("db.engine_created", url=url)
    return _engine


def async_session() -> async_sessionmaker[AsyncSession]:
    """Return the singleton session factory, bound to :func:`sql_engine`."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=sql_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Transaction-managed async session context.

    Commits on clean exit, rolls back on exception, always closes.::

        async with session_scope() as sess:
            sess.add(...)
    """
    s = async_session()()
    try:
        yield s
        await s.commit()
    except Exception:
        await s.rollback()
        raise
    finally:
        await s.close()


async def init_database(*, create_tables: bool = True) -> None:
    """Create all schemas / tables + ensure filesystem directories exist.

    Parameters
    ----------
    create_tables:
        If ``True`` (dev convenience) run ``Base.metadata.create_all``.
        In production this parameter should be ``False`` and schema changes
        go through Alembic migrations only.
    """
    import os

    settings = get_settings()
    url = settings.database_url

    # For local SQLite file databases, ensure the directory exists BEFORE we
    # try to create a connection (previously this was done as a side effect
    # inside a Pydantic validator — a code smell we fixed in audit §3.1).
    if url.startswith("sqlite") and ("/" in url or "\\" in url):
        # Typical shape: sqlite+aiosqlite:///./data/noesis.db
        raw_path = url.split("://", 1)[-1].lstrip("/")
        # Remove any query strings (none today, but future-proof)
        raw_path = raw_path.split("?", 1)[0]
        parent = os.path.dirname(os.path.abspath(raw_path))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
            log.info("db.data_dir_created", path=parent)

    engine = sql_engine()
    if create_tables:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    log.info("db.initialised", create_tables=create_tables)
