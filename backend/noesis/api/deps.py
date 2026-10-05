"""
FastAPI dependency injection helpers.

Keep these pure (no hidden state) so they're composable + testable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from noesis.database.sql import async_session
from noesis.types import APIEnvelope

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a per-request SQLAlchemy ``AsyncSession``, closed on teardown."""
    async with async_session()() as session:
        try:
            yield session
        finally:
            await session.close()


DBSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_request_id(request: Request) -> str:
    """Return the current request's ``X-Request-ID`` (auto-generated if missing)."""
    rid = request.state.request_id
    return rid  # type: ignore[no-any-return]


RequestID = Annotated[str, Depends(get_request_id)]


def ok_envelope(
    data: object | None,
    *,
    request_id: str | None = None,
    meta: dict | None = None,
) -> APIEnvelope[object]:
    return APIEnvelope(ok=True, data=data, request_id=request_id, meta=meta or {})


def err_envelope(
    error: str,
    *,
    request_id: str | None = None,
    meta: dict | None = None,
) -> APIEnvelope[object]:
    return APIEnvelope(ok=False, error=error, request_id=request_id, meta=meta or {})
