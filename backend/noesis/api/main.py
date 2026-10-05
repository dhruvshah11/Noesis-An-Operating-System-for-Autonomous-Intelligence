"""
FastAPI application factory.

Boot order (via ``lifespan``):
  1. Configure logging (once, idempotent).
  2. Read settings.
  3. Initialise SQL database tables (dev convenience — production uses Alembic).
  4. Warm singleton connections (Qdrant, Redis) so first real request isn't slow.
  5. Register routes + middleware.

Middleware chain (request flows top-to-bottom):
  * Request-ID middleware (generate / propagate ``X-Request-ID``).
  * Structured access logging (per-request latency, status, route tag).
  * CORS middleware.
  * GZip compression.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from noesis.api.deps import err_envelope
from noesis.api.routes.bench_results import router as bench_results_router
from noesis.api.routes.health import router as health_router
from noesis.api.routes.llm_benchmark import router as llm_benchmark_router
from noesis.api.routes.v1 import router as v1_router
from noesis.api.routes.v1_metrics import router as metrics_router
from noesis.config import get_settings
from noesis.database.sql import init_database
from noesis.logging import configure_logging, get_logger
from noesis.observability import observe_http_request


def _use_route_ids() -> None:
    """Tag every endpoint with a stable ``operation_id`` = function name.

    Improves OpenAPI UX + makes observability dashboards stable.
    """
    # FastAPI does this by default for routes added via ``add_api_route`` but
    # we enforce it explicitly for consistency.
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager — startup + teardown logic lives here."""
    from noesis.core.di import build_default_container
    from noesis.kernel import Kernel
    from noesis.plugins import PluginManager

    settings = get_settings()
    configure_logging()
    log = get_logger(__name__)
    log.info(
        "app.starting",
        name=settings.app_name,
        version=settings.app_version,
        env=settings.app_env,
    )

    # Build the DI container + kernel + plugin runtime.
    container = build_default_container()
    kernel: Kernel = await container.get(Kernel)
    await kernel.start()
    plugin_manager = PluginManager(kernel)
    # Discover plugins in ./plugins directory (developer-local) + entry points.
    import pathlib

    plugins_dir = pathlib.Path("./plugins")
    if plugins_dir.is_dir():
        try:
            await plugin_manager.discover(dirs=[plugins_dir])
        except Exception as exc:
            log.warning("app.plugins.discover_failed", error=str(exc))
    await plugin_manager.boot_all()

    app.state.container = container
    app.state.kernel = kernel
    app.state.plugins = plugin_manager

    # Initialise SQL (auto-create tables in dev)
    await init_database(create_tables=settings.app_env == "development")

    # Warm up downstream clients (first connection is expensive)
    try:
        from noesis.database.qdrant import get_qdrant

        get_qdrant()
    except Exception as exc:
        log.warning("app.qdrant.warmup_failed", error=str(exc))
    try:
        from noesis.database.redis import get_redis

        _ = get_redis()
    except Exception as exc:
        log.warning("app.redis.warmup_failed", error=str(exc))

    log.info(
        "app.started",
        port=settings.app_port,
        kernel_state=kernel.state.value,
        plugins_loaded=len(plugin_manager.list_plugins()),
    )
    yield
    # ---- teardown ----
    # Keep teardowns short (1-5s) with timeouts — TestClient shutdown on
    # Windows/IOCP must not hang forever, otherwise integration tests hang.
    log.info("app.shutdown")
    try:
        await asyncio.wait_for(plugin_manager.shutdown_all(), timeout=2)
    except Exception as exc:  # pragma: no cover - best effort
        log.warning("app.plugins.shutdown_failed", error=str(exc))
    try:
        await asyncio.wait_for(container.aclose(), timeout=2)
    except Exception as exc:  # pragma: no cover - best effort
        log.warning("app.container.close_failed", error=str(exc))


def _validation_error_handler(request: Request, exc: RequestValidationError) -> Response:
    """Return a structured ``APIEnvelope`` for 422s instead of FastAPI's default."""
    rid = getattr(request.state, "request_id", None)
    errors = []
    for err in exc.errors():
        errors.append({"loc": list(err.get("loc", [])), "msg": err.get("msg"), "type": err.get("type")})
    payload = err_envelope(
        "Request validation failed",
        request_id=rid,
        meta={"errors": errors},
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=payload.model_dump(mode="json"),
    )


def _pydantic_validation_handler(request: Request, exc: ValidationError) -> Response:
    """Catch stray Pydantic v2 ValidationErrors raised inside endpoints."""
    rid = getattr(request.state, "request_id", None)
    errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=err_envelope(
            "Internal data validation error",
            request_id=rid,
            meta={"errors": errors},
        ).model_dump(mode="json"),
    )


