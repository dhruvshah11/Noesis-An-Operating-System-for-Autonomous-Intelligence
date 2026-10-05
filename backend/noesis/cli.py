"""
Noesis command-line interface (CLI).

Entry point: ``noesis`` (exposed via ``pyproject.toml`` console_scripts).
Run ``noesis --help`` to see all commands.
"""

from __future__ import annotations

import contextlib
import importlib.metadata
import platform
import sys
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from typer import Exit, Option, Typer

# Console singleton used by every command for consistent styling / --no-color.
console = Console()
app = Typer(
    name="noesis",
    help="Noesis — autonomic multi-agent operating system for research, coding & planning.",
    no_args_is_help=True,
    add_completion=True,
    rich_markup_mode="rich",
)

__all__ = ["app", "main"]


def _detect_version() -> str:
    """Fall back to '0.1.0-dev' if the distribution is not installed (pip -e handles both fine)."""
    try:
        return importlib.metadata.version("noesis")
    except importlib.metadata.PackageNotFoundError:
        return "0.1.0-dev"


VERSION = _detect_version()


# ---------------------------------------------------------------------------
# --- Top-level options
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: bool = Option(False, "--version", "-V", help="Print Noesis version and exit."),
    quiet: bool = Option(False, "--quiet", "-q", help="Suppress non-essential output."),
) -> None:
    if version:
        console.print(f"noesis {VERSION}")
        raise Exit(0)
    global _QUIET
    _QUIET = quiet
    # Replicate original no_args_is_help behaviour: when no subcommand supplied, show help.
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise Exit(0)


_QUIET: bool = False


def _echo(message: str, *, style: str | None = None) -> None:
    if not _QUIET:
        console.print(message, style=style)


# ---------------------------------------------------------------------------
# --- serve
# ---------------------------------------------------------------------------


@app.command()
def serve(
    host: str = Option("127.0.0.1", "--host", "-h", help="Bind address for the HTTP server."),
    port: int = Option(8000, "--port", "-p", min=1, max=65535, help="Bind TCP port."),
    workers: int = Option(1, "--workers", "-w", min=1, max=32, help="Number of uvicorn worker processes."),
    reload: bool = Option(False, "--reload", help="Enable hot reload (dev only)."),
    access_log: bool = Option(True, "--access-log/--no-access-log", help="Emit HTTP access logs."),
) -> None:
    """Start the FastAPI backend server."""
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - missing dep user message
        console.print(f"[bold red]uvicorn is required to serve the API: {exc}[/bold red]")
        console.print("Install dev dependencies:  [cyan]pip install noesis[dev][/cyan]")
        raise Exit(2) from exc

    _echo(
        Panel.fit(
            f"[bold green]Noesis {VERSION}[/bold green]\n"
            f"[dim]workers=[/dim]{workers}  "
            f"[dim]reload=[/dim]{reload}  "
            f"[dim]access_log=[/dim]{access_log}",
            title="Starting API server",
            border_style="cyan",
        )
    )
    uvicorn.run(
        "noesis.api.main:app",
        host=host,
        port=port,
        workers=workers,
        reload=reload,
        access_log=access_log,
        log_level="info",
    )


# ---------------------------------------------------------------------------
# --- doctor
# ---------------------------------------------------------------------------


def _check(name: str, ok: bool, detail: str = "") -> tuple[str, str, str]:
    status = "[bold green]✓[/bold green]" if ok else "[bold red]✗[/bold red]"
    return status, name, detail


