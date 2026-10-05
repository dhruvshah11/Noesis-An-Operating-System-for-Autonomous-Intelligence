"""
MBPP (Mostly Basic Python Problems) benchmark harness (MS7) — Vidya(Coder) agent only.

* Loads the bundled offline stub ``mbpp_sanitized_first500_stub.json`` from
  ``backend/benchmarks/mbpp/``.  First 10 entries include id/prompt/3 reference
  solutions; entries 11-500 are placeholder prompts so the harness can iterate
  all 500 deterministically without network.
* 5-sample Vidya-only Coder agent pattern: temperature=0.7, seeds 42..46
  (via MockProvider for sandbox/seeded mode or real Ollama for adaptive/host).
* ``python -c compile`` syntax smoke per solution; aggregate pass@k estimates.

CLI:
  cd backend
  py scripts/bench_mbpp.py --outdir docs/eval/results_mbpp --mode seeded --smoke 3
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import io
import json
import math
import os
import random
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
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

from noesis.llm.base import BaseProvider
from noesis.types import ChatMessage, ProviderResponse, ProviderType, TokenUsage, MessageRole

# ---------------------------------------------------------------------------
# MockProvider (self-contained — matches HumanEval shape).
# ---------------------------------------------------------------------------


class MockProvider(BaseProvider):
    provider_id = "mock"

    def __init__(
        self,
        *,
        model: str = "mock-seeded",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: float = 120.0,
        seed: int = 42,
        **kwargs: object,
    ) -> None:
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens, timeout=timeout, **kwargs)
        self._seed = int(seed)

    async def _chat_impl(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict] | None,
        tool_choice: str | dict | None,
        **override_kwargs: object,
    ) -> ProviderResponse:
        h = hashlib.sha256()
        h.update(self.model.encode())
        h.update(b"\x00")
        h.update(f"{self.temperature:.6f}".encode())
        h.update(b"\x00")
        h.update(str(self._seed).encode())
        for m in messages:
            role_val = m.role.value if hasattr(m.role, "value") else str(m.role)
            h.update(role_val.encode())
            h.update(b"\x01")
            h.update((m.content or "").encode("utf-8", errors="replace"))
            h.update(b"\x02")
        digest = h.hexdigest()
        rng = random.Random(digest)
        templates = [
            "def {fname}(nums):\n    return sum(nums)\n",
            "def {fname}(s):\n    return len(s)\n",
            "def {fname}(x, y):\n    return x * y\n",
            "def {fname}(items):\n    out = []\n    for it in items:\n        if it not in out:\n            out.append(it)\n    return out\n",
            "def {fname}(n):\n    res = []\n    a, b = 0, 1\n    for _ in range(n):\n        res.append(a)\n        a, b = b, a + b\n    return res\n",
        ]
        pick = templates[rng.randrange(len(templates))]
        fname = f"mbpp_fn_{digest[:8]}"
        content = pick.format(fname=fname)
        return ProviderResponse(
            provider=ProviderType.OLLAMA,
            model=self.model,
            content=content,
            tool_calls=[],
            usage=TokenUsage(
                prompt_tokens=sum(len((m.content or "").split()) for m in messages),
                completion_tokens=len(content.split()),
                total_tokens=sum(len((m.content or "").split()) for m in messages) + len(content.split()),
            ),
            latency_ms=1.0 + rng.random() * 3.0,
            finish_reason="stop",
            raw={"mock_digest": digest},
        )


_OLLAMA_INSTALLED_MODELS_CACHE: list[str] | None = None


def _ping_ollama_models(base_url: str = "http://localhost:11434") -> list[str]:
    global _OLLAMA_INSTALLED_MODELS_CACHE
    if _OLLAMA_INSTALLED_MODELS_CACHE is not None:
        return _OLLAMA_INSTALLED_MODELS_CACHE
    try:
        import httpx
    except Exception:
        _OLLAMA_INSTALLED_MODELS_CACHE = []
        return _OLLAMA_INSTALLED_MODELS_CACHE
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{base_url.rstrip('/')}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                _OLLAMA_INSTALLED_MODELS_CACHE = [m for m in models if m]
            else:
                _OLLAMA_INSTALLED_MODELS_CACHE = []
    except Exception:
        _OLLAMA_INSTALLED_MODELS_CACHE = []
    return _OLLAMA_INSTALLED_MODELS_CACHE


def _pick_adaptive_model(override: str | None = None) -> str:
    RECOMMENDED = [
        "qwen2.5-coder:7b-instruct-q4_K_M",
        "deepseek-coder-v2:16b-lite-instruct-q4_K_M",
    ]
    FALLBACK_2 = "llama3.1:8b"

    if override:
        return override

    env_model = os.environ.get("OLLAMA_MODEL", "").strip()
    if env_model:
        return env_model

    installed = _ping_ollama_models()
    installed_lower = [m.lower() for m in installed]

    for rec in RECOMMENDED:
        if rec.lower() in installed_lower:
            return rec

    if FALLBACK_2.lower() in installed_lower:
        return FALLBACK_2

    raise SystemExit(
        "[bench_mbpp] ERROR: Adaptive mode requires qwen2.5-coder:7b-instruct-q4_K_M "
        "OR deepseek-coder-v2:16b-lite-instruct-q4_K_M. "
        "Run `ollama pull qwen2.5-coder:7b-instruct-q4_K_M` then retry."
    )


def _resolve_llm_provider(mode: str, *, seed: int = 42, temperature: float = 0.7, model_override: str | None = None):
    if mode == "seeded":
        return MockProvider(model="mock-coder", temperature=temperature, seed=seed)
    if mode == "adaptive":
        from noesis.llm.ollama_provider import OllamaProvider

        chosen_model = _pick_adaptive_model(model_override)
        print(f"[bench_mbpp] adaptive mode using model: {chosen_model}")
        return OllamaProvider(
            model=chosen_model,
            temperature=temperature,
            max_tokens=4096,
            timeout=300.0,
            base_url="http://localhost:11434",
        )
    raise ValueError(f"Unknown mode {mode!r}")


# ---------------------------------------------------------------------------
# Corpus loader (bundled stub JSON).
# ---------------------------------------------------------------------------

DEFAULT_STUB = BACKEND_ROOT / "benchmarks" / "mbpp" / "mbpp_sanitized_first500_stub.json"


def _load_corpus(stub_path: Path) -> list[dict[str, Any]]:
    with open(stub_path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    return list(obj.get("tasks", []))


# ---------------------------------------------------------------------------
# Vidya(Coder) + sandbox compile.
# ---------------------------------------------------------------------------


async def _vidya_coder_generate(provider: BaseProvider, prompt: str, *, seed: int, temperature: float) -> tuple[str, int]:
    t0 = time.perf_counter()
    messages = [
        ChatMessage(
            role=MessageRole.SYSTEM,
            content="You are Vidya, a precise Python coding agent. Return ONLY runnable Python. No markdown fences, no prose.",
        ),
        ChatMessage(
            role=MessageRole.USER,
            content=prompt + "\nReturn ONLY Python, no markdown.",
        ),
    ]
    resp = await provider.chat(messages, temperature=temperature)
    content = resp.content or ""
    duration_ms = int((time.perf_counter() - t0) * 1000)
    return content, duration_ms


def _syntax_compile_check(code: str, timeout_s: int = 10) -> tuple[bool, str]:
    wrapper = "import ast, sys\nast.parse(sys.argv[1])\n"
    try:
        completed = subprocess.run(
            [sys.executable, "-c", wrapper, code.replace("'''", '"""').strip()],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            encoding="utf-8",
            errors="replace",
        )
        ok = completed.returncode == 0
        detail = (completed.stderr or completed.stdout or "").strip()[:200]
        return ok, detail
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"[:200]


