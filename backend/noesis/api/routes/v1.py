"""
v1 API router aggregate.

Mount everything under the ``/v1`` prefix so URL-versioning is the default
from day one.  Future ``v2/`` can live alongside without touching this file.

Usage::

    from noesis.api.routes.v1 import router as v1_router
    app.include_router(v1_router, prefix="/v1")
"""

from __future__ import annotations

from fastapi import APIRouter

from noesis.api.routes.health import router as health_router
from noesis.api.routes.kernel import router as kernel_router
from noesis.api.routes.v1_m3 import auth_router, observability_router
from noesis.api.routes.v1_m5 import router as m5_router
from noesis.api.routes.v1_metrics import router as metrics_router

router = APIRouter(tags=["v1"])

# Mount v1 endpoints here as they ship (M1 adds /chat /plans /runs etc.)
router.include_router(health_router)
router.include_router(kernel_router)
router.include_router(auth_router)
router.include_router(observability_router)
router.include_router(m5_router)
router.include_router(metrics_router)

__all__ = ["router"]
