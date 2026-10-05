"""
Ollama connectivity and model inventory diagnostic script.

Pings the Ollama REST API at ``/api/tags``, reports installed models,
and checks whether recommended code-generation models (DeepSeek / Qwen)
are available.

Exit codes:
  0 → reachable AND qwen OR deepseek model is installed
  1 → unreachable (ConnectionError / timeout / DNS failure)
  2 → reachable but neither qwen nor deepseek installed

CLI:
  py scripts/ollama_ping.py
  py scripts/ollama_ping.py --json
  py scripts/ollama_ping.py --base-url http://gpu-box:11434

Importable:
  from scripts.ollama_ping import ping_ollama_sync
  result = ping_ollama_sync("http://localhost:11434")
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass


BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import httpx

DEFAULT_MODEL_RECOMMENDED = "qwen2.5-coder:7b-instruct-q4_K_M"
DEFAULT_BASE_URL = "http://localhost:11434"
TIMEOUT_S = 5.0


def _empty_result(base_url: str) -> dict[str, Any]:
    return {
        "ok": False,
        "reachable": False,
        "models_count": 0,
        "models": [],
        "default_model_recommended": DEFAULT_MODEL_RECOMMENDED,
        "deepseek": {"installed": False, "name": None},
        "qwen": {"installed": False, "name": None},
        "errors": [],
    }


def _find_model(names: list[str], prefix: str) -> str | None:
    for n in names:
        low = n.lower()
        if low.startswith(prefix.lower()):
            return n
    return None


def ping_ollama_sync(base_url: str = DEFAULT_BASE_URL, *, timeout_s: float = TIMEOUT_S) -> dict[str, Any]:
    """Ping Ollama and return structured inventory dict (synchronous wrapper).

    Uses httpx in synchronous mode — safe for CLI and one-shot scripts.
    Never raises; all errors are captured in the ``errors`` list.
    """
    result = _empty_result(base_url)
    tags_url = base_url.rstrip("/") + "/api/tags"

    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.get(tags_url)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.ConnectError as exc:
        result["errors"].append(f"ConnectError: {exc}")
        return result
    except httpx.TimeoutException as exc:
        result["errors"].append(f"TimeoutException: {exc}")
        return result
    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")
        return result

    result["reachable"] = True
    models_raw = payload.get("models", []) if isinstance(payload, dict) else []
    models: list[dict[str, Any]] = []
    names: list[str] = []

    for m in models_raw:
        if not isinstance(m, dict):
            continue
        name = str(m.get("name", ""))
        names.append(name)
        details = m.get("details")
        if not isinstance(details, dict):
            details = {}
        models.append(
            {
                "name": name,
                "size": int(m.get("size") or 0),
                "modified_at": str(m.get("modified_at") or ""),
                "digest": str(m.get("digest") or ""),
                "details": {
                    "parent_model": str(details.get("parent_model") or ""),
                    "format": str(details.get("format") or ""),
                    "family": str(details.get("family") or ""),
                    "families": details.get("families") if isinstance(details.get("families"), list) else [],
                    "parameter_size": str(details.get("parameter_size") or ""),
                    "quantization_level": str(details.get("quantization_level") or ""),
                },
            }
        )

    result["models_count"] = len(models)
    result["models"] = models

    deepseek_name = _find_model(names, "deepseek")
    qwen_name = _find_model(names, "qwen")

    result["deepseek"] = {
        "installed": deepseek_name is not None,
        "name": deepseek_name,
    }
    result["qwen"] = {
        "installed": qwen_name is not None,
        "name": qwen_name,
    }
    result["ok"] = bool(deepseek_name or qwen_name)

    return result


def _print_human(result: dict[str, Any]) -> None:
    if not result["reachable"]:
        print(
            "Ollama not reachable on localhost:11434 — install Ollama, "
            "run `ollama serve` in terminal, then "
            f"`ollama pull {DEFAULT_MODEL_RECOMMENDED}` (4.7GB)"
        )
        if result["errors"]:
            for e in result["errors"]:
                print(f"  · {e}", file=sys.stderr)
        return

    print(f"Ollama reachable. {result['models_count']} model(s) installed.")
    if result["qwen"]["installed"]:
        print(f"  ✓ Qwen model: {result['qwen']['name']}")
    else:
        print(f"  ✗ Qwen model NOT installed — recommended: {DEFAULT_MODEL_RECOMMENDED}")
    if result["deepseek"]["installed"]:
        print(f"  ✓ DeepSeek model: {result['deepseek']['name']}")
    else:
        print("  ✗ DeepSeek model NOT installed")

    if not result["ok"]:
        print(
            f"\nRecommended model missing. Pull it with:\n"
            f"  ollama pull {DEFAULT_MODEL_RECOMMENDED}"
        )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="ollama_ping",
        description="Diagnose Ollama reachability and installed code models.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Print only machine-readable JSON to stdout.",
    )
    p.add_argument(
        "--base-url",
        type=str,
        default=DEFAULT_BASE_URL,
        help=f"Ollama base URL (default: {DEFAULT_BASE_URL}).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    result = ping_ollama_sync(args.base_url)

    if getattr(args, "json", False):
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_human(result)

    if not result["reachable"]:
        return 1
    if not result["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
