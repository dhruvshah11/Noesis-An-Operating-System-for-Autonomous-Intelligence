"""C1 MAC claim-suite: GET /llm/benchmark — 4/4 capability-gate pattern.

Claim C1 (MAC): every endpoint that triggers live LLM provider calls (and
can burn budget / saturate GPU capacity) MUST reject callers whose
capability token lacks ``llm.benchmark.read``.

4 assertions per claim-suite (1 ALLOW + 3 DENY variants):
  Test 1 — ALLOW: token carries ``llm.benchmark.read`` → 200
  Test 2 — DENY: token only has unrelated ``memory.read`` → 403 / DENY envelope
  Test 3 — DENY: token signature invalid / TTL expired → 403 / DENY envelope
  Test 4 — DENY: token carries ``llm.*`` with explicit DENY (negative) mask → 403
"""

from __future__ import annotations

import base64
import hmac
import json
import time
from hashlib import sha256
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from noesis.config import get_settings
from noesis.kernel.capabilities import CapabilityToken

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    pass


REQUIRED_CAP = "llm.benchmark.read"
ENDPOINT = "/llm/benchmark"


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(payload_json: str, key: bytes) -> bytes:
    return hmac.new(key, payload_json.encode("utf-8"), sha256).digest()


def _build_cap_headers(
    token_id: UUID,
    caps: list[str],
    *,
    deny_mask: list[str] | None = None,
    expired: bool = False,
    signature_invalid: bool = False,
    owner: str = "test-agent",
    workspace_id: str = "test-workspace",
) -> dict[str, str]:
    """Build properly-signed X-Noesis-Capability-Token headers.

    Mirror of the helper in the bench_results claim-suite — kept
    intentionally duplicated (not imported) so each claim-suite file is
    self-contained and readable by auditors without cross-file jumps.
    """
    settings = get_settings()
    key = settings.claim_suites_hmac_secret.get_secret_value().encode("utf-8")

    now = int(time.time())
    expires = 1 if expired else now + 3600  # 1h TTL normally, 1970 for expired

    payload = {
        "owner": owner,
        "workspace_id": workspace_id,
        "expires_at_unix_s": expires,
        "capabilities": list(caps),
        "deny_masks": list(deny_mask or []),
        "issued_at_unix_s": now,
    }
    payload_json = json.dumps(payload, sort_keys=True)
    payload_b64 = _b64url_encode(payload_json.encode("utf-8"))

    if signature_invalid:
        wrong_key = b"wrong-key-for-testing-tampered-sig"
        mac = _sign(payload_json, wrong_key)
    else:
        mac = _sign(payload_json, key)

    mac_b64 = _b64url_encode(mac)
    token = f"{payload_b64}.{mac_b64}"

    return {
        "X-Noesis-Capability-Token": token,
    }


