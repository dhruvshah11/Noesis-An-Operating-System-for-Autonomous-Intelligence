"""
Prometheus + JSON + JSON metrics route.

Two endpoints:
  GET /metrics           — Prometheus text/plain (OpenMetrics) scrape convention.
  GET /v1/metrics_json   — JSON APIEnvelope with snapshot counters + summaries
                           for the dashboard Metrics page widget.

Note:
  * We deliberately DO NOT register /metrics under the /v1 prefix on the
    router object itself, because Prometheus scrape conventions expect
    /metrics at the server root.  Root /metrics is mounted directly on
    the FastAPI app in astra.api.main:create_app().
  * The dashboard-facing JSON counterpart is mounted as /v1/metrics_json so
    there is exactly 1 route per verb per prefix and no collision between
    routers.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from noesis.observability import render_text, snapshot_as_dict
from noesis.types import APIEnvelope

router = APIRouter(tags=["observability"])


@router.get("/metrics", summary="Prometheus scrape endpoint (root /metrics mount)")
async def prometheus_scrape(request: Request) -> Response:
    """OpenMetrics text-format scrape (see astra.api.main for root /metrics mount)."""
    body, content_type = render_text()
    return Response(content=body, media_type=content_type)


@router.get("/metrics_json", summary="JSON metrics snapshot")
async def metrics_snapshot_json(request: Request) -> APIEnvelope[dict[str, object]]:
    """JSON envelope of counters + summaries totals for the dashboard Metrics page."""
    data = snapshot_as_dict()
    request_id = getattr(request.state, "request_id", None)
    return APIEnvelope(ok=True, data=data, request_id=request_id)


__all__ = ["router"]
