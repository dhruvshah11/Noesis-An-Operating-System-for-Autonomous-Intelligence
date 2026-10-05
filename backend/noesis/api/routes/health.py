"""
Health + Readiness probes.

Three endpoints (standard for Kubernetes-style deployments):

* ``GET  /health/livez``    — Liveness: 200 if the Python process is alive.
* ``GET  /health/readyz``   — Readiness: 200 only if *every* dependency
                              (SQLite, Qdrant, Redis) answers its probe.
* ``GET  /health``          — Convenience alias for readyz, including a
                              pretty summary of subsystem statuses.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from typing import Literal

from fastapi import APIRouter
from sqlalchemy import text

from noesis.api.deps import RequestID, err_envelope, ok_envelope
from noesis.database.sql import async_session
from noesis.logging import get_logger
from noesis.types import APIEnvelope

log = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


Status = Literal["pass", "warn", "fail"]


@dataclass(slots=True)
class SubsystemHealth:
    name: str
    status: Status
    latency_ms: float
    error: str | None = None


async def _probe_sqlite() -> SubsystemHealth:
    try:
        t0 = asyncio.get_event_loop().time()
        async with async_session()() as sess:
            (await sess.execute(text("SELECT 1"))).scalar_one()
        return SubsystemHealth("sql", "pass", round((asyncio.get_event_loop().time() - t0) * 1000, 2))
    except Exception as exc:
        log.warning("health.sql.fail", error=str(exc))
        return SubsystemHealth("sql", "fail", 0.0, error=str(exc))


async def _probe_redis() -> SubsystemHealth:
    try:
        from noesis.database.redis import get_redis

        t0 = asyncio.get_event_loop().time()
        client = get_redis()
        await client.ping()
        return SubsystemHealth("redis", "pass", round((asyncio.get_event_loop().time() - t0) * 1000, 2))
    except Exception as exc:
        log.warning("health.redis.fail", error=str(exc))
        return SubsystemHealth("redis", "fail", 0.0, error=str(exc))


async def _probe_qdrant() -> SubsystemHealth:
    try:
        from noesis.database.qdrant import get_qdrant

        t0 = asyncio.get_event_loop().time()
        store = get_qdrant()
        # List collections is the lightest "does the server respond?" call.
        _ = [c async for c in store.client.get_collections()]
        return SubsystemHealth("qdrant", "pass", round((asyncio.get_event_loop().time() - t0) * 1000, 2))
    except Exception as exc:
        log.warning("health.qdrant.fail", error=str(exc))
        return SubsystemHealth("qdrant", "fail", 0.0, error=str(exc))


@router.get("/livez", response_model=APIEnvelope[dict])
async def livez(request_id: RequestID) -> APIEnvelope[dict]:
    """Liveness probe — always responds 200 while the app is alive."""
    return ok_envelope({"status": "pass"}, request_id=request_id)


@router.get("/readyz", response_model=APIEnvelope[dict])
async def readyz(request_id: RequestID) -> APIEnvelope[dict]:
    """Readiness probe — fails 503 if any subsystem probe fails."""
    subsystems = await asyncio.gather(_probe_sqlite(), _probe_redis(), _probe_qdrant())
    overall: Status = "pass" if all(s.status == "pass" for s in subsystems) else "fail"
    payload = {
        "status": overall,
        "checks": {s.name: asdict(s) for s in subsystems},
    }
    if overall == "pass":
        return ok_envelope(payload, request_id=request_id)
    return err_envelope(
        "One or more subsystems are unhealthy",
        request_id=request_id,
        meta=payload,
    )


@router.get("", response_model=APIEnvelope[dict])
async def health(request_id: RequestID) -> APIEnvelope[dict]:
    """Combined health view (convenience alias for /readyz)."""
    return await readyz(request_id)
