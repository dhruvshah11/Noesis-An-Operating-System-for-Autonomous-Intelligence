"""
Structured logging for Noesis.

Two output modes, selected by ``APP_ENV``:
  * ``development`` — colourful, human-readable console logs via structlog.
  * ``staging`` / ``production`` — line-delimited JSON for log aggregators.

The module exposes a single ``get_logger()`` factory that should be used
everywhere instead of ``logging.getLogger`` or ``print``.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from noesis.config import get_settings


def _build_shared_processors() -> list[structlog.types.Processor]:
    """Processors applied in *every* environment — ordered carefully.

    Order matters: timestamps first, then add context, then filter/secrets,
    then format for output.
    """
    return [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        _scrub_secrets,
        structlog.processors.EventRenamer("message"),
    ]


def _scrub_secrets(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Redact well-known secret keys + bearer tokens recursively before emission.

    Walks nested dicts + lists so callers like
    ``log.info("signed in", payload={"auth_token": "…", "Authorization": "Bearer …"})``
    still don't leak credentials.  Matches are case-insensitive.
    """

    sensitive_substrings = (
        "key",
        "token",
        "secret",
        "password",
        "jwt",
        "authorization",
        "auth",
        "credential",
    )

    sentinel_bearer = "bearer "

    def is_sensitive_key(k: object) -> bool:
        if not isinstance(k, str):
            return False
        lower = k.lower()
        return any(s in lower for s in sensitive_substrings)

    def looks_like_bearer(v: object) -> bool:
        if not isinstance(v, str):
            return False
        stripped = v.lstrip()
        return stripped[: len(sentinel_bearer)].lower() == sentinel_bearer

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            out: dict[str, Any] = {}
            for k, v in node.items():
                if is_sensitive_key(k) and isinstance(v, (str, bytes)):
                    out[k] = "***REDACTED***"
                elif isinstance(v, str) and looks_like_bearer(v):
                    out[k] = "***REDACTED_BEARER***"
                else:
                    out[k] = walk(v)
            return out
        if isinstance(node, list):
            return [walk(item) for item in node]
        if isinstance(node, tuple):
            return tuple(walk(item) for item in node)
        if isinstance(node, set):
            # Sets rarely hold secrets, but scrub for paranoia if a string set
            # entry looks like a bare bearer token.
            return {"***REDACTED_BEARER***" if (isinstance(item, str) and looks_like_bearer(item)) else item for item in node}
        if isinstance(node, str) and looks_like_bearer(node):
            return "***REDACTED_BEARER***"
        return node

    return walk(event_dict)  # type: ignore[return-value]


def configure_logging() -> None:
    """Idempotently configure stdlib logging + structlog together.

    Bootstrap-safe: if ``Settings`` validation fails at import-time (e.g.
    pytest collection before a ``.env`` is loaded), we fall back to a
    conservative development-mode renderer so callers of :func:`get_logger`
    at module-import time never raise.
    """
    try:
        settings = get_settings()
        env = settings.app_env
        debug = settings.debug
    except Exception:  # pragma: no cover - defensive safety net
        env = "development"
        debug = False

    log_level = logging.DEBUG if debug or env == "development" else logging.INFO

    shared_processors = _build_shared_processors()

    renderer = structlog.dev.ConsoleRenderer(colors=True) if env == "development" else structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(sys.stdout)
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # Silence noisy third-party loggers.
    for noisy in ("httpx", "urllib3", "uvicorn.access", "httpcore"):
        logging.getLogger(noisy).setLevel(max(log_level, logging.WARNING))


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a typed, bound structlog logger.  Use this everywhere.

    Parameters
    ----------
    name:
        Usually ``__name__`` — mirrored by stdlib logging so structured
        and unstructured logs share source attribution.
    """
    if not structlog.is_configured():
        configure_logging()
    return structlog.stdlib.get_logger(name)