@app.command()
def doctor(
    show_secrets: bool = Option(
        False,
        "--show-secrets",
        help="[yellow]DO NOT commit logs with this on[/yellow] — prints env var contents.",
    ),
) -> None:
    """Run a diagnostic report — env, config, provider credentials, DB connectivity."""
    from noesis.config import get_settings
    from noesis.logging import configure_logging

    configure_logging()

    started = time.perf_counter()
    table = Table(title="Noesis Doctor Report", show_lines=True, header_style="bold cyan")
    table.add_column("Status", justify="center", no_wrap=True)
    table.add_column("Check", style="bold")
    table.add_column("Detail", overflow="fold")

    table.add_row(*_check("Python version", sys.version_info >= (3, 11), f"{sys.version.split()[0]} ({platform.python_implementation()})"))
    table.add_row(*_check("Platform / OS", True, f"{platform.system()} {platform.release()} {platform.machine()}"))
    table.add_row(*_check("Noesis version", True, VERSION))

    settings = get_settings()
    table.add_row(*_check("APP_ENV", settings.app_env in {"local", "test", "staging", "production"}, settings.app_env))
    table.add_row(*_check("DEBUG policy", not settings.debug or settings.app_env in {"local", "test"}, f"{settings.debug} (allowed local/test only)"))

    table.add_row(
        *_check(
            "Database URL",
            bool(settings.database_url),
            (settings.database_url if show_secrets else ("<set>" if settings.database_url else "<missing>")),
        )
    )
    table.add_row(
        *_check("CORS origins count", len(settings.cors_origins) > 0 or settings.app_env == "test", f"{len(settings.cors_origins)} origin(s)")
    )

    # --- Provider credentials (secret-safe by default)
    providers: list[tuple[str, object]] = [
        ("OPENAI_API_KEY", settings.openai_api_key),
        ("ANTHROPIC_API_KEY", settings.anthropic_api_key),
        ("GOOGLE_API_KEY", settings.google_api_key),
        ("OPENROUTER_API_KEY", settings.openrouter_api_key),
    ]
    for env_var, secret in providers:
        val_secret = bool(secret and secret.get_secret_value())
        table.add_row(
            *_check(env_var, val_secret, secret.get_secret_value() if show_secrets and val_secret else ("<set>" if val_secret else "<missing>"))
        )

    table.add_row(
        *_check(
            "Vector store (Qdrant URL)",
            bool(settings.qdrant_url),
            settings.qdrant_url,
        )
    )
    table.add_row(*_check("Redis URL", bool(settings.redis_url), settings.redis_url))

    # --- Import checks
    imports_ok = True
    missing: list[str] = []
    for mod_name in ("fastapi", "sqlalchemy", "pydantic", "tenacity", "structlog", "httpx", "alembic", "typer"):
        try:
            importlib.import_module(mod_name)
        except ImportError:
            imports_ok = False
            missing.append(mod_name)
    table.add_row(*_check("Core deps installed", imports_ok, "all OK" if imports_ok else f"missing: {', '.join(missing)}"))

    # --- DB connectivity (best-effort async)
    db_ok, db_detail = False, "unknown"
    try:
        import asyncio

        from noesis.database.sql import sql_engine

        async def _ping() -> None:
            engine = sql_engine()
            async with engine.begin() as conn:
                await conn.exec_driver_sql("SELECT 1")

        asyncio.run(_ping())
        db_ok, db_detail = True, "SELECT 1 OK"
    except Exception as exc:
        db_ok = False
        db_detail = f"error: {exc!s:.200}"
    table.add_row(*_check("Database connectivity", db_ok, db_detail))

    table.add_row(
        *_check(
            "Default LLM provider",
            bool(settings.default_provider),
            f"{settings.default_provider} / {settings.default_model} (T={settings.temperature})",
        )
    )

    took_ms = (time.perf_counter() - started) * 1000
    console.print(table)
    console.print(f"[dim]doctor run completed in {took_ms:.0f}ms[/dim]")

    if db_ok and imports_ok:
        console.print("[bold green]System is healthy.[/bold green]")
        raise Exit(0)
    console.print("[bold red]Some checks failed — review the report above.[/bold red]")
    raise Exit(1)


# ---------------------------------------------------------------------------
# --- shell (interactive REPL against the LLM factory)
# ---------------------------------------------------------------------------


