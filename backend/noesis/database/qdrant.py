"""
Typed Qdrant client wrapper with collection management.

Qdrant stores everything as ``(id, vector, payload)``.  We add a thin
typed layer so callers never have to hand-roll payload dicts:

    store = QdrantStore.from_settings()
    await store.ensure_collection("documents", dims=1536)
    await store.upsert_points("documents", points=[...])
    hits = await store.search("documents", query_vector, top_k=8, filter={...})
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from noesis.config import Settings, get_settings
from noesis.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable
    from uuid import UUID

log = get_logger(__name__)


# Distance metric default: COSINE is standard for text embeddings.
_DEFAULT_DISTANCE = models.Distance.COSINE


@dataclass
class VectorPoint:
    """Domain object for one Qdrant point."""

    id: str | UUID
    vector: list[float]
    payload: dict[str, Any]


@dataclass
class SearchHit:
    """Result of a semantic search."""

    id: str
    score: float
    payload: dict[str, Any]
    vector: list[float] | None = None


class QdrantStore:
    """Thin wrapper around :class:`AsyncQdrantClient`.

    One instance per application (see :func:`get_qdrant`).
    """

    def __init__(self, client: AsyncQdrantClient, *, collection_prefix: str = "noesis") -> None:
        self.client = client
        self.collection_prefix = collection_prefix.rstrip("_") + "_" if collection_prefix else ""

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> QdrantStore:
        settings = settings or get_settings()
        api_key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
        url = str(settings.qdrant_url)
        client = AsyncQdrantClient(url=url, api_key=api_key, prefer_grpc=False)
        log.info("qdrant.connected", url=url, has_api_key=bool(api_key))
        return cls(client, collection_prefix=settings.qdrant_collection_prefix)

    # ------------------------------------------------------------------
    # Collection helpers
    # ------------------------------------------------------------------

    def collection_name(self, name: str) -> str:
        """Prepend the configured prefix so dev/test/prod don't collide."""
        return f"{self.collection_prefix}{name}"

    async def ensure_collection(
        self,
        name: str,
        *,
        dims: int,
        distance: models.Distance = _DEFAULT_DISTANCE,
        recreate: bool = False,
    ) -> str:
        """Create the collection iff missing.  Returns the full prefixed name."""
        full = self.collection_name(name)
        exists = False
        try:
            exists = await self.client.collection_exists(full)
        except (UnexpectedResponse, ConnectionError):
            exists = False
        if exists and recreate:
            await self.client.delete_collection(full)
            exists = False
        if not exists:
            await self.client.create_collection(
                full,
                vectors_config=models.VectorParams(size=dims, distance=distance),
                optimizers_config=models.OptimizersConfigDiff(memmap_threshold=20_000),
            )
            await self.client.create_payload_index(
                full,
                field_name="created_at",
                field_schema=models.PayloadSchemaType.FLOAT,
            )
            log.info("qdrant.collection_created", name=full, dims=dims, distance=distance)
        return full

    async def delete_collection(self, name: str) -> bool:
        full = self.collection_name(name)
        try:
            await self.client.delete_collection(full)
            return True
        except (UnexpectedResponse, ValueError):
            return False

    # ------------------------------------------------------------------
    # Data API
    # ------------------------------------------------------------------

    async def upsert_points(
        self,
        collection: str,
        *,
        points: Iterable[VectorPoint],
        batch_size: int = 256,
    ) -> int:
        """Upsert points in batches.  Returns count inserted."""
        full = self.collection_name(collection)
        batch: list[models.PointStruct] = []
        total = 0
        for p in points:
            batch.append(
                models.PointStruct(
                    id=str(p.id),
                    vector=p.vector,
                    payload={**p.payload, "created_at": datetime.utcnow().timestamp()},
                )
            )
            if len(batch) >= batch_size:
                await self.client.upsert(collection_name=full, points=batch, wait=True)
                total += len(batch)
                batch.clear()
        if batch:
            await self.client.upsert(collection_name=full, points=batch, wait=True)
            total += len(batch)
        if total:
            log.debug("qdrant.upserted", collection=full, count=total)
        return total

    async def search(
        self,
        collection: str,
        *,
        query_vector: list[float],
        top_k: int = 10,
        score_threshold: float | None = None,
        filter: models.Filter | dict | None = None,
        with_vectors: bool = False,
    ) -> list[SearchHit]:
        full = self.collection_name(collection)
        if isinstance(filter, dict):
            filter = models.Filter(**filter)
        results = await self.client.search(
            collection_name=full,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=filter,
            with_vectors=with_vectors,
            with_payload=True,
        )
        return [
            SearchHit(
                id=str(r.id),
                score=r.score,
                payload=r.payload or {},
                vector=list(r.vector) if with_vectors and r.vector is not None else None,
            )
            for r in results
        ]

    async def scroll(
        self,
        collection: str,
        *,
        filter: models.Filter | dict | None = None,
        limit: int = 100,
    ) -> list[SearchHit]:
        full = self.collection_name(collection)
        if isinstance(filter, dict):
            filter = models.Filter(**filter)
        points, _next_offset = await self.client.scroll(
            collection_name=full,
            scroll_filter=filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return [
            SearchHit(
                id=str(p.id),
                score=0.0,
                payload=p.payload or {},
                vector=None,
            )
            for p in points
        ]

    async def delete_points(self, collection: str, *, point_ids: Iterable[str | UUID]) -> int:
        full = self.collection_name(collection)
        ids = [str(pid) for pid in point_ids]
        if not ids:
            return 0
        await self.client.delete(
            collection_name=full,
            points_selector=models.PointIdsList(points=ids),
            wait=True,
        )
        return len(ids)

    async def count(self, collection: str) -> int:
        full = self.collection_name(collection)
        res = await self.client.count(collection_name=full, exact=True)
        return res.count


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_STORE: QdrantStore | None = None


def get_qdrant(settings: Settings | None = None) -> QdrantStore:
    """Return the singleton :class:`QdrantStore`, creating it lazily."""
    global _STORE
    if _STORE is None:
        _STORE = QdrantStore.from_settings(settings)
    return _STORE