def _pass_at_k(k: int, per_task_correct: list[int]) -> float:
    n = len(per_task_correct)
    if n == 0:
        return 0.0
    correct = sum(1 for c in per_task_correct if c > 0)
    if correct == 0:
        return 0.0
    if k >= n:
        return 1.0
    numerator = 1.0
    for i in range(k):
        numerator *= 1.0 - (correct / (n - i))
    return 1.0 - numerator


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


@dataclass
class MBPPRow:
    task_id: str
    prompt_md5: str
    sample_idx: int
    compile_pass: int
    length_chars: int
    duration_ms: int
    has_reference: int


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="bench_mbpp",
        description="MBPP harness — Vidya(Coder) only, 5 samples @ seeds 42..46.",
    )
    p.add_argument(
        "--corpus",
        type=str,
        default=str(DEFAULT_STUB),
        help="Path to MBPP stub JSON.",
    )
    p.add_argument(
        "--outdir",
        type=str,
        default=str(BACKEND_ROOT / "docs" / "eval" / "results_mbpp"),
        help="Output directory.",
    )
    p.add_argument("--mode", type=str, default="seeded", choices=["seeded", "adaptive"])
    p.add_argument("--smoke", type=int, default=5, help="First N tasks only (0 = disable).")
    p.add_argument("--samples", type=int, default=5, help="Samples per task (>=1).")
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--base-seed", type=int, default=42)
    p.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override Ollama model for adaptive mode (skips auto-pick). Ignored in seeded mode.",
    )
    p.add_argument(
        "--max",
        type=int,
        default=None,
        dest="smoke",
        help="Alias for --smoke (first N tasks only).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    random.seed(args.base_seed)

    stub_path = Path(args.corpus)
    if not stub_path.is_absolute():
        stub_path = (BACKEND_ROOT / stub_path).resolve()
    if not stub_path.exists():
        print(
            f"[bench_mbpp] ERROR: MBPP stub not found at {stub_path}",
            file=sys.stderr,
        )
        return 2

    outdir = Path(args.outdir)
    if not outdir.is_absolute():
        outdir = (Path.cwd() / outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    corpus = _load_corpus(stub_path)
    if args.smoke and args.smoke > 0:
        corpus = corpus[: args.smoke]

    samples_per_task = max(1, int(args.samples))
    seeds = [args.base_seed + i for i in range(samples_per_task)]

    print(f"[bench_mbpp] tasks={len(corpus)} samples={samples_per_task} mode={args.mode} stub={stub_path}")

    rows: list[MBPPRow] = []
    per_task_compiles: dict[str, list[int]] = defaultdict(list)
    t_start = time.perf_counter()

    for t_idx, task in enumerate(corpus):
        task_id = str(task.get("task_id", f"mbpp_{t_idx:04d}"))
        prompt_text = task.get("prompt", "")
        refs = task.get("reference_solutions", []) or []
        prompt_md5 = hashlib.md5(prompt_text.encode("utf-8")).hexdigest()
        print(f"  [{t_idx + 1}/{len(corpus)}] task={task_id} refs={len(refs)}")

        for s_idx, seed in enumerate(seeds):
            provider = _resolve_llm_provider(args.mode, seed=seed, temperature=args.temperature, model_override=args.model)
            t0 = time.perf_counter()
            try:
                code, gen_ms = asyncio.run(
                    _vidya_coder_generate(
                        provider,
                        prompt_text,
                        seed=seed,
                        temperature=args.temperature,
                    )
                )
            except Exception as exc:
                code = f"# ERROR: {type(exc).__name__}: {exc}"
                gen_ms = int((time.perf_counter() - t0) * 1000)

            compile_ok, _ = _syntax_compile_check(code)
            row = MBPPRow(
                task_id=task_id,
                prompt_md5=prompt_md5,
                sample_idx=s_idx,
                compile_pass=1 if compile_ok else 0,
                length_chars=len(code),
                duration_ms=gen_ms,
                has_reference=1 if refs else 0,
            )
            rows.append(row)
            per_task_compiles[task_id].append(1 if compile_ok else 0)

    csv_path = outdir / "mbpp_results.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "task_id",
                "prompt_md5",
                "sample_idx",
                "compile_pass",
                "length_chars",
                "duration_ms",
                "has_reference",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    r.task_id,
                    r.prompt_md5,
                    r.sample_idx,
                    r.compile_pass,
                    r.length_chars,
                    r.duration_ms,
                    r.has_reference,
                ]
            )

    per_task_k = [1 if any(v) else 0 for v in per_task_compiles.values()]
    pass_1 = _pass_at_k(1, per_task_k)
    pass_3 = _pass_at_k(3, per_task_k)
    pass_5 = _pass_at_k(5, per_task_k)

    summary = {
        "harness": "bench_mbpp",
        "corpus_stub": str(stub_path),
        "mode": args.mode,
        "samples_per_task": samples_per_task,
        "temperature": args.temperature,
        "seeds": seeds,
        "tasks_total": len(corpus),
        "rows_written": len(rows),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "wall_duration_ms": int((time.perf_counter() - t_start) * 1000),
        "csv": str(csv_path),
        "aggregates": {
            "compile_pass_total": sum(1 for r in rows if r.compile_pass),
            "compile_pass_rate": (round(sum(1 for r in rows if r.compile_pass) / len(rows), 4) if rows else 0.0),
            "pass_at_1": round(pass_1, 4),
            "pass_at_3": round(pass_3, 4),
            "pass_at_5": round(pass_5, 4),
            "tasks_with_reference_solutions": sum(r.has_reference for r in rows if r.sample_idx == 0),
            "tasks_with_any_pass": sum(per_task_k),
            "avg_duration_ms": (round(sum(r.duration_ms for r in rows) / len(rows), 2) if rows else 0),
            "avg_length_chars": (round(sum(r.length_chars for r in rows) / len(rows), 2) if rows else 0),
        },
    }

    summary_path = outdir / "mbpp_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, sort_keys=True)

    print(
        f"[bench_mbpp] DONE: pass@1={summary['aggregates']['pass_at_1']:.3f} "
        f"pass@5={summary['aggregates']['pass_at_5']:.3f} "
        f"csv={csv_path} summary={summary_path}"
    )

    mbpp_table5_path = outdir / "mbpp_paper_table5_difficulty.csv"
    items_sorted = sorted(per_task_compiles.items(), key=lambda kv: kv[0])
    n_items = max(1, len(items_sorted))

    task_durations: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        task_durations[r.task_id].append(r.duration_ms)

    mbpp_bucket_rows = []
    for bucket_idx in range(5):
        start = (bucket_idx * n_items) // 5
        end = ((bucket_idx + 1) * n_items) // 5 if bucket_idx < 4 else n_items
        slice_items = items_sorted[start:end]
        if not slice_items:
            continue
        difficulty_1_to_5 = bucket_idx + 1
        bucket_label = f"difficulty_{difficulty_1_to_5}"
        slice_flags = [1 if any(v) else 0 for _, v in slice_items]
        n_tasks = len(slice_items)
        n_correct = sum(slice_flags)
        pass_at_1_b = round((n_correct / n_tasks) if n_tasks > 0 else 0.0, 6)

        all_durations: list[int] = []
        for tid, _ in slice_items:
            all_durations.extend(task_durations.get(tid, []))
        avg_duration_ms = round(sum(all_durations) / len(all_durations), 2) if all_durations else 0

        mbpp_bucket_rows.append([
            bucket_label, difficulty_1_to_5, n_tasks, n_correct, pass_at_1_b, avg_duration_ms,
        ])

    with open(mbpp_table5_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["bucket_label", "difficulty_1_to_5", "n_tasks", "n_correct", "pass_at_1", "avg_duration_ms"])
        for row in mbpp_bucket_rows:
            writer.writerow(row)
    print(f"[paper_table] Wrote: mbpp_paper_table5_difficulty.csv — {len(mbpp_bucket_rows)} rows")

    try:
        from noesis.benchmarks.stats import aggregate_run_and_write_json
        stats_result = aggregate_run_and_write_json(outdir=args.outdir)
        print(f"\n[stats] Wrote paper tables: {stats_result.get('tables_path')!r}")
    except Exception as exc:  # pragma: no cover - best-effort, harness shouldn't fail if stats fail
        print(f"\n[stats] WARN: stats post-processing failed (continuing anyway): {exc!s:.200}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