@app.command()
def shell(
    provider: str | None = Option(None, "--provider", help="Override DEFAULT_PROVIDER for this session."),
    model: str | None = Option(None, "--model", "-m", help="Override DEFAULT_MODEL for this session."),
    temperature: float | None = Option(None, min=0.0, max=2.0, help="Override temperature."),
    system_prompt: str | None = Option(None, "--system", help="One-shot system prompt for this session."),
    max_tokens: int | None = Option(None, "--max-tokens", help="Override MAX_TOKENS cap."),
) -> None:
    """Interactive chat shell — sends user lines directly to the configured LLM provider."""
    from noesis.logging import configure_logging
    from noesis.types import ChatMessage, MessageRole

    configure_logging()
    try:
        from noesis.llm import get_provider
    except Exception as exc:
        console.print(f"[bold red]Failed to build provider registry: {exc}[/bold red]")
        raise Exit(2) from exc

    try:
        llm = get_provider(provider=provider, model=model, temperature=temperature, max_tokens=max_tokens)
    except Exception as exc:
        console.print(f"[bold red]Cannot configure provider: {exc}[/bold red]")
        console.print("Run [cyan]noesis doctor[/cyan] to debug missing credentials.")
        raise Exit(2) from exc

    console.print(
        Panel.fit(
            f"[bold]provider:[/bold] {llm.provider_id}    [bold]model:[/bold] {llm.model}    "
            f"[bold]T:[/bold] {llm.temperature}\n"
            f"[dim]Type a line to chat. Empty line to exit. Ctrl+C to quit.[/dim]",
            title="Noesis Shell",
            border_style="green",
        )
    )

    history: list[ChatMessage] = []
    if system_prompt:
        history.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
    try:
        import asyncio

        while True:
            line = console.input("[bold yellow]>[/bold yellow] ").strip()
            if not line:
                _echo("bye!", style="dim")
                return
            history.append(ChatMessage(role=MessageRole.USER, content=line))
            try:
                response = asyncio.run(llm.chat(history))
            except Exception as exc:
                console.print(f"[bold red]call failed: {exc}[/bold red]")
                continue
            history.append(ChatMessage(role=MessageRole.ASSISTANT, content=response.content))
            tokens = response.usage.total_tokens
            console.print(f"[bold green]{llm.provider_id}[/bold green] [dim]({tokens} tokens, {response.latency_ms:.0f}ms):[/dim]")
            console.print(response.content)
    except (EOFError, KeyboardInterrupt):
        _echo("\nbye!", style="dim")


# ---------------------------------------------------------------------------
# --- alembic wrapper (convenience)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# --- run (agent execution pipeline)
# ---------------------------------------------------------------------------


