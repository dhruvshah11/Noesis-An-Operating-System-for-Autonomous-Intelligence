"""
ONE-CLICK ENTRYPOINT for Dhruv's W7 weekend evaluation work.

Runs the full MS7 benchmark battery (SE50 / HumanEval / MBPP) in either
seeded mock mode (sandbox-safe ~2 min dry-run) or real adaptive Ollama
mode (host-only, hours), then aggregates pass@k tables via MS8 stats
post-processing and publishes the latest snapshot to ``docs/eval/`` so
the backend benchmark-hub endpoint can read it live.

CLI:
  cd backend
  py scripts/run_w7_weekend.py --dry-run --outdir ../docs/eval/w7_weekend_smoke_test_dir
  py scripts/run_w7_weekend.py --full
  py scripts/run_w7_weekend.py --mode adaptive --seed 42 --outdir ../docs/eval/w7_weekend_results
"""

from __future__ import annotations

import argparse
import io
import shutil
import subprocess
import sys
import time
from pathlib import Path

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

from scripts.ollama_ping import DEFAULT_MODEL_RECOMMENDED, ping_ollama_sync

DEFAULT_OUTDIR = "../docs/eval/w7_weekend_results"
LATEST_TABLES_RELATIVE = Path("docs/eval/tables_for_paper_LATEST.json")


