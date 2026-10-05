"""
Persistence layer.

Three backends:
  * :mod:`astra.database.sql`    — SQLAlchemy async (SQLite / Postgres) for
    structured relational data (users, conversations, tasks).
  * :mod:`astra.database.qdrant` — Qdrant vector DB for semantic search /
    memory embeddings / RAG chunks.
  * :mod:`astra.database.redis`  — Redis for ephemeral cache, rate-limit
    counters, and (future) Celery/RQ task broker.

``qdrant_client`` is imported **lazily** so the package can be imported
even when ``qdrant_client`` Python bindings aren't installed (e.g. bare
unit-test runs, minimal dev installs).  Use :func:`get_qdrant` /
:class:`QdrantStore` via attribute access — ``ImportError`` will only
be raised if you actually instantiate a Qdrant object with missing deps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from noesis.database.redis import get_redis
from noesis.database.sql import async_session, init_database, sql_engine

if TYPE_CHECKING:  # pragma: no cover
    from noesis.database.qdrant import QdrantStore


def __getattr__(name: str) -> object:
    """Lazy-fallback attribute loader for Qdrant types."""
    if name in ("QdrantStore", "get_qdrant"):
        from noesis.database.qdrant import QdrantStore as _QdrantStore
        from noesis.database.qdrant import get_qdrant as _get_qdrant

        globals()["QdrantStore"] = _QdrantStore
        globals()["get_qdrant"] = _get_qdrant
        return _QdrantStore if name == "QdrantStore" else _get_qdrant
    raise AttributeError(f"module astra.database has no attribute {name!r}")


__all__ = [
    "QdrantStore",
    "async_session",
    "get_qdrant",
    "get_redis",
    "init_database",
    "sql_engine",
]