@app.command()
def run(
    goal: str = Option(
        ...,
        "--goal",
        "-g",
        help="High-level objective the 12-agent pipeline should accomplish.",
    ),
    seed: int = Option(
        42,
        "--seed",
        "-s",
        min=0,
        max=2**31 - 1,
        help="Deterministic seed. Same seed + goal => bit-exact same report output.",
    ),
    deterministic: bool = Option(
        True,
        "--deterministic/--adaptive",
        help="Use pure-Python seeded agents (default, 0 LLM calls) or live LLM provider.",
    ),
    agent: str | None = Option(
        None,
        "--agent",
        "-a",
        help="Run single agent type only (e.g. planner). Any AgentType value OK.",
    ),
    max_steps: int = Option(
        12,
        "--max-steps",
        min=1,
        max=256,
        help="Maximum Planner/Orchestrator steps.",
    ),
    workspace: str = Option(
        "default",
        "--workspace",
        "-w",
        help="Workspace id for call isolation + memory tier keying.",
    ),
    format: str = Option(
        "table",
        "--format",
        "-f",
        help="Output format: [table|json].",
    ),
    output: Path | None = Option(
        None,
        "--output",
        "-o",
        help="Write final aggregate JSON report to a file for audit/repro archives.",
    ),
) -> None:
    """Run a goal through the Noesis 12-agent deterministic pipeline.

    Defaults to ``--deterministic`` (pure-Python seeded agents, 0 LLM calls,
    0 token fees, bit-exact reproducibility — perfect for audits, demos, and
    the 100-run determinism manifest).  Use ``--adaptive`` for live LLM via
    the provider configured in ``.env.local``.

    \b
    Shell examples:
      noesis run -g "Produce a Rust CLI todo list" -s 42
      noesis run -g "Noesis architecture" -a planner -f json
      noesis run -g "Fix 3 parser bugs" --adaptive -o run_20260824.json
    """
    # Keep heavy imports local so `noesis --help` stays snappy.
    import hashlib
    import json
    import random as _py_random

    from noesis.agents.core import (
        AgentRoster,
        AgentRunContext,
        OrchestratorReport,
        PlannerReport,
    )
    from noesis.kernel.capabilities import (
        Capability,
        CapabilityOp,
        CapabilityToken,
        PermissionDenied,
    )
    from noesis.tools import ToolRegistry
    from noesis.types import AgentType, TaskStatus

    if deterministic:
        _py_random.seed(seed)

    owner = f"noesis-cli-seed-{seed}"
    token = CapabilityToken(owner_agent_id=owner, workspace_id=workspace)
    registry = ToolRegistry()

    default_caps: tuple[Capability, ...] = tuple(Capability(op, "*") for op in CapabilityOp)
    ctx = AgentRunContext(
        token=token,
        capabilities=default_caps,
        tools=registry,
        request_id=f"cli-{seed}-{hashlib.md5(goal.encode()).hexdigest()[:8]}",
        workspace_id=workspace,
    )

    t0 = time.perf_counter()
    steps_run: list[dict] = []
    pipeline_status = TaskStatus.SUCCESS
    final_summary = ""
    aggregate_report: dict | None = None

    try:
        # ----- Single agent short path ------------------------------------
        if agent is not None:
            try:
                atype = AgentType(agent)
            except ValueError:
                available = ", ".join(a.value for a in AgentRoster.all_types())
                console.print(f"[bold red]Unknown agent type {agent!r}.[/bold red]\nAvailable: {available}\n")
                raise Exit(2) from None
            inst = AgentRoster.spawn(atype, ctx)
            state: dict = {"goal": goal, "query": goal, "seed": seed, "max_steps": max_steps}
            out = inst.run(state, ctx)
            steps_run.append(
                {
                    "slot": 1,
                    "agent": atype.value,
                    "status": TaskStatus(out.get("status", TaskStatus.PENDING.value)).name,
                    "report_type": out.get("report_type"),
                    "summary": _cli_summarise_report(out.get("report")),
                }
            )
            aggregate_report = {"agent": atype.value, "goal": goal, "output": out}
            final_summary = steps_run[0]["summary"] or "(no summary)"
            pipeline_status = TaskStatus(out["status"])

        # ----- Full 12-agent pipeline -------------------------------------
        else:
            planner = AgentRoster.spawn(AgentType.PLANNER, ctx)
            plan_state: dict = {"goal": goal, "max_steps": max_steps, "seed": seed}
            plan_out = planner.run(plan_state, ctx)
            plan_report = PlannerReport(**plan_out["report"])
            steps_run.append(
                {
                    "slot": 1,
                    "agent": AgentType.PLANNER.value,
                    "status": TaskStatus(plan_out["status"]).name,
                    "report_type": "PlannerReport",
                    "summary": plan_report.summary[:120] + ("…" if len(plan_report.summary) > 120 else ""),
                }
            )
            if TaskStatus(plan_out["status"]) != TaskStatus.SUCCESS:
                pipeline_status = TaskStatus(plan_out["status"])
                final_summary = f"Planner failed: {plan_report.summary[:160]}"
                aggregate_report = {"plan": plan_out}
                raise Exit(3)

            orchestrator = AgentRoster.spawn(AgentType.ORCHESTRATOR, ctx)
            orch_workers_list = [s.agent_type for s in plan_report.steps[:max_steps]]
            orch_state = {
                "goal": goal,
                "seed": seed,
                "max_steps": max_steps,
                "workers": orch_workers_list,
                "join_policy": "all",
            }
            orch_out = orchestrator.run(orch_state, ctx)
            orch_report = OrchestratorReport(**orch_out["report"])
            steps_run.append(
                {
                    "slot": len(steps_run) + 1,
                    "agent": AgentType.ORCHESTRATOR.value,
                    "status": TaskStatus(orch_out["status"]).name,
                    "report_type": "OrchestratorReport",
                    "summary": orch_report.summary[:160],
                }
            )

            dispatched = [AgentType(w) for w in orch_report.dispatched_to]
            results_by_worker: dict[str, dict] = {}
            for i, wtype in enumerate(dispatched, start=len(steps_run) + 1):
                worker = AgentRoster.spawn(wtype, ctx)
                worker_state = {
                    "goal": goal,
                    "query": goal,
                    "seed": seed,
                    "max_steps": max_steps,
                    "plan": plan_report.model_dump(mode="json"),
                }
                wout = worker.run(worker_state, ctx)
                status_name = TaskStatus(wout["status"]).name
                steps_run.append(
                    {
                        "slot": i,
                        "agent": wtype.value,
                        "status": status_name,
                        "report_type": wout.get("report_type"),
                        "summary": _cli_summarise_report(wout.get("report")),
                    }
                )
                results_by_worker[wtype.value] = wout
                if status_name != TaskStatus.SUCCESS.name:
                    pipeline_status = TaskStatus.FAILED

            # Executor Kriyakārī tri-state sign-off gate
            try:
                executor = AgentRoster.spawn(AgentType.EXECUTOR, ctx)
                signoff_candidates = [
                    {
                        "worker": wt.value,
                        "report": results_by_worker[wt.value].get("report"),
                        "status": results_by_worker[wt.value].get("status"),
                    }
                    for wt in dispatched
                ]
                exec_state: dict = {
                    "goal": goal,
                    "seed": seed,
                    "candidate_reports": signoff_candidates,
                }
                exec_out = executor.run(exec_state, ctx)
                steps_run.append(
                    {
                        "slot": len(steps_run) + 1,
                        "agent": AgentType.EXECUTOR.value,
                        "status": TaskStatus(exec_out["status"]).name,
                        "report_type": exec_out.get("report_type"),
                        "summary": _cli_summarise_report(exec_out.get("report")),
                    }
                )
                aggregate_report = {
                    "goal": goal,
                    "seed": seed,
                    "deterministic": deterministic,
                    "workspace": workspace,
                    "planner": plan_out,
                    "orchestrator": orch_out,
                    "workers": results_by_worker,
                    "executor_signoff": exec_out,
                    "steps_run": steps_run,
                }
                decision = (exec_out.get("report") or {}).get("decision") or "(no decision)"
                final_summary = f"Executor sign-off gate: {decision!r}."
                if str(decision).lower() == "reject":
                    pipeline_status = TaskStatus.FAILED
            except PermissionDenied as pd:
                pipeline_status = TaskStatus.FAILED
                final_summary = f"Executor sign-off gated by PermissionDenied (op={pd.op.value}, target={pd.target}): {pd.details[:180]}"
                aggregate_report = {"error": "EXECUTOR_GATE_DENIED", "details": str(pd)}

    except PermissionDenied as pd:
        pipeline_status = TaskStatus.FAILED
        final_summary = f"Spawn-denied: {pd.op.value}:{pd.target} — {pd.details[:180]}"
        console.print(f"[bold red]⛔ {final_summary}[/bold red]")

    total_ms = round((time.perf_counter() - t0) * 1000, 2)
    status_style = "green" if pipeline_status == TaskStatus.SUCCESS else "red"

    if format == "json":
        payload = {
            "goal": goal,
            "seed": seed,
            "deterministic": deterministic,
            "single_agent": agent,
            "max_steps": max_steps,
            "workspace": workspace,
            "duration_ms": total_ms,
            "status": pipeline_status.name,
            "summary": final_summary,
            "steps": steps_run,
            "report": aggregate_report,
        }
        rendered = json.dumps(payload, indent=2, sort_keys=True, default=str)
        console.print(rendered)
        if output is not None:
            output.write_text(rendered, encoding="utf-8")
            _echo(f"[dim]Wrote JSON report → {output}[/dim]")
    else:
        console.print(
            Panel(
                "\n".join(
                    [
                        f"[bold]Goal[/bold]:         {goal}",
                        f"[bold]Seed[/bold]:         {seed}  "
                        + ("[bold green]deterministic[/bold green]" if deterministic else "[bold yellow]adaptive[/bold yellow]"),
                        f"[bold]Workspace[/bold]:    {workspace}",
                        f"[bold]Agent[/bold]:        {agent or 'full 12-agent pipeline'}  (max steps {max_steps})",
                        f"[bold]Duration[/bold]:     {total_ms} ms",
                        f"[bold]Result[/bold]:       [{status_style}]{pipeline_status.name}[/{status_style}]",
                        f"[bold]Summary[/bold]:      {final_summary}",
                    ]
                ),
                title="[bold purple]NOESIS RUN SUMMARY[/bold purple]",
                border_style="purple",
                expand=False,
            )
        )
        table = Table(
            title="Step-by-step report",
            show_lines=False,
            header_style="bold magenta",
        )
        table.add_column("#", justify="right", style="dim", no_wrap=True)
        table.add_column("Agent", style="cyan", no_wrap=True)
        table.add_column("Status", no_wrap=True)
        table.add_column("Report type", style="dim")
        table.add_column("Summary")
        for row in steps_run:
            row_style = (
                "green"
                if row["status"] == TaskStatus.SUCCESS.name
                else ("yellow" if row["status"] in {TaskStatus.RUNNING.name, TaskStatus.AWAITING_INPUT.name} else "red")
            )
            table.add_row(
                str(row["slot"]),
                row["agent"],
                f"[{row_style}]{row['status']}[/{row_style}]",
                row.get("report_type") or "",
                row.get("summary") or "",
            )
        console.print(table)

        if output is not None:
            payload = {
                "goal": goal,
                "seed": seed,
                "deterministic": deterministic,
                "single_agent": agent,
                "max_steps": max_steps,
                "workspace": workspace,
                "duration_ms": total_ms,
                "status": pipeline_status.name,
                "summary": final_summary,
                "steps": steps_run,
                "report": aggregate_report,
            }
            output.write_text(
                json.dumps(payload, indent=2, sort_keys=True, default=str),
                encoding="utf-8",
            )
            _echo(f"[dim]Wrote JSON audit report → {output}[/dim]")

    raise Exit(0 if pipeline_status == TaskStatus.SUCCESS else 4)


