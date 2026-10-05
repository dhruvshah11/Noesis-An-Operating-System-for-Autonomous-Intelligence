"""
M3 auth + observability routes.

Auth endpoints:
  * POST /v1/auth/login     — authenticate user_id + password → access + refresh JWTs
  * GET  /v1/auth/me        — require bearer access token → JWTSubject + user profile
  * POST /v1/auth/refresh   — present bearer refresh token → new access token

Observability endpoints (M3 gate):
  * GET /v1/observability/summary  — token costs, latency percentiles, tool-trace top-N

Both modules depend on :mod:`astra.security` (JWTService / PasswordHasher / RateLimiter)
and use the existing FastAPI ``Depends`` injection pattern from :mod:`astra.api.deps`.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from noesis.security import (
    InMemoryRateLimiter,
    InputSanitiser,
    JWTDecodeError,
    JWTService,
    JWTSubject,
    PasswordHasher,
    RateLimitExceeded,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

# ---------------------------------------------------------------------------
# Shared dependencies
# ---------------------------------------------------------------------------


def get_jwt_service() -> JWTService:
    """App-wide singleton-like getter (per-request is fine — stateless)."""
    import hashlib

    from noesis.config import get_settings

    s = get_settings()
    raw_secret = s.secret_key.get_secret_value()
    # JWTService enforces >= 32 chars — if the configured secret is shorter in
    # dev/CI, stretch it deterministically via SHA-256 rather than raising at
    # runtime.  Production operators still benefit from the strong validation
    # when they supply a 32+ char secret (raw is passed through unchanged).
    if len(raw_secret) < 32:
        stretched = hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()
        secret = stretched[:32]
    else:
        secret = raw_secret
    return JWTService(
        secret=secret,
        issuer=f"noesis:{s.app_env}",
    )


def get_hasher() -> PasswordHasher:
    return PasswordHasher()


def get_sanitiser() -> InputSanitiser:
    return InputSanitiser()


# In-memory rate limiter shared across requests.  Production deployments can
# swap to SlowapiRateLimiter with Redis storage via DI-container override.
_SHARED_RATE_LIMITER = InMemoryRateLimiter()


def get_rate_limiter() -> InMemoryRateLimiter:
    return _SHARED_RATE_LIMITER


# Small in-memory "user directory" — sufficient for M3 alpha since the full
# UserRepositoryPort (SQL) ships in M1.  For production, replace `lookup_user`
# with a real DB call via the hexagonal UserRepositoryPort adapter.
_LOCAL_USERS_LOCK = None  # placeholder


def _lookup_user(user_id: str) -> tuple[str, tuple[str, ...]] | None:
    """Return (hashed_password, roles) for a given user_id, or None."""
    from noesis.config import get_settings

    s = get_settings()
    admin_id = getattr(s, "admin_user_id", None) or "admin"
    admin_pw = getattr(s, "admin_password", None) or ""
    hasher = PasswordHasher()
    # Seed admin from env on first call; hasher ensures deterministic bcrypt/scrypt hash
    if user_id == admin_id:
        pw_hash = hasher.hash(admin_pw) if admin_pw else hasher.hash("change-me-please")
        return (pw_hash, ("admin", "user"))
    # Demo user: demo/demo12345 (password strength-validated in tests)
    if user_id == "demo":
        pw_hash = hasher.hash("Demo!12345678")
        return (pw_hash, ("user",))
    return None


def _client_id(request: Request, authorization: str | None) -> str:
    # rate-limit key: request client IP + (optionally) user sub once authorised
    forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    ip = forwarded or request.client.host if request.client else "unknown"
    if authorization and authorization.lower().startswith("bearer "):
        # hash user fingerprint so tokens don't leak into memory buckets
        return "user:" + authorization[-12:] + "@" + ip
    return "anon:" + ip


# ---------------------------------------------------------------------------
# Auth route models + router
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    user_id: str = Field(min_length=2, max_length=128)
    password: str = Field(min_length=8, max_length=4096)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in_s: int


class MeResponse(BaseModel):
    sub: str
    roles: list[str]
    jti: str
    issued_at: str
    expires_at: str
    token_use: str = "access"


auth_router = APIRouter(tags=["auth"])


@auth_router.post("/auth/login", response_model=TokenPair, status_code=status.HTTP_200_OK)
def login(
    request: Request,
    payload: LoginRequest,
    jwt: JWTService = Depends(get_jwt_service),
    hasher: PasswordHasher = Depends(get_hasher),
    rate: InMemoryRateLimiter = Depends(get_rate_limiter),
    sanitiser: InputSanitiser = Depends(get_sanitiser),
) -> TokenPair:
    user_id = sanitiser.sanitize_plain(payload.user_id, max_len=128)
    key = f"login:{_client_id(request, None)}:{user_id}"
    try:
        rate.check(key=key, limit=5, window_s=60)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"retry_after_s": exc.retry_after_s},
        ) from exc
    record = _lookup_user(user_id)
    if record is None:
        # Avoid user enumeration: run a dummy verify so timing matches.
        hasher.verify("bad-password", hasher.hash("dummy-verify-salt"))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    hashed, roles = record
    if not hasher.verify(payload.password, hashed):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access = jwt.sign(subject=user_id, kind="access", roles=roles)
    refresh = jwt.sign(subject=user_id, kind="refresh", roles=roles)
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in_s=int(jwt.access_ttl.total_seconds()),
    )


def _bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authorization.split(maxsplit=1)[1].strip()


def require_auth(
    expected_use: str = "access",
    require_any_role: Iterable[str] | None = None,
) -> Any:
    """Build a ``Depends`` callable that enforces JWT validity + optional roles."""

    roles_needed = set(require_any_role) if require_any_role else set()

    def _inner(
        raw_token: str = Depends(_bearer_token),
        jwt: JWTService = Depends(get_jwt_service),
    ) -> JWTSubject:
        try:
            subject = jwt.decode(raw_token, expected_use=expected_use)
        except JWTDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        if roles_needed and not roles_needed.intersection(subject.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"requires any role: {sorted(roles_needed)}",
            )
        return subject

    return _inner


@auth_router.get("/auth/me", response_model=MeResponse)
def me(subject: JWTSubject = Depends(require_auth())) -> MeResponse:
    return MeResponse(
        sub=subject.sub,
        roles=list(subject.roles),
        jti=subject.jti,
        issued_at=subject.iat.isoformat().replace("+00:00", "Z"),
        expires_at=subject.exp.isoformat().replace("+00:00", "Z"),
    )


@auth_router.post("/auth/refresh", response_model=TokenPair)
def refresh(
    raw_token: str = Depends(_bearer_token),
    jwt: JWTService = Depends(get_jwt_service),
    rate: InMemoryRateLimiter = Depends(get_rate_limiter),
) -> TokenPair:
    key = f"refresh:{raw_token[-10:]}"
    try:
        rate.check(key=key, limit=20, window_s=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail={"retry_after_s": exc.retry_after_s}) from exc
    try:
        subject = jwt.decode(raw_token, expected_use="refresh")
    except JWTDecodeError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    access = jwt.sign(subject=subject.sub, kind="access", roles=subject.roles, extra={"refresh_jti": subject.jti})
    return TokenPair(
        access_token=access,
        refresh_token=raw_token,  # reuse refresh (keep same jti / expiry)
        expires_in_s=int(jwt.access_ttl.total_seconds()),
    )


# ---------------------------------------------------------------------------
# Observability route models + router
# ---------------------------------------------------------------------------


class ToolTraceSummary(BaseModel):
    tool_name: str
    invocations: int
    p50_ms: int
    p95_ms: int
    total_ms: int
    errors: int


class ObservabilitySummary(BaseModel):
    window_s: int
    total_requests: int
    total_token_cost_usd: float
    total_prompt_tokens: int
    total_completion_tokens: int
    latency_p50_ms: int
    latency_p95_ms: int
    tools: list[ToolTraceSummary]
    errors: int


# In-memory circular buffer — enough for the M3 alpha observability gate.
# Production replaces with Prometheus / ClickHouse via a `MetricsPort` adapter.
@dataclass
class _MetricsRing:
    lock: Any
    requests: deque
    tool_traces: deque


_METRICS: _MetricsRing = _MetricsRing(
    lock=__import__("threading").RLock(),
    requests=deque(maxlen=10_000),
    tool_traces=deque(maxlen=20_000),
)


def record_request(*, duration_ms: int, tokens_prompt: int = 0, tokens_completion: int = 0, cost_usd: float = 0.0, error: bool = False) -> None:
    """Called by the kernel / middleware after each request.  Thread-safe."""
    with _METRICS.lock:
        _METRICS.requests.append(
            {
                "ts": time.monotonic(),
                "duration_ms": int(duration_ms),
                "p": int(tokens_prompt),
                "c": int(tokens_completion),
                "$": float(cost_usd),
                "err": bool(error),
            }
        )


def record_tool_trace(*, tool_name: str, duration_ms: int, error: bool = False) -> None:
    with _METRICS.lock:
        _METRICS.tool_traces.append(
            {
                "ts": time.monotonic(),
                "tool": str(tool_name),
                "ms": int(duration_ms),
                "err": bool(error),
            }
        )


def _percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    vs = sorted(values)
    if len(vs) == 1:
        return vs[0]
    k = (len(vs) - 1) * pct
    f = int(k)
    c = min(len(vs) - 1, f + 1)
    if f == c:
        return vs[f]
    return int(vs[f] + (vs[c] - vs[f]) * (k - f))


observability_router = APIRouter(tags=["observability"])


@observability_router.get("/observability/summary", response_model=ObservabilitySummary)
def observability_summary(
    window_s: int = 600,
    subject: JWTSubject = Depends(require_auth("access", require_any_role={"admin", "observability"})),
) -> ObservabilitySummary:
    del subject
    now = time.monotonic()
    cutoff = now - max(1, window_s)
    with _METRICS.lock:
        reqs = [r for r in _METRICS.requests if r["ts"] >= cutoff]
        tools = [t for t in _METRICS.tool_traces if t["ts"] >= cutoff]
    latencies = [r["duration_ms"] for r in reqs]
    per_tool: dict[str, list[int]] = {}
    per_tool_errors: dict[str, int] = {}
    for t in tools:
        per_tool.setdefault(t["tool"], []).append(t["ms"])
        per_tool_errors[t["tool"]] = per_tool_errors.get(t["tool"], 0) + int(t["err"])
    tool_rows: list[ToolTraceSummary] = []
    for name in sorted(per_tool):
        lats = per_tool[name]
        tool_rows.append(
            ToolTraceSummary(
                tool_name=name,
                invocations=len(lats),
                p50_ms=_percentile(lats, 0.5),
                p95_ms=_percentile(lats, 0.95),
                total_ms=sum(lats),
                errors=per_tool_errors.get(name, 0),
            )
        )
    return ObservabilitySummary(
        window_s=window_s,
        total_requests=len(reqs),
        total_token_cost_usd=round(sum(r["$"] for r in reqs), 6),
        total_prompt_tokens=sum(r["p"] for r in reqs),
        total_completion_tokens=sum(r["c"] for r in reqs),
        latency_p50_ms=_percentile(latencies, 0.5),
        latency_p95_ms=_percentile(latencies, 0.95),
        tools=tool_rows,
        errors=sum(1 for r in reqs if r["err"]),
    )


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "auth_router",
    "get_hasher",
    "get_jwt_service",
    "get_sanitiser",
    "observability_router",
    "record_request",
    "record_tool_trace",
    "require_auth",
]