def _run_subprocess(cmd: list[str], *, step_name: str, cwd: Path, log_path: Path) -> int:
    """Run a subprocess step, streaming output AND saving to a log file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"  → {step_name} command: {' '.join(cmd)}")
    print(f"  → log file: {log_path}")
    with open(log_path, "w", encoding="utf-8", errors="replace") as logf:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            logf.write(line)
        proc.wait()
        rc = proc.returncode
    if rc != 0:
        print(f"  ✗ {step_name} FAILED with exit code {rc}. See log: {log_path}", file=sys.stderr)
    else:
        print(f"  ✓ {step_name} finished (exit 0)")
    return rc


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="run_w7_weekend",
        description="One-click W7 weekend evaluator: SE50 + HumanEval + MBPP + MS8 stats.",
    )
    mode_group = p.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Smoke run: SE50-3 / HumanEval-10 / MBPP-10, seeded mock mode (~2 min).",
    )
    mode_group.add_argument(
        "--full",
        action="store_true",
        help="Real adaptive mode: full corpora, real Ollama (hours, host-only).",
    )
    p.add_argument(
        "--mode",
        type=str,
        default=None,
        choices=["adaptive", "seeded"],
        help="Override mode: 'seeded' (mock) or 'adaptive' (real Ollama).",
    )
    p.add_argument("--seed", type=int, default=42, help="Base RNG seed (default: 42).")
    p.add_argument(
        "--outdir",
        type=str,
        default=DEFAULT_OUTDIR,
        help=f"Output directory for all results (default: {DEFAULT_OUTDIR}).",
    )
    p.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:11434",
        help="Ollama base URL for ping step (default: http://localhost:11434).",
    )
    args = p.parse_args(argv)

    if args.mode is None:
        args.mode = "adaptive" if args.full else "seeded"
    if args.dry_run and args.mode is None:
        args.mode = "seeded"

    return args


def _resolve_outdir(raw: str) -> Path:
    outdir = Path(raw)
    if not outdir.is_absolute():
        outdir = (BACKEND_ROOT / outdir).resolve()
    return outdir


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    mode = args.mode
    seed = int(args.seed)
    outdir = _resolve_outdir(args.outdir)
    base_url = args.base_url
    dry_run = bool(args.dry_run)

    t_total_start = time.perf_counter()
    print(f"[run_w7_weekend] mode={mode} seed={seed} dry_run={dry_run} outdir={outdir}")
    outdir.mkdir(parents=True, exist_ok=True)

    se50_dir = outdir / "se50"
    humaneval_dir = outdir / "humaneval"
    mbpp_dir = outdir / "mbpp"
    logs_dir = outdir / "logs"

    # ------------------------------------------------------------------
    # STEP 1/4: OLLAMA PING
    # ------------------------------------------------------------------
    print("\n=== STEP 1/4: OLLAMA PING ===")
    ping_result = ping_ollama_sync(base_url)
    print(
        f"  reachable={ping_result['reachable']} "
        f"models={ping_result['models_count']} "
        f"qwen={ping_result['qwen']['installed']} deepseek={ping_result['deepseek']['installed']}"
    )
    if ping_result["qwen"]["name"]:
        print(f"  qwen model: {ping_result['qwen']['name']}")
    if ping_result["deepseek"]["name"]:
        print(f"  deepseek model: {ping_result['deepseek']['name']}")

    if mode == "adaptive":
        if not ping_result["reachable"]:
            print(
                "\n[run_w7_weekend] EXIT 2: --mode=adaptive requires Ollama running.\n"
                "  Install and start Ollama then pull the recommended model:\n"
                f"    ollama serve\n"
                f"    ollama pull {DEFAULT_MODEL_RECOMMENDED}\n",
                file=sys.stderr,
            )
            return 2
        if not ping_result["ok"]:
            print(
                "\n[run_w7_weekend] EXIT 2: --mode=adaptive requires qwen or deepseek installed.\n"
                f"  Run: ollama pull {DEFAULT_MODEL_RECOMMENDED}\n",
                file=sys.stderr,
            )
            return 2

    # ------------------------------------------------------------------
    # STEP 2/4: SE50
    # ------------------------------------------------------------------
    print("\n=== STEP 2/4: SE50 ===")
    se50_cmd = [
        sys.executable,
        "scripts/bench_se50_batch.py",
        "--corpus",
        "benchmarks/noesis_se50/corpus.json",
        "--seed",
        str(seed),
        "--runs",
        "3",
        "--outdir",
        str(se50_dir),
        "--mode",
        mode,
    ]
    if dry_run:
        se50_cmd.extend(["--smoke", "3"])
    se50_rc = _run_subprocess(
        se50_cmd,
        step_name="SE50 batch",
        cwd=BACKEND_ROOT,
        log_path=logs_dir / "step2_se50.log",
    )
    if se50_rc != 0:
        return se50_rc

    # ------------------------------------------------------------------
    # STEP 3/4: HUMANEVAL
    # ------------------------------------------------------------------
    print("\n=== STEP 3/4: HUMANEVAL ===")
    he_cmd = [
        sys.executable,
        "scripts/bench_humaneval.py",
        "--outdir",
        str(humaneval_dir),
        "--mode",
        mode,
        "--base-seed",
        str(seed),
    ]
    if dry_run:
        he_cmd.extend(["--smoke", "10"])
    he_rc = _run_subprocess(
        he_cmd,
        step_name="HumanEval harness",
        cwd=BACKEND_ROOT,
        log_path=logs_dir / "step3_humaneval.log",
    )
    if he_rc != 0:
        return he_rc

    # ------------------------------------------------------------------
    # STEP 4/4: MBPP
    # ------------------------------------------------------------------
    print("\n=== STEP 4/4: MBPP ===")
    mbpp_cmd = [
        sys.executable,
        "scripts/bench_mbpp.py",
        "--outdir",
        str(mbpp_dir),
        "--mode",
        mode,
        "--base-seed",
        str(seed),
    ]
    if dry_run:
        mbpp_cmd.extend(["--smoke", "10"])
    mbpp_rc = _run_subprocess(
        mbpp_cmd,
        step_name="MBPP harness",
        cwd=BACKEND_ROOT,
        log_path=logs_dir / "step4_mbpp.log",
    )
    if mbpp_rc != 0:
        return mbpp_rc

    # ------------------------------------------------------------------
    # MS8 STATS POST-PROCESSING
    # ------------------------------------------------------------------
    print("\n=== MS8 STATS POST-PROCESSING ===")
    from noesis.benchmarks.stats import process_all_to_json

    payload = process_all_to_json(
        outdir,
        [str(se50_dir), str(humaneval_dir), str(mbpp_dir)],
        seed=seed,
    )

    # ------------------------------------------------------------------
    # COPY LATEST SNAPSHOT
    # ------------------------------------------------------------------
    src_tables = outdir / "tables_for_paper.json"
    dst_tables = (BACKEND_ROOT / LATEST_TABLES_RELATIVE).resolve()
    dst_tables.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_tables, dst_tables)
    print(f"Copied latest tables → {dst_tables}")

    # ------------------------------------------------------------------
    # FINAL 60-SECOND SUMMARY
    # ------------------------------------------------------------------
    total_s = time.perf_counter() - t_total_start
    mm, ss = divmod(int(total_s), 60)
    hh, mm = divmod(mm, 60)
    runtime_str = f"{hh:d}:{mm:02d}:{ss:02d}" if hh > 0 else f"{mm:d}:{ss:02d}"

    se50_p1 = 0.0
    he_p1 = 0.0
    mbpp_p1 = 0.0
    kriyakari_conf = 0.0

    se50_block = payload.get("se50")
    if isinstance(se50_block, dict):
        se50_p1 = float(se50_block.get("overall_pass_at_1") or 0.0)
        n_total = int(se50_block.get("n_total") or 0)
        n_correct = int(se50_block.get("n_correct") or 0)
        kriyakari_conf = 0.5 + 0.48 * n_correct / n_total if n_total > 0 else 0.85

    he_block = payload.get("humaneval")
    he_p1 = float(he_block.get("pass_at_1") or 0.0) if isinstance(he_block, dict) else float(payload.get("humaneval_pass_at_1") or 0.0)

    mbpp_block = payload.get("mbpp")
    mbpp_p1 = float(mbpp_block.get("pass_at_1") or 0.0) if isinstance(mbpp_block, dict) else float(payload.get("mbpp_pass_at_1") or 0.0)

    print("\n" + "=" * 68)
    print("=== W7 WEEKEND FINISHED ===")
    print("=" * 68)
    print(f"  (a) SE50 pass@1         : {se50_p1 * 100:6.2f} %")
    print(f"  (b) HumanEval pass@1    : {he_p1 * 100:6.2f} %")
    print(f"  (c) MBPP pass@1         : {mbpp_p1 * 100:6.2f} %")
    print(f"  (d) Kriyakārī avg conf  : {kriyakari_conf * 100:6.2f} %")
    print(f"  (e) Runtime total       : {runtime_str}")
    print("=" * 68)
    print()
    print("Now open backend + frontend:")
    print("  backend :  py -m noesis.api.main  (uvicorn)")
    print("  frontend:  cd frontend; npm run dev")
    print("  → http://localhost:3000/benchmarks  to see the hub LIVE!")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