def _cli_summarise_report(report: object) -> str:
    """Pull a short one-line human-readable snippet from any report dict."""
    if not isinstance(report, dict):
        return ""
    for key in (
        "summary",
        "overall",
        "decision",
        "reasoning",
        "plan_summary",
        "top_ranked_summary",
        "signoff_reason",
    ):
        val = report.get(key)
        if isinstance(val, str) and val:
            snippet = val.strip().splitlines()[0]
            if len(snippet) > 160:
                snippet = snippet[:157] + "…"
            return snippet
    if not report:
        return "(empty)"
    keys = sorted(k for k in report.keys() if not k.startswith("_"))[:6]
    return f"report keys: {', '.join(keys)}"


@app.command(name="db:upgrade")
def db_upgrade(revision: str = Option("head", "--revision", help="Target Alembic revision, or 'head' for latest.")) -> None:
    """Apply pending Alembic migrations to the configured database."""

    _run_alembic(["upgrade", revision])


@app.command(name="db:downgrade")
def db_downgrade(revision: str = Option("-1", "--revision", help="Target Alembic revision (e.g. 'base', '-1').")) -> None:
    """Roll back Alembic migrations."""
    _run_alembic(["downgrade", revision])


@app.command(name="db:makemigrations")
def db_makemigrations(message: str = Option("auto", "-m", "--message", help="Revision message.")) -> None:
    """Generate a new Alembic migration by diffing Base.metadata vs the current DB schema."""
    _run_alembic(["revision", "--autogenerate", "-m", message])