@pytest.mark.claim_suite
@pytest.mark.C1
@pytest.mark.MAC
class TestClaimC1MACLLMBenchmark:
    """C1 MAC capability-gate claim for GET /llm/benchmark."""

    # ------------------------------------------------------------------
    # Test 1: ALLOW — wide token with explicit llm.benchmark.read → 200
    # ------------------------------------------------------------------

    def test_allow_wide_token_with_llm_benchmark_read(
        self,
        test_client: TestClient,
    ) -> None:
        """C1-ALLOW: capability token carrying ``llm.benchmark.read`` MUST pass."""
        token = CapabilityToken(
            id=uuid4(),
            owner_agent_id="claim-audit-agent-002",
            workspace_id="llm-bench-ws",
        )
        headers = _build_cap_headers(
            token.id,
            caps=[REQUIRED_CAP, "llm.chat", "workspace.read"],
            owner=token.owner_agent_id,
            workspace_id=token.workspace_id or "llm-bench-ws",
        )
        resp = test_client.get(ENDPOINT, headers=headers)

        assert resp.status_code == 200, (
            f"ALLOW path must return 200 with {REQUIRED_CAP} capability; "
            f"got {resp.status_code}: {resp.text[:300]}"
        )
        body = resp.json()
        assert body.get("ok") is True, "Envelope ok must be True on ALLOW path"
        assert "data" in body
        assert "provider" in body["data"], "BenchmarkResult schema: provider field required"
        assert "prompt_tokens_per_sec" in body["data"]

    # ------------------------------------------------------------------
    # Test 2: DENY — token lacks llm.benchmark.read (only memory.read) → 403
    # ------------------------------------------------------------------

    @pytest.mark.claim_suite
    @pytest.mark.C1
    @pytest.mark.MAC
    def test_deny_missing_llm_benchmark_read_cap(
        self,
        test_client: TestClient,
    ) -> None:
        """C1-DENY-1: token without ``llm.benchmark.read`` MUST be rejected."""
        token = CapabilityToken(
            id=uuid4(),
            owner_agent_id="rogue-memory-agent-505",
            workspace_id=None,
        )
        headers = _build_cap_headers(
            token.id,
            caps=["memory.read"],
            owner=token.owner_agent_id,
            workspace_id="llm-bench-ws",
        )
        resp = test_client.get(ENDPOINT, headers=headers)

        assert resp.status_code == 403, (
            f"DENY path must return 403 when {REQUIRED_CAP} is absent; "
            f"got {resp.status_code} — gate not enforced?"
        )
        body = resp.json()
        assert body.get("ok") is False, "DENY envelope must carry ok=false"
        err = body.get("error") or ""
        assert REQUIRED_CAP in err or "capability" in err.lower(), (
            f"DENY error must name the missing cap '{REQUIRED_CAP}'; got: {err}"
        )

    # ------------------------------------------------------------------
    # Test 3: DENY — token TTL expired / invalid signature → 403
    # ------------------------------------------------------------------

    @pytest.mark.claim_suite
    @pytest.mark.C1
    @pytest.mark.MAC
    def test_deny_expired_token_or_bad_signature(
        self,
        test_client: TestClient,
    ) -> None:
        """C1-DENY-2: forged / stale tokens MUST be rejected even if caps look right."""
        token = CapabilityToken(
            id=uuid4(),
            owner_agent_id="replay-attack-agent-0xBEEF",
            workspace_id="llm-bench-ws",
        )
        headers_expired = _build_cap_headers(
            token.id,
            caps=[REQUIRED_CAP],
            expired=True,
            owner=token.owner_agent_id,
            workspace_id=token.workspace_id or "llm-bench-ws",
        )
        resp = test_client.get(ENDPOINT, headers=headers_expired)

        assert resp.status_code == 403, (
            f"Expired token must yield 403; got {resp.status_code}"
        )
        body = resp.json()
        assert body.get("ok") is False

        headers_badsig = _build_cap_headers(
            token.id,
            caps=[REQUIRED_CAP],
            signature_invalid=True,
            owner=token.owner_agent_id,
            workspace_id=token.workspace_id or "llm-bench-ws",
        )
        resp2 = test_client.get(ENDPOINT, headers=headers_badsig)
        assert resp2.status_code == 403, (
            f"Tampered-sig token must yield 403; got {resp2.status_code}"
        )
        body2 = resp2.json()
        assert body2.get("ok") is False
        assert (body2.get("error") or "").lower() in {
            "invalid_token",
            "token_invalid",
            "unauthorized",
        } or "signature" in (body2.get("error") or "").lower() or "mac" in (body2.get("error") or "").lower()

    # ------------------------------------------------------------------
    # Test 4: DENY — llm.* wildcard with explicit DENY (negative) mask
    # ------------------------------------------------------------------

    @pytest.mark.claim_suite
    @pytest.mark.C1
    @pytest.mark.MAC
    def test_deny_wildcard_deny_mask_overrides_allow(
        self,
        test_client: TestClient,
    ) -> None:
        """C1-DENY-3: explicit DENY mask ``llm.*`` MUST trump any allow-list."""
        token = CapabilityToken(
            id=uuid4(),
            owner_agent_id="restricted-datascience-agent-202",
            workspace_id="llm-bench-ws",
        )
        headers = _build_cap_headers(
            token.id,
            caps=[REQUIRED_CAP, "memory.read", "workspace.read"],
            deny_mask=["llm.*"],
            owner=token.owner_agent_id,
            workspace_id=token.workspace_id or "llm-bench-ws",
        )
        resp = test_client.get(ENDPOINT, headers=headers)

        assert resp.status_code == 403, (
            f"DENY mask llm.* must override allow of {REQUIRED_CAP}; "
            f"got {resp.status_code} — negative-capability precedence broken?"
        )
        body = resp.json()
        assert body.get("ok") is False
        err = body.get("error") or ""
        assert "deny" in err.lower() or "forbidden" in err.lower(), (
            f"DENY-mask rejection must mention deny/forbidden; got: {err}"
        )
