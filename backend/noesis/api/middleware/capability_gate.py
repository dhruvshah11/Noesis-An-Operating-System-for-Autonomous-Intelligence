"""Capability-based security gate — FastAPI dependency + request middleware.

Wraps the C1 AND-mask capability system from noesis.kernel.capabilities as a
FastAPI `Depends` injection.  Endpoints annotated with
`Depends(requires_capabilities(...))` will validate the incoming request for a
`X-Noesis-Capability-Token` header.  If it's missing, malformed, expired, or
lacks the required capability name and allow/deny masks permit the action →
raise 403 HTTPException.

This gate is intentionally NARROW for M2 — wired only for bench endpoints
today to close the 6 xfail claim-suites.  Roll out to /v1 routes in M3.
"""

from __future__ import annotations

import fnmatch
import hmac
import json
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import sha256
from typing import TYPE_CHECKING, Annotated

from fastapi import Header, HTTPException, Request, status
from pydantic import BaseModel, Field, ValidationError

from noesis.config import get_settings
from noesis.kernel.capabilities import CapabilityToken  # noqa: F401  (re-exported signature compat)

if TYPE_CHECKING:
    from collections.abc import Callable


class CapabilityTokenPayload(BaseModel):
    """JSON payload we expect inside the b64 token after HMAC passes."""
    owner: str = Field(..., min_length=1)
    workspace_id: str = Field(..., min_length=1)
    expires_at_unix_s: int = Field(..., ge=1700000000)
    capabilities: list[str] = Field(default_factory=list, min_length=0)
    deny_masks: list[str] = Field(default_factory=list, description="AND-mask deny list. If ANY matches req_cap → DENY.")
    issued_at_unix_s: int = Field(default_factory=lambda: int(time.time()))


def _b64url_encode(b: bytes) -> str:
    return urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return urlsafe_b64decode(s + pad)


def _sign(payload_json: str, key: bytes) -> bytes:
    return hmac.new(key, payload_json.encode("utf-8"), sha256).digest()


def _glob_match(pattern: str, value: str) -> bool:
    return fnmatch.fnmatchcase(value, pattern)


def _verify_token(header_value: str, *, required_cap: str | None) -> CapabilityTokenPayload:
    settings = get_settings()
    key = settings.claim_suites_hmac_secret.get_secret_value().encode("utf-8")

    parts = header_value.split(".")
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="C1_DENY_MAC: malformed capability token (expected b64payload.b64mac)",
        )

    payload_b64, mac_b64 = parts
    try:
        payload_bytes = _b64url_decode(payload_b64)
        mac_bytes = _b64url_decode(mac_b64)
    except (ValueError, Exception) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="C1_DENY_MAC: invalid base64 in capability token",
        ) from exc

    expected_mac = _sign(payload_bytes.decode("utf-8"), key)
    if not hmac.compare_digest(mac_bytes, expected_mac):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="C1_DENY_MAC: capability token HMAC signature verification failed",
        )

    try:
        payload_json = json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="C1_DENY_MAC: capability token payload is not valid JSON",
        ) from exc

    try:
        token_payload = CapabilityTokenPayload(**payload_json)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="C1_DENY_MAC: capability token payload schema invalid",
        ) from exc

    now = int(time.time())
    if token_payload.expires_at_unix_s < now:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"C1_DENY_EXPIRED: capability token expired at unix_ts={token_payload.expires_at_unix_s}",
        )

    if required_cap is None:
        return token_payload

    if required_cap not in token_payload.capabilities:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"C1_DENY_MISSING_CAP: caller lacks required capability '{required_cap}' "
                f"(capabilities on token: {', '.join(token_payload.capabilities) or 'none'})"
            ),
        )

    for mask in token_payload.deny_masks:
        if _glob_match(mask, required_cap):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"C1_DENY_MASK: deny mask '{mask}' matched required capability '{required_cap}' "
                    f"(negative capability precedence: deny always wins)"
                ),
            )

    return token_payload


def requires_capabilities(*required: str) -> Callable[..., None]:
    """FastAPI `Depends` factory — assert the caller holds all listed capabilities.

    Usage::

        @router.get("/foo", dependencies=[Depends(requires_capabilities("foo.read"))])
        async def get_foo(): ...

    Empty *required means "any valid, unexpired, correctly-signed token" —
    authentication-only, no authorization.
    """

    caps_list: tuple[str, ...] = tuple(required)

    async def _gate(
        request: Request,
        x_noesis_capability_token: Annotated[
            str | None,
            Header(
                alias="X-Noesis-Capability-Token",
                description="Signed capability token from the kernel (b64payload.b64mac).",
            ),
        ] = None,
    ) -> None:
        _ = request
        if x_noesis_capability_token is None or not x_noesis_capability_token.strip():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "C1_DENY_MISSING_CAP: missing X-Noesis-Capability-Token header "
                    "(MAC-gated endpoint requires a signed capability token)"
                ),
            )

        header_value = x_noesis_capability_token.strip()

        if not caps_list:
            _verify_token(header_value, required_cap=None)
            return

        for cap in caps_list:
            _verify_token(header_value, required_cap=cap)

    return _gate