def _run_alembic(args: list[str]) -> None:
    import subprocess

    backend_root = Path(__file__).resolve().parent.parent
    cmd = [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args]
    _echo(f"[dim]RUN {' '.join(cmd)}[/dim]")
    completed: subprocess.CompletedProcess[int] | None = None
    try:
        completed = subprocess.run(
            cmd,
            cwd=backend_root,
            check=False,  # we translate returncode into typer.Exit ourselves
        )
    except KeyboardInterrupt:  # pragma: no cover
        console.print("[dim]user interrupt[/dim]")
        raise Exit(130) from None
    raise Exit(completed.returncode if completed is not None else 1)


# ---------------------------------------------------------------------------
# --- plugins (sysadmin: list / verify / load / unload)
# ---------------------------------------------------------------------------


plugins_app = Typer(
    name="plugins",
    help="Plugin sub-system: list / verify / load / unload.",
    no_args_is_help=True,
)
app.add_typer(plugins_app)


def _run(coro):  # type: ignore[no-untyped-def]
    """Small async runner for CLI commands."""
    import asyncio

    return asyncio.run(coro)


def _plugins_render_json(rows: list[dict]) -> str:
    import orjson

    return orjson.dumps(rows, option=orjson.OPT_INDENT_2).decode()


@plugins_app.command(name="list")
def plugins_list(
    format: str = Option("table", "--format", "-f", help="Output format: [table|json]."),
    plugins_dir: list[Path] | None = Option(
        None, "--dir", "-d", help="Directory to discover plugins in (discover only, no kernel boot).  Repeat for multiple dirs."
    ),
) -> None:
    """List installed plugins.

    Without ``--dir`` boots the full Noesis container + Kernel + PluginManager
    so it reflects the exact set a running `noesis serve` would see.  With
    ``--dir`` it's a lightweight offline discover (useful for pre-deploy CI).
    """
    from noesis.plugins.manager import PluginLifecycleState

    rows: list[dict] = []
    if plugins_dir:
        # Offline discover-only path (no kernel).  Reuse PluginManager class
        # by constructing with a temporary in-memory kernel.
        from noesis.kernel import Kernel
        from noesis.plugins.manager import PluginManager

        async def _offline() -> None:
            k = Kernel.build_default()
            pm = PluginManager(k)
            for d in plugins_dir:
                await pm.discover(dirs=[d], include_entry_points=False)
            for rid, state, manifest in pm.list_plugins():
                rows.append(
                    {
                        "id": rid,
                        "version": manifest.version,
                        "state": state.value,
                        "name": manifest.name,
                        "author": manifest.author,
                        "kind": manifest.kind_human,
                        "entry_point": manifest.entry_point or "",
                    }
                )

        _run(_offline())
    else:
        # Full boot path (same as serve lifespan).
        from noesis.core.di import build_default_container
        from noesis.plugins import PluginManager

        async def _booted() -> None:
            c = build_default_container()
            from noesis.kernel import Kernel

            k: Kernel = await c.get(Kernel)
            await k.start()
            pm = PluginManager(k)
            for d in [Path("./plugins")]:
                if d.is_dir():
                    with contextlib.suppress(Exception):
                        await pm.discover(dirs=[d])
            await pm.boot_all()
            for rid, state, manifest in pm.list_plugins():
                rows.append(
                    {
                        "id": rid,
                        "version": manifest.version,
                        "state": state.value,
                        "name": manifest.name,
                        "author": manifest.author,
                        "kind": manifest.kind_human,
                        "entry_point": manifest.entry_point or "",
                    }
                )
            await c.aclose()

        _run(_booted())

    if format == "json":
        sys.stdout.write(_plugins_render_json(rows) + "\n")
        raise Exit(0)

    if not rows:
        _echo("[dim](no plugins loaded)[/dim]")
        raise Exit(0)

    t = Table(title="Noesis Plugins", header_style="bold magenta")
    t.add_column("ID", style="bold")
    t.add_column("VERSION")
    t.add_column("STATE", style="bold")
    t.add_column("NAME")
    t.add_column("AUTHOR")
    t.add_column("KIND")
    t.add_column("ENTRY_POINT", overflow="fold")
    for r in rows:
        st_ok = r["state"] == PluginLifecycleState.HOOKS_RUNNING.value
        st_style = "green" if st_ok else ("yellow" if r["state"] == PluginLifecycleState.REGISTERED.value else "red")
        t.add_row(
            r["id"],
            r["version"],
            f"[{st_style}]{r['state']}[/{st_style}]",
            r["name"],
            r["author"],
            r["kind"],
            r["entry_point"],
        )
    console.print(t)
    raise Exit(0)


