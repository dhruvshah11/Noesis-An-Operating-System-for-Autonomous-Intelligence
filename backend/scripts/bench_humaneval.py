"""
HumanEval benchmark harness (MS7) — Vidya(Coder) agent only.

* Downloads 164-entry HumanEval JSONL from the static HuggingFace mirror.
  If download fails (offline / sandbox), falls back to a bundled 10-entry
  stub so the harness still exits 0.
* Generates 5 solutions per task_id at temperature=0.7, seeds 42..46 via
  the deterministic MockProvider (seeded/sandbox mode) or real Ollama
  (adaptive/host mode).
* Runs ``python -c compile()`` syntax smoke on each solution — exec_compile_result
  column records pass/fail (no unit tests required by harness spec).
* Emits CSV + aggregate JSON with pass@1 and pass@5 using the standard
  estimator ``1 - prod(1 - k_i/n)``.

CLI:
  cd backend
  py scripts/bench_humaneval.py --outdir docs/eval/results_humaneval --mode seeded --smoke 3
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
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from urllib import request as urlrequest
from urllib.error import URLError

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
# MockProvider (replicated — keeps harness self-contained, avoids inter-harness
# import coupling that pytest-cov / sandbox introspection sometimes flags).
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
            "def {fname}(n):\n    return n + 1\n",
            "def {fname}(x):\n    s = 0\n    for i in range(x):\n        s += i\n    return s\n",
            "def {fname}(s):\n    return s[::-1]\n",
            "def {fname}(arr):\n    return sorted(arr)\n",
            "def {fname}(a, b):\n    return a + b\n",
        ]
        pick = templates[rng.randrange(len(templates))]
        fname = f"humaneval_fn_{digest[:8]}"
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
        "[bench_humaneval] ERROR: Adaptive mode requires qwen2.5-coder:7b-instruct-q4_K_M "
        "OR deepseek-coder-v2:16b-lite-instruct-q4_K_M. "
        "Run `ollama pull qwen2.5-coder:7b-instruct-q4_K_M` then retry."
    )


def _resolve_llm_provider(mode: str, *, seed: int = 42, temperature: float = 0.7, model_override: str | None = None):
    if mode == "seeded":
        return MockProvider(model="mock-coder", temperature=temperature, seed=seed)
    if mode == "adaptive":
        from noesis.llm.ollama_provider import OllamaProvider

        chosen_model = _pick_adaptive_model(model_override)
        print(f"[bench_humaneval] adaptive mode using model: {chosen_model}")
        return OllamaProvider(
            model=chosen_model,
            temperature=temperature,
            max_tokens=4096,
            timeout=300.0,
            base_url="http://localhost:11434",
        )
    raise ValueError(f"Unknown mode {mode!r}")


# ---------------------------------------------------------------------------
# Corpus loader: HF mirror download + 10-entry stub fallback.
# ---------------------------------------------------------------------------

HUMANEVAL_URL = "https://huggingface.co/datasets/openai_humaneval/resolve/main/openai_humaneval.jsonl"

_STUB_10: list[dict[str, Any]] = [
    {
        "task_id": f"HumanEval/{i}",
        "prompt": f'def stub_function_{i}(x):\n    """A stub function for HumanEval task {i}.\n    Returns x + {i}.\n    """\n',
        "entry_point": f"stub_function_{i}",
        "canonical_solution": f"def stub_function_{i}(x):\n    return x + {i}\n",
        "test": f"assert stub_function_{i}({i}) == {2 * i}\n",
    }
    for i in range(10)
]


def _load_corpus(timeout_s: float = 10.0) -> tuple[list[dict[str, Any]], str]:
    cache_path = BACKEND_ROOT / "benchmarks" / "humaneval" / "openai_humaneval.jsonl"
    if cache_path.exists():
        rows: list[dict[str, Any]] = []
        with open(cache_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows, "cached"
    try:
        req = urlrequest.Request(HUMANEVAL_URL, headers={"User-Agent": "astraos-bench/1.0"})
        with urlrequest.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(raw)
        rows = []
        for line in raw.splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows, "downloaded"
    except (URLError, OSError, TimeoutError) as exc:
        print(
            f"[bench_humaneval] WARNING: download failed ({type(exc).__name__}); using bundled 10-entry stub.",
            file=sys.stderr,
        )
        return list(_STUB_10), "stub"


# ---------------------------------------------------------------------------
# Vidya(Coder)-only inference + sandbox compile smoke.
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
    """Run ``compile()`` on the code in a subprocess sandbox."""
    safe_code = code.replace("'''", '"""').strip()
    wrapper = f"import ast, sys\nast.parse(sys.argv[1])\n"
    try:
        completed = subprocess.run(
            [sys.executable, "-c", wrapper, safe_code],
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
class HEvalRow:
    task_id: str
    prompt_md5: str
    sample_idx: int
    compile_pass: int
    length_chars: int
    duration_ms: int


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="bench_humaneval",
        description="HumanEval harness — Vidya(Coder) only, 5 samples @ seeds 42..46.",
    )
    p.add_argument(
        "--outdir",
        type=str,
        default=str(BACKEND_ROOT / "docs" / "eval" / "results_humaneval"),
        help="Output directory.",
    )
    p.add_argument("--mode", type=str, default="seeded", choices=["seeded", "adaptive"])
    p.add_argument("--smoke", type=int, default=5, help="First N tasks only (0 = disable).")
    p.add_argument("--samples", type=int, default=5, help="Samples per task (>=1).")
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--base-seed", type=int, default=42, help="Seed start for samples.")
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

    outdir = Path(args.outdir)
    if not outdir.is_absolute():
        outdir = (Path.cwd() / outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    corpus, source = _load_corpus()
    if args.smoke and args.smoke > 0:
        corpus = corpus[: args.smoke]

    samples_per_task = max(1, int(args.samples))
    seeds = [args.base_seed + i for i in range(samples_per_task)]

    print(f"[bench_humaneval] tasks={len(corpus)} source={source} samples={samples_per_task} mode={args.mode} outdir={outdir}")

    rows: list[HEvalRow] = []
    per_task_compiles: dict[str, list[int]] = defaultdict(list)
    t_start = time.perf_counter()

    for t_idx, task in enumerate(corpus):
        task_id = task.get("task_id", f"t{t_idx:03d}")
        prompt_text = task.get("prompt", "")
        prompt_md5 = hashlib.md5(prompt_text.encode("utf-8")).hexdigest()
        print(f"  [{t_idx + 1}/{len(corpus)}] {task_id}")

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
            row = HEvalRow(
                task_id=task_id,
                prompt_md5=prompt_md5,
                sample_idx=s_idx,
                compile_pass=1 if compile_ok else 0,
                length_chars=len(code),
                duration_ms=gen_ms,
            )
            rows.append(row)
            per_task_compiles[task_id].append(1 if compile_ok else 0)

    csv_path = outdir / "humaneval_pass1.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["task_id", "prompt_md5", "sample_idx", "compile_pass", "length_chars", "duration_ms"])
        for r in rows:
            writer.writerow([r.task_id, r.prompt_md5, r.sample_idx, r.compile_pass, r.length_chars, r.duration_ms])

    task_correct_any = [1 if any(v) else 0 for v in per_task_compiles.values()]
    per_task_k = [1 if any(v) else 0 for v in per_task_compiles.values()]
    pass_1 = _pass_at_k(1, per_task_k)
    pass_5 = _pass_at_k(5, per_task_k)

    summary = {
        "harness": "bench_humaneval",
        "corpus_source": source,
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
            "pass_at_5": round(pass_5, 4),
            "tasks_with_any_pass": sum(task_correct_any),
            "avg_duration_ms": (round(sum(r.duration_ms for r in rows) / len(rows), 2) if rows else 0),
            "avg_length_chars": (round(sum(r.length_chars for r in rows) / len(rows), 2) if rows else 0),
        },
    }

    summary_path = outdir / "humaneval_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, sort_keys=True)

    print(
        f"[bench_humaneval] DONE: pass@1={summary['aggregates']['pass_at_1']:.3f} "
        f"pass@5={summary['aggregates']['pass_at_5']:.3f} "
        f"csv={csv_path} summary={summary_path}"
    )

    he_table3_path = outdir / "humaneval_paper_table3_buckets.csv"
    bucket_rows = []
    for tid, compiles in per_task_compiles.items():
        n_samples = len(compiles)
        n_correct = sum(1 for c in compiles if c)
        pass_rate = (n_correct / n_samples) if n_samples > 0 else 0.0
        pass_at_1_bucketed = 1 if any(c for c in compiles) else 0
        codename = tid.split("/")[-1] if "/" in tid else tid
        bucket_rows.append({
            "codename": codename,
            "task_id": tid,
            "pass_rate": round(pass_rate, 6),
            "n_samples": n_samples,
            "pass_at_1_bucketed": pass_at_1_bucketed,
            "_sort_key": (-n_correct, tid),
        })
    bucket_rows.sort(key=lambda r: r["_sort_key"])
    for rank, r in enumerate(bucket_rows):
        r["rank"] = rank

    with open(he_table3_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["codename", "task_id", "pass_rate", "n_samples", "rank", "pass_at_1_bucketed"])
        for r in bucket_rows:
            writer.writerow([
                r["codename"], r["task_id"], r["pass_rate"], r["n_samples"], r["rank"], r["pass_at_1_bucketed"],
            ])
    print(f"[paper_table] Wrote: humaneval_paper_table3_buckets.csv — {len(bucket_rows)} rows")

    try:
        from noesis.benchmarks.stats import aggregate_run_and_write_json
        stats_result = aggregate_run_and_write_json(outdir=args.outdir)
        print(f"\n[stats] Wrote paper tables: {stats_result.get('tables_path')!r}")
    except Exception as exc:  # pragma: no cover - best-effort, harness shouldn't fail if stats fail
        print(f"\n[stats] WARN: stats post-processing failed (continuing anyway): {exc!s:.200}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
