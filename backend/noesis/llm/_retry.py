"""
Unified retry policy for all LLM provider HTTP calls.

Keeping the decorator in *one* file avoids duplicating the identical 4-line
``@retry(reraise=True, stop=stop_after_attempt(4), ...)`` block across 6
provider methods, and lets us tune the policy (backoff, jitter, status codes)
in a single place for all 5 providers.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from noesis.logging import get_logger

log = get_logger(__name__)

# HTTP status codes that we treat as transient and retry.  429 rate-limit
# from providers is the most common, followed by 5xx gateway/load-balancer
# blips during large inference storms.
TRANSIENT_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})

F = TypeVar("F", bound=Callable[..., Any])


class HTTPRetryableError(Exception):
    """Raised by provider HTTP wrappers to signal a retry is warranted.

    Carries the raw status code + response body preview for observability.
    """

    __slots__ = ("body_preview", "status_code")

    def __init__(self, status_code: int, body_preview: str = "") -> None:
        super().__init__(f"HTTP {status_code}: {body_preview[:200]}")
        self.status_code = status_code
        self.body_preview = body_preview[:200]


def _log_retry_attempt(retry_state: RetryCallState) -> None:
    """Emit a structured warn log on every retry (helpful for debugging)."""
    fn_name = getattr(retry_state.fn, "__qualname__", str(retry_state.fn))
    attempt = retry_state.attempt_number
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    log.warning(
        "llm.retry",
        fn=fn_name,
        attempt=attempt,
        exc_type=type(exc).__name__ if exc else None,
        exc=str(exc)[:200] if exc else None,
    )


def with_provider_retry(max_attempts: int = 4, max_wait_s: int = 10) -> Callable[[F], F]:
    """Decorate a provider HTTP method with a safe, transient-error retry.

    Parameters
    ----------
    max_attempts:
        Total attempts (1 initial + N-1 retries).
    max_wait_s:
        Cap on the exponential+jitter backoff (seconds between retries).
    """

    return retry(
        reraise=True,
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(max=max_wait_s),
        retry=retry_if_exception_type(HTTPRetryableError),
        before_sleep=_log_retry_attempt,
    )  # type: ignore[return-value]


__all__ = [
    "TRANSIENT_HTTP_STATUSES",
    "HTTPRetryableError",
    "with_provider_retry",
]