@plugins_app.command("verify")
def plugins_verify(
    directory: Path = Option(
        ..., "--dir", "-d", exists=False, help="Plugin directory to scan (will be searched recursively for manifest.json files)."
    ),
    strict: bool = Option(False, "--strict", help="Exit non-zero if any manifest has warnings (SHA mismatch / missing entry point)."),
    format: str = Option("table", "--format", "-f", help="Output format: [table|json]."),
) -> None:
    """Validate manifest.json files BEFORE loading them into a running kernel.

    Prints every discovered manifest with status codes.  Exit codes:
      0  → all ok (or --strict off + only warnings)
      1  → --strict was on and at least one manifest had warnings
      2  → directory did not exist or contained parse errors
    """
    from noesis.plugins.manager import PluginManager

    results = PluginManager.verify_manifest_directory(directory)
    rows = []
    any_bad = False
    any_warn = False
    for path, manifest, status in results:
        bad = status.startswith("invalid:") or status == "no_manifest_found"
        warn = status not in {"ok"} and not bad
        if bad:
            any_bad = True
        if warn:
            any_warn = True
        rows.append(
            {
                "path": str(path),
                "id": manifest.id if manifest else "-",
                "version": manifest.version if manifest else "-",
                "status": status,
                "ok": status == "ok",
            }
        )

    if format == "json":
        sys.stdout.write(_plugins_render_json(rows) + "\n")
    else:
        t = Table(title=f"Verify: {directory}", header_style="bold magenta")
        t.add_column("PATH", overflow="fold")
        t.add_column("ID")
        t.add_column("VERSION")
        t.add_column("STATUS", style="bold")
        for r in rows:
            style = (
                "green" if r["ok"] else ("yellow" if r["status"].startswith("invalid:") is False and r["status"] != "no_manifest_found" else "red")
            )
            # column already added above; t.add_column intentional no-op removed
            t.add_row(r["path"], r["id"], r["version"], f"[{style}]{r['status']}[/{style}]")
        console.print(t)

    if any_bad:
        raise Exit(2)
    if strict and any_warn:
        raise Exit(1)
    raise Exit(0)