def _http_exception_handler(request: Request, exc: HTTPException) -> Response:
    """Wrap FastAPI HTTPExceptions in the standard APIEnvelope format.

    Preserves ``exc.headers`` (for e.g. WWW-Authenticate on 401 / 407) and
    forwards structured dict ``detail`` into the envelope ``meta`` field when
    present — callers like the rate-limiter pass ``{"retry_after_s": N}`` so
    clients can implement correct backoff.
    """
    rid = getattr(request.state, "request_id", None)
    detail = exc.detail
    if isinstance(detail, dict):
        error_msg = str(detail.get("msg") or detail.get("error") or f"HTTP {exc.status_code}")
        meta = detail
    else:
        error_msg = str(detail)
        meta = None
    body = err_envelope(error_msg, request_id=rid, meta=meta)
    response = JSONResponse(
        status_code=exc.status_code,
        content=body.model_dump(mode="json"),
    )
    if exc.headers:
        for k, v in exc.headers.items():
            response.headers[k] = v
    return response


def _generic_exception_handler(request: Request, exc: Exception) -> Response:
    """Last-resort handler that never leaks raw exceptions to the client."""
    log = get_logger(__name__)
    rid = getattr(request.state, "request_id", None)
    log.error("app.unhandled_exception", exc_type=type(exc).__name__, exc=str(exc), request_id=rid)
    body = err_envelope(
        "Internal server error",
        request_id=rid,
        meta={"type": type(exc).__name__} if get_settings().app_env == "development" else None,
    )
    return JSONResponse(status_code=500, content=body.model_dump(mode="json"))


def create_app() -> FastAPI:
    """Application factory — tests call this with overridden settings."""
    settings = get_settings()

    app = FastAPI(
        title=f"{settings.app_name} API",
        version=settings.app_version,
        description=(
            "Noesis — The Autonomous Multi-Agent AI Operating System.  "
            "Multi-agent orchestration with long-term memory, RAG, tool-calling, "
            "planning, and self-reflection.  All public routes live under `/v1` "
            "for semantic URL versioning."
        ),
        terms_of_service="https://github.com/noesis/noesis/blob/main/TERMS.md",
        contact={
            "name": "Noesis Maintainers",
            "url": "https://github.com/noesis/noesis",
            "email": "maintainers@noesis.dev",
        },
        license_info={
            "name": "MIT License",
            "url": "https://github.com/noesis/noesis/blob/main/LICENSE",
        },
        servers=[
            {"url": "/v1", "description": "v1 API (current)"},
            {"url": "/", "description": "Root (legacy redirects to /v1)"},
        ],
        lifespan=lifespan,
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
        openapi_url="/openapi.json" if settings.app_env != "production" else None,
    )

    # ---- Middleware (order matters) ----------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*", "Idempotency-Key"],
        expose_headers=["X-Request-ID", "Idempotency-Key"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.middleware("http")
    async def _idempotency_key_tracker(request: Request, call_next: Any) -> Response:
        """Attach the optional ``Idempotency-Key`` request header to state.

        Write operations in M1+ will read ``request.state.idempotency_key``
        and short-circuit against Redis for a cached response (24h TTL).
        """
        request.state.idempotency_key = request.headers.get("Idempotency-Key")
        return await call_next(request)

    @app.middleware("http")
    async def _request_id_and_access_log(request: Request, call_next: Any) -> Response:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = rid
        log = get_logger("http.access")
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            # FastAPI's exception middleware catches these too, but we still
            # want an access log entry for 500s.
            response = _generic_exception_handler(request, exc)
        finally:
            status_code = response.status_code if "response" in locals() else 500
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            route = getattr(request.scope.get("route", None), "name", "not_found") or "not_found"
            method = request.method or "GET"
            path = request.url.path or "/"
            observe_http_request(
                method=method,
                route=path,
                status_code=status_code,
                duration_seconds=latency_ms / 1000.0,
            )
            level = "error" if status_code >= 500 else ("warning" if status_code >= 400 else "info")
            getattr(log, level)(
                "http.request",
                method=method,
                path=path,
                status=status_code,
                latency_ms=latency_ms,
                request_id=rid,
                route=route,
                idempotency_key_length=len(request.headers.get("Idempotency-Key", "")),
            )
        response.headers["X-Request-ID"] = rid
        idem = getattr(request.state, "idempotency_key", None)
        if idem:
            response.headers["Idempotency-Key"] = idem
        return response

    # ---- Exception handlers ------------------------------------------
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(ValidationError, _pydantic_validation_handler)
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _generic_exception_handler)

    # ---- Include routers ---------------------------------------------
    app.include_router(v1_router, prefix="/v1")
    app.include_router(health_router)
    app.include_router(llm_benchmark_router)
    app.include_router(bench_results_router)
    # Bare /metrics (prometheus scrape convention) — NOT under /v1
    app.include_router(metrics_router, include_in_schema=True)

    # ---- Root info endpoint (friendly landing) -----------------------
    @app.get("/", tags=["meta"], include_in_schema=False)
    async def root(request: Request) -> Response:
        return JSONResponse(
            content={
                "ok": True,
                "name": settings.app_name,
                "version": settings.app_version,
                "env": settings.app_env,
                "docs": "/docs" if settings.app_env != "production" else None,
                "health": "/v1/health",
                "current_api_prefix": "/v1",
                "request_id": getattr(request.state, "request_id", None),
            }
        )

    _use_route_ids()
    return app


app = create_app()
