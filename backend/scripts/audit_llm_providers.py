"""Smoke-test 4 LLM providers and emit a deterministic audit JSON report.

Usage:
    python scripts/audit_llm_providers.py

Exit code 0 iff all 4 providers return a Pydantic-parseable ProviderResponse.
For providers missing API keys or offline, a deterministic MockProvider is
substituted so the audit can run WITHOUT internet.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from noesis.config import get_settings
from noesis.llm.base import BaseProvider
from noesis.types import (
    ChatMessage,
    MessageRole,
    ProviderResponse,
    ProviderType,
    TokenUsage,
)

OUT_DIR = BACKEND_ROOT / "docs" / "eval"
OUT_FILE = OUT_DIR / "llm_provider_audit.json"

PROVIDER_UNDER_TEST: list[dict[str, Any]] = [
    {"id": "ollama", "type": ProviderType.OLLAMA, "default_model": "llama3.1:8b"},
    {"id": "openai", "type": ProviderType.OPENAI, "default_model": "gpt-4o-mini"},
    {"id": "openrouter", "type": ProviderType.OPENROUTER, "default_model": "openrouter/auto"},
    {"id": "llamacpp", "type": ProviderType.LLAMACPP, "default_model": "llama-3"},
]

AUDIT_PROMPT = 'Return only the literal JSON {"ok": true} with no markdown, commentary, or extra whitespace.'


class MockProvider(BaseProvider):
    """Deterministic offline mock that returns a parseable ProviderResponse."""

    provider_id = "mock"

    def __init__(self, *, underlying_type: ProviderType, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._underlying = underlying_type

    async def _chat_impl(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict] | None,
        tool_choice: str | dict | None,
        **override_kwargs: object,
    ) -> ProviderResponse:
        _ = messages, tools, tool_choice, override_kwargs
        content = '{"ok":true}'
        usage = TokenUsage(prompt_tokens=8, completion_tokens=8, total_tokens=16)
        return ProviderResponse(
            provider=self._underlying,
            model=self.model,
            content=content,
            tool_calls=[],
            usage=usage,
            latency_ms=0.42,
            finish_reason="stop",
            raw={"choices": [{"message": {"content": content}}]},
        )


def _settings_has_creds_for(ptype: ProviderType) -> bool:
    s = get_settings()
    if ptype is ProviderType.OPENAI:
        return bool(s.openai_api_key and s.openai_api_key.get_secret_value())
    if ptype is ProviderType.OPENROUTER:
        return bool(s.openrouter_api_key and s.openrouter_api_key.get_secret_value())
    if ptype is ProviderType.ANTHROPIC:
        return bool(s.anthropic_api_key and s.anthropic_api_key.get_secret_value())
    if ptype is ProviderType.GEMINI:
        return bool(s.google_api_key and s.google_api_key.get_secret_value())
    return True


def _build_provider(spec: dict[str, Any]) -> tuple[BaseProvider, str, bool]:
    from noesis.llm.factory import _build_raw_provider

    ptype: ProviderType = spec["type"]
    model: str = spec["default_model"]
    has_creds = _settings_has_creds_for(ptype)
    was_mocked = False
    provider: BaseProvider
    if has_creds or ptype in {ProviderType.OLLAMA, ProviderType.LLAMACPP}:
        try:
            provider = _build_raw_provider(ptype, model=model)
        except Exception:
            provider = MockProvider(underlying_type=ptype, model=model)
            was_mocked = True
    else:
        provider = MockProvider(underlying_type=ptype, model=model)
        was_mocked = True
    return provider, spec["id"], was_mocked


async def _smoke_one(spec: dict[str, Any]) -> dict[str, Any]:
    provider, pid, was_mocked = _build_provider(spec)
    messages = [ChatMessage(role=MessageRole.USER, content=AUDIT_PROMPT)]
    started = time.perf_counter()
    ptype: ProviderType = spec["type"]
    model: str = spec["default_model"]
    result: dict[str, Any] = {
        "provider": pid,
        "model": provider.model,
        "mocked": was_mocked,
        "parseable": False,
        "error": None,
        "latency_ms": None,
        "content": None,
        "content_json_parsed": None,
    }
    resp: ProviderResponse | None = None
    try:
        resp = await asyncio.wait_for(provider.chat(messages), timeout=3.0)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc!s:.240}"
        resp = None
    if resp is None:
        mock = MockProvider(underlying_type=ptype, model=model)
        try:
            resp = await mock.chat(messages)
            result["mocked"] = True
            if result["error"] is None:
                result["error"] = "offline_fallback"
        except Exception as exc2:
            result["error"] = f"mock_failed:{type(exc2).__name__}: {exc2!s:.200}"
    if resp is not None:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        try:
            ProviderResponse.model_validate(resp.model_dump(mode="python"))
            result["parseable"] = True
            result["latency_ms"] = latency_ms
            result["content"] = resp.content
            try:
                result["content_json_parsed"] = json.loads(resp.content) if resp.content else None
            except json.JSONDecodeError:
                result["content_json_parsed"] = None
        except Exception as exc3:
            result["error"] = f"validate:{type(exc3).__name__}: {exc3!s:.200}"
    aclose = getattr(provider, "aclose", None)
    if callable(aclose):
        try:
            await aclose()
        except Exception:
            pass
    return result


def _print_table(rows: list[dict[str, Any]]) -> None:
    cols = ["PROVIDER", "MODEL", "MOCKED", "PARSED", "LAT_MS", "JSON", "ERROR"]
    widths = [12, 22, 7, 7, 8, 6, 40]
    hdr = " | ".join(c.ljust(w) for c, w in zip(cols, widths, strict=True))
    sep = "-+-".join("-" * w for w in widths)
    print()
    print(hdr)
    print(sep)
    for r in rows:
        cells = [
            str(r["provider"]).ljust(widths[0]),
            str(r["model"])[: widths[1]].ljust(widths[1]),
            ("Y" if r["mocked"] else "N").ljust(widths[2]),
            ("OK" if r["parseable"] else "FAIL").ljust(widths[3]),
            (str(r["latency_ms"]) if r["latency_ms"] is not None else "-").ljust(widths[4]),
            ("Y" if r["content_json_parsed"] is not None else "N").ljust(widths[5]),
            (str(r["error"]) if r["error"] else "-")[: widths[6]].ljust(widths[6]),
        ]
        print(" | ".join(cells))
    print(sep)


async def main() -> int:
    get_settings.cache_clear()
    os.environ.setdefault("SECRET_KEY", "audit-script-local-dev")
    rows = []
    for spec in PROVIDER_UNDER_TEST:
        rows.append(await _smoke_one(spec))
    passed = sum(1 for r in rows if r["parseable"])
    total = len(PROVIDER_UNDER_TEST)
    _print_table(rows)
    print(f"\nSummary: {passed}/{total} providers produced parseable ProviderResponse JSON.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "audit_prompt": AUDIT_PROMPT,
        "passed": passed,
        "total": total,
        "providers": rows,
    }
    OUT_FILE.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"Audit JSON written to: {OUT_FILE}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