@plugins_app.command("load")
def plugins_load(
    manifest_path: Path = Option(..., "--manifest", "-m", help="Path to a single manifest.json file to load."),
    plugins_dir: Path = Option(None, "--dir", "-d", help="Alternative: load every manifest.json found under this directory."),
) -> None:
    """Load plugin(s) into a transient kernel and print their post-load state.

    Useful as a smoke test in CI pipelines before `kubectl apply`-ing a config
    that references a new plugin version.
    """
    from noesis.plugins.manager import PluginLoadError, PluginManager
    from noesis.plugins.manifest import PluginManifest

    async def _go() -> list[tuple[str, str, str]]:
        from noesis.kernel import Kernel

        k = Kernel.build_default()
        await k.start()
        pm = PluginManager(k)
        manifests: list[PluginManifest] = []
        if plugins_dir is not None:
            from noesis.plugins.manager import PluginManager as _PM

            for _p, m, s in _PM.verify_manifest_directory(plugins_dir):
                if m is not None and s == "ok":
                    manifests.append(m)
        if manifest_path.exists():
            manifests.append(PluginManifest.from_disk(manifest_path))
        loaded: list[tuple[str, str, str]] = []
        for m in manifests:
            try:
                await pm.load_from_manifest(m)
                loaded.append((m.id, m.version, "registered"))
            except PluginLoadError as exc:
                loaded.append((m.id, m.version, f"failed:{exc.reason}"))
        await pm.boot_all()
        for rid, state, _m in pm.list_plugins():
            loaded = [(r_id, r_v, state.value if r_id == rid else r_s) for (r_id, r_v, r_s) in loaded]
        return loaded

    results = _run(_go())
    rows = [{"id": rid, "version": ver, "state": s} for (rid, ver, s) in results]
    # human-readable default; --format is not needed for load (json vs table would be nice but keep simple)
    t = Table(title="Plugin load results", header_style="bold magenta")
    t.add_column("ID", style="bold")
    t.add_column("VERSION")
    t.add_column("STATE")
    for r in rows:
        style = "green" if r["state"] in {"registered", "hooks_running"} else "red"
        t.add_row(r["id"], r["version"], f"[{style}]{r['state']}[/{style}]")
    console.print(t)
    any_fail = any(r["state"].startswith("failed:") for r in rows)
    raise Exit(1 if any_fail else 0)


@plugins_app.command("unload")
def plugins_unload(
    plugin_id: str = Option(..., "--id", help="Plugin id (DNS-reverse form, e.g. com.example.myplugin)."),
    purge: bool = Option(False, "--purge", help="Also forget the plugin record entirely (default: keep UNLOADED state for audit)."),
) -> None:
    """Unload a single plugin from a booted kernel.

    Boots a kernel + discovers ./plugins to match plugin IDs, then unloads.
    Returns 0 if plugin was found and unloaded, 1 otherwise.
    """
    from noesis.plugins.manager import PluginManager

    async def _go() -> bool:
        from pathlib import Path as _P

        from noesis.kernel import Kernel

        k = Kernel.build_default()
        await k.start()
        pm = PluginManager(k)
        d = _P("./plugins")
        if d.is_dir():
            await pm.discover(dirs=[d])
        return await pm.unload(plugin_id, remove_from_registry=purge)

    ok = _run(_go())
    if ok:
        _echo(f"[bold green]Plugin {plugin_id!r} unloaded (purge={purge}).[/bold green]")
        raise Exit(0)
    console.print(f"[bold red]Plugin {plugin_id!r} not found — nothing to unload.[/bold red]")
    raise Exit(1)


def main() -> None:  # pragma: no cover - entry point, exercised manually
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
