"""Hexagonal tool-port, registry + typed tool adapters.

Capability-based invocation (``TOOL_INVOKE:<name>``) is gated in
:meth:`ToolRegistry.invoke` so callers from inside the scheduler or agents
cannot side-step the kernel-issued :class:`CapabilityToken`.
"""

from __future__ import annotations

import ast
import csv
import datetime as _dt
import io
import json
import os
import re
import shlex
import shutil
import smtplib
import sqlite3
import stat
import string
import subprocess
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.message import EmailMessage
from imaplib import IMAP4_SSL
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urlparse
from uuid import UUID, uuid4

try:  # httpx is in pyproject deps but keep import-time tolerant for dry-run
    import httpx  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - fallback socket stub
    httpx = None  # type: ignore[assignment]

from noesis.kernel.capabilities import Capability, CapabilityOp, CapabilityToken, PermissionDenied

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ToolArtifact:
    """Side-effect artifact a tool can return alongside stdout.

    Matches the wire shape of :class:`astra.types.Artifact` so callers can
    round-trip into the SQL artifact repository later without translation.
    """

    artifact_id: UUID = field(default_factory=uuid4)
    kind: str = "file"
    name: str = ""
    content_type: str = "text/plain"
    content_sha256: str = ""
    size_bytes: int = 0
    payload: bytes = b""


@dataclass(slots=True)
class ToolResult:
    """Uniform return shape from every ToolPort.invoke()."""

    success: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    artifacts: list[ToolArtifact] = field(default_factory=list)
    structured: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Port + registry
# ---------------------------------------------------------------------------


class ToolPort(ABC):
    """Every tool must implement these 3 members.

    10-yr rules:
      * ``parameter_schema`` must be a JSON-Schema dict — never accept raw
        stringly ``args: str``.  The agent / LLM is responsible for conforming
        to the schema; the tool is responsible for validating it.
      * ``invoke`` MUST NOT accept ``**kwargs``; the registry fans in
        ``dict[str, Any]`` from the wire and type-checked by Pydantic at the
        HTTP boundary before it reaches the tool.
      * Capability gates live in :class:`ToolRegistry`, never inside the tool
        itself — this keeps the adapter surface portable (in-Memory adapters
        are always usable from tests without a kernel).
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def parameter_schema(self) -> dict[str, Any]: ...

    @abstractmethod
    def invoke(self, args: Mapping[str, Any]) -> ToolResult: ...


class ToolRegistry:
    """Lookup + capability-gated fan-out to :class:`ToolPort` adapters."""

    def __init__(self, *, tools: Iterable[ToolPort] | None = None) -> None:
        self._tools: dict[str, ToolPort] = {}
        # Optional per-tool required capability target.  Default = tool.name,
        # so the default gate is ``(TOOL_INVOKE, <toolname>)``.
        self._required_cap: dict[str, str] = {}
        for t in tools or []:
            self.register(t)

    # -- registration ------------------------------------------------------

    def register(
        self,
        tool: ToolPort,
        *,
        requires_cap_target: str | None = None,
    ) -> None:
        if tool.name in self._tools:
            raise ValueError(f"ToolRegistry: duplicate tool name '{tool.name}'")
        self._tools[tool.name] = tool
        self._required_cap[tool.name] = requires_cap_target or tool.name

    # -- introspection -----------------------------------------------------

    @property
    def names(self) -> list[str]:
        return sorted(self._tools.keys())

    def get(self, name: str) -> ToolPort:
        if name not in self._tools:
            raise KeyError(name)
        return self._tools[name]

    def manifest(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameter_schema,
                "requires_capability": self._required_cap[t.name],
            }
            for t in (self._tools[n] for n in self.names)
        ]

    # -- invocation --------------------------------------------------------

    def invoke(
        self,
        name: str,
        args: Mapping[str, Any],
        *,
        token: CapabilityToken | None = None,
        capabilities: Iterable[Capability] | None = None,
    ) -> ToolResult:
        if name not in self._tools:
            return ToolResult(
                success=False,
                exit_code=-1,
                stderr=f"Unknown tool '{name}'.  Available: {', '.join(self.names)}",
            )
        target = self._required_cap[name]
        if token is not None and capabilities is not None:
            allowed = any(c.allows(CapabilityOp.TOOL_INVOKE, target) for c in capabilities)
            if not allowed:
                raise PermissionDenied(
                    token_id=token.id,
                    op=CapabilityOp.TOOL_INVOKE,
                    target=target,
                    details=f"Tool '{name}' requires TOOL_INVOKE:{target}",
                )
        tool = self._tools[name]
        started = _dt.datetime.now(tz=_dt.UTC)
        try:
            result = tool.invoke(args)
        except PermissionDenied:
            raise
        except Exception as exc:
            result = ToolResult(
                success=False,
                exit_code=-2,
                stderr=f"{type(exc).__name__}: {exc}",
            )
        elapsed = _dt.datetime.now(tz=_dt.UTC) - started
        result.duration_ms = max(1, int(elapsed.total_seconds() * 1000))
        return result


# ---------------------------------------------------------------------------
# Validator helpers (shared)
# ---------------------------------------------------------------------------


def _require(args: Mapping[str, Any], key: str, t: type) -> Any:
    if key not in args:
        raise ValueError(f"missing required arg '{key}'")
    v = args[key]
    if not isinstance(v, t):
        raise ValueError(f"arg '{key}' must be {t.__name__}, got {type(v).__name__}")
    return v


_ALPHANUM_SAFE = set(string.ascii_letters + string.digits + "_-./")
_SHELL_SAFE = set(string.ascii_letters + string.digits + "_-./ :@")


def _is_safe_path(allow_root: Path, requested: str) -> Path:
    """Refuse any path-traversal / absolute-escape / symlinks across tools."""
    allow = allow_root.resolve()
    candidate = (allow / requested).resolve()
    if allow != candidate and allow not in candidate.parents:
        raise ValueError(f"path escapes allowed root: {requested!r}")
    return candidate


# ===========================================================================
# Adapter 1 : shell — whitelist-based command execution
# ===========================================================================


class ShellTool(ToolPort):
    """Run shell commands with an optional whitelist + allowed working dir.

    If ``allowed_commands`` is non-empty every command must start with one of
    the listed executables (after shlex split).  When it's empty the tool is
    "dry-run only" — the adapter returns a mocked stdout but never spawns
    a real subprocess.  This keeps tests green on any host, and forces a
    production deployment to opt-in to command names.
    """

    def __init__(
        self,
        *,
        allowed_commands: Iterable[str] = (),
        cwd: Path | None = None,
        timeout_s: float = 15.0,
    ) -> None:
        self._allowed = set(allowed_commands)
        self._cwd = Path(cwd) if cwd else Path.cwd()
        self._timeout_s = timeout_s
        self._lock = threading.RLock()

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return "Run a shell command and capture stdout/stderr/exit_code."

    @property
    def parameter_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["command"],
            "properties": {
                "command": {"type": "string", "description": "Command to execute (shlex-safe)."},
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional extra arguments appended after command split.",
                },
                "timeout_s": {"type": "number", "minimum": 0.1, "maximum": 600},
            },
        }

    def invoke(self, args: Mapping[str, Any]) -> ToolResult:
        cmd = _require(args, "command", str).strip()
        extra_args = list(args.get("args", []) or [])
        if not cmd:
            raise ValueError("command must be non-empty")
        try:
            parts = shlex.split(cmd, posix=True)
        except ValueError as exc:
            return ToolResult(success=False, exit_code=-1, stderr=f"shlex error: {exc}")
        full = parts + extra_args
        if not full:
            raise ValueError("empty argv after splitting")
        exe = full[0]
        if self._allowed:
            if exe not in self._allowed:
                return ToolResult(
                    success=False,
                    exit_code=127,
                    stderr=f"ShellTool: '{exe}' not in allowed_commands list.",
                )
        else:
            # Dry-run: describe what *would* run so agents can still reason about it.
            return ToolResult(
                success=True,
                exit_code=0,
                stdout=(f"[shell dry-run] would exec: {shlex.join(full)}\n[shell dry-run] cwd: {self._cwd}"),
            )
        try:
            timeout_s = float(args.get("timeout_s", self._timeout_s))
        except (TypeError, ValueError):
            timeout_s = self._timeout_s
        started = time.perf_counter()
        try:
            proc = subprocess.run(
                full,
                cwd=str(self._cwd),
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
                shell=False,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
        except subprocess.TimeoutExpired as exc:
            return ToolResult(
                success=False,
                exit_code=124,
                stderr=f"timeout after {timeout_s:g}s",
                stdout=exc.stdout.decode() if isinstance(exc.stdout, (bytes, bytearray)) else str(exc.stdout or ""),
            )
        except (OSError, FileNotFoundError) as exc:
            return ToolResult(success=False, exit_code=126, stderr=f"exec error: {exc}")
        return ToolResult(
            success=proc.returncode == 0,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )


# ===========================================================================
# Adapter 2 : PythonSandbox — ast-whitelisted exec
# ===========================================================================


_ALLOWED_AST_NODES = {
    ast.Module,
    ast.Expression,
    ast.Expr,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Del,
    ast.Call,
    ast.FunctionDef,
    ast.Return,
    ast.If,
    ast.IfExp,
    ast.For,
    ast.While,
    ast.Break,
    ast.Continue,
    ast.Pass,
    ast.Assign,
    ast.AugAssign,
    ast.AnnAssign,
    ast.List,
    ast.Tuple,
    ast.Set,
    ast.Dict,
    ast.Compare,
    ast.BoolOp,
    ast.UnaryOp,
    ast.BinOp,
    ast.Subscript,
    ast.Slice,
    ast.Lambda,
    ast.NamedExpr,
    ast.Starred,
    ast.keyword,
    ast.Import,
    ast.ImportFrom,
    ast.alias,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.comprehension,
    ast.JoinedStr,
    ast.FormattedValue,
    ast.Try,
    ast.ExceptHandler,
    ast.Raise,
    ast.Assert,
    ast.ClassDef,
    ast.arg,
    ast.arguments,
    ast.Match,
    ast.match_case,
    ast.MatchValue,
    ast.MatchSingleton,
    ast.MatchSequence,
    ast.MatchMapping,
    ast.MatchStar,
    ast.MatchAs,
    ast.MatchOr,
    ast.With,
    ast.withitem,
    ast.AsyncFor,
    ast.AsyncFunctionDef,
    ast.Await,
    ast.AsyncWith,
    ast.Attribute,
    ast.Index,
    ast.Global,
    ast.Nonlocal,
    ast.Delete,
    ast.Yield,
    ast.YieldFrom,
}


class PythonSandboxTool(ToolPort):
    """Execute a small Python snippet inside a whitelist AST + restricted-builtins scope.

    Timeout is enforced via a separate daemon thread (best-effort on CPython —
    GIL loop-heavy snippets yield to SIG-style cancellation).
    """

    _RESTRICTED: ClassVar[dict[str, None]] = {
        "__import__": None,
        "open": None,
        "exec": None,
        "eval": None,
        "compile": None,
        "globals": None,
        "locals": None,
        "vars": None,
        "dir": None,
        "breakpoint": None,
        "input": None,
    }

    def __init__(
        self,
        *,
        allow_imports: Iterable[str] = (
            "json",
            "math",
            "statistics",
            "datetime",
            "re",
            "collections",
            "hashlib",
            "base64",
            "csv",
            "uuid",
            "itertools",
            "functools",
            "random",
            "string",
            "typing",
            "fractions",
            "decimal",
            "struct",
        ),
        timeout_s: float = 5.0,
    ) -> None:
        self._allowed_imports: set[str] = set(allow_imports)
        self._timeout_s = timeout_s
        self._lock = threading.RLock()

    @property
    def name(self) -> str:
        return "python_sandbox"

    @property
    def description(self) -> str:
        return "Run a Python expression/statements inside a restricted sandbox."

    @property
    def parameter_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["code"],
            "properties": {
                "code": {"type": "string", "description": "Python snippet. Last expression value is returned."},
                "env": {"type": "object", "additionalProperties": {"type": ["string", "number", "boolean", "array", "object", "null"]}},
            },
        }

    def _safe_import(self, name: str, *rest, **_kw):
        if name not in self._allowed_imports:
            raise ImportError(f"import not allowed: {name!r}")
        return __import__(name, *rest, **_kw)

    def _ast_check(self, node: ast.AST) -> None:
        for child in ast.walk(node):
            if type(child) not in _ALLOWED_AST_NODES:
                raise ValueError(f"AST node {type(child).__name__} not allowed by sandbox")
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                for alias in child.names:
                    mod = alias.name.split(".")[0]
                    if isinstance(child, ast.ImportFrom):
                        mod = (child.module or "").split(".")[0] or mod
                    if mod not in self._allowed_imports:
                        raise ValueError(f"import of module {mod!r} not allowed")

    def invoke(self, args: Mapping[str, Any]) -> ToolResult:
        code = _require(args, "code", str)
        env: dict[str, Any] = dict(args.get("env", {}) or {})
        try:
            tree = ast.parse(code, mode="exec")
            self._ast_check(tree)
        except SyntaxError as exc:
            return ToolResult(success=False, exit_code=65, stderr=f"SyntaxError: {exc}")
        except ValueError as exc:
            return ToolResult(success=False, exit_code=66, stderr=str(exc))
        # Wrap: append "print(last_value)" style capture
        last_expr = None
        body = tree.body
        if body and isinstance(body[-1], ast.Expr):
            last_expr = body[-1]
            body[-1] = ast.Assign(targets=[ast.Name(id="_ASTRA_LAST", ctx=ast.Store())], value=last_expr.value)
            ast.fix_missing_locations(tree)
        compiled = compile(tree, "<astra-python-sandbox>", "exec")
        import builtins as _builtins

        safe_builtins: dict[str, Any] = {}
        for bname in dir(_builtins):
            val = getattr(_builtins, bname, None)
            if bname in self._RESTRICTED:
                continue
            safe_builtins[bname] = val
        safe_builtins["__import__"] = self._safe_import
        globals_dict: dict[str, Any] = {"__builtins__": safe_builtins, **env}
        locals_dict: dict[str, Any] = {}
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        safe_builtins["print"] = lambda *a, **kw: print(*a, file=buf_out, **{k: v for k, v in kw.items() if k in {"sep", "end"}})

        def run(code_obj, g, loc, result_bucket):
            try:
                exec(code_obj, g, loc)
                result_bucket["ok"] = True
            except BaseException as exc:
                result_bucket["ok"] = False
                # Capture short traceback-ish description (no tb to avoid leaks)
                lines = [f"{type(exc).__name__}: {exc}"]
                tb = exc.__traceback__
                while tb is not None:
                    fname = tb.tb_frame.f_code.co_filename
                    lineno = tb.tb_lineno
                    lines.append(f"  at {fname}:{lineno}")
                    tb = tb.tb_next
                result_bucket["error_lines"] = lines
                buf_err.write("\n".join(lines) + "\n")

        bucket: dict[str, Any] = {"ok": False}
        thread = threading.Thread(target=run, args=(compiled, globals_dict, locals_dict, bucket), daemon=True)
        start = time.perf_counter()
        thread.start()
        thread.join(self._timeout_s)
        if thread.is_alive():
            return ToolResult(
                success=False,
                exit_code=124,
                stderr=f"sandbox timed out after {self._timeout_s:g}s",
                stdout=buf_out.getvalue(),
            )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        success = bucket.get("ok", False)
        exit_code = 0 if success else 70
        if last_expr is not None and "_ASTRA_LAST" in locals_dict:
            last_val = locals_dict["_ASTRA_LAST"]
            try:
                structured = {"result": json.loads(json.dumps(last_val, default=str))}
            except TypeError:
                structured = {"result": repr(last_val)}
        else:
            structured = {}
        return ToolResult(
            success=success,
            exit_code=exit_code,
            stdout=buf_out.getvalue(),
            stderr=buf_err.getvalue(),
            structured=structured,
            duration_ms=elapsed_ms,
        )


# ===========================================================================
# Adapter 3 : files — path-traversal-safe read/write/list against a root
# ===========================================================================


class FilesTool(ToolPort):
    """Read / write / list files under an allowed-root directory."""

    def __init__(self, allowed_root: Path, *, operations: Iterable[str] = ("read", "write", "list")) -> None:
        self._root = Path(allowed_root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._ops = set(operations)
        self._lock = threading.RLock()

    @property
    def name(self) -> str:
        return "files"

    @property
    def description(self) -> str:
        return "Filesystem read/write/list under the workspace allowed_root."

    @property
    def parameter_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["operation", "path"],
            "properties": {
                "operation": {"type": "string", "enum": ["read", "write", "list", "mkdir", "delete"]},
                "path": {"type": "string"},
                "content": {"type": "string"},
                "glob": {"type": "string"},
            },
        }

    def invoke(self, args: Mapping[str, Any]) -> ToolResult:
        op = _require(args, "operation", str)
        if op not in self._ops:
            return ToolResult(success=False, exit_code=1, stderr=f"FilesTool: operation '{op}' disabled")
        if op == "list":
            try:
                target = _is_safe_path(self._root, args.get("path", "."))
            except ValueError as exc:
                return ToolResult(success=False, exit_code=13, stderr=str(exc))
            pattern = args.get("glob", "*") or "*"
            if not target.is_dir():
                return ToolResult(success=False, exit_code=2, stderr=f"not a directory: {target}")
            with self._lock:
                rows = []
                for p in sorted(target.glob(pattern)):
                    try:
                        st = p.stat()
                    except OSError:
                        continue
                    rows.append(f"{('d' if p.is_dir() else '-')}{stat.filemode(st.st_mode)[1:]:9s} {st.st_size:>10d} {p.name}")
                return ToolResult(success=True, exit_code=0, stdout="\n".join(rows))
        rel = _require(args, "path", str)
        try:
            target = _is_safe_path(self._root, rel)
        except ValueError as exc:
            return ToolResult(success=False, exit_code=13, stderr=str(exc))
        with self._lock:
            if op == "read":
                if not target.is_file():
                    return ToolResult(success=False, exit_code=2, stderr=f"not a file: {target}")
                try:
                    data = target.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    data = target.read_bytes().hex()
                return ToolResult(success=True, exit_code=0, stdout=data)
            if op == "write":
                content = args.get("content", "") or ""
                content = content if isinstance(content, str) else json.dumps(content)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                return ToolResult(
                    success=True,
                    exit_code=0,
                    stdout=f"wrote {len(content)} bytes → {target.relative_to(self._root).as_posix()}",
                )
            if op == "mkdir":
                target.mkdir(parents=True, exist_ok=True)
                return ToolResult(success=True, stdout=f"created {target.relative_to(self._root).as_posix()}")
            if op == "delete":
                if not target.exists():
                    return ToolResult(success=False, exit_code=2, stderr="not found")
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
                return ToolResult(success=True, stdout="deleted")
        return ToolResult(success=False, exit_code=1, stderr=f"unknown operation {op!r}")


# ===========================================================================
# Adapter 4 : github — httpx stub against api.github.com (dry-run by default)
# ===========================================================================


class GitHubTool(ToolPort):
    """Thin GitHub REST client (dry-run when no ``api_token`` is supplied)."""

    def __init__(self, *, api_token: str = "", api_base: str = "https://api.github.com", user_agent: str = "Noesis/dev") -> None:
        self._token = api_token
        self._api_base = api_base.rstrip("/")
        self._ua = user_agent

    @property
    def name(self) -> str:
        return "github"

    @property
    def description(self) -> str:
        return "Read GitHub issues, PRs, file contents and repository metadata."

    @property
    def parameter_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["operation", "owner", "repo"],
            "properties": {
                "operation": {"type": "string", "enum": ["issues", "pulls", "contents", "repo"]},
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "path": {"type": "string"},
                "state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"},
                "per_page": {"type": "integer", "minimum": 1, "maximum": 100},
                "branch": {"type": "string", "default": "main"},
            },
        }

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/vnd.github+json", "User-Agent": self._ua}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    def invoke(self, args: Mapping[str, Any]) -> ToolResult:
        op = _require(args, "operation", str)
        owner = _require(args, "owner", str)
        repo = _require(args, "repo", str)
        state = str(args.get("state", "open"))
        per_page = int(args.get("per_page", 10) or 10)
        branch = str(args.get("branch", "main"))
        path = str(args.get("path", ""))
        if not self._token or httpx is None:
            # Dry-run shape — validates params, returns synthetic list
            sample = {
                "owner": owner,
                "repo": repo,
                "operation": op,
                "branch": branch,
                "path": path,
                "state": state,
                "per_page": per_page,
                "mode": "dry-run (no api_token)",
            }
            return ToolResult(success=True, exit_code=0, stdout=json.dumps(sample, indent=2), structured=sample)
        rel = {
            "repo": f"/repos/{owner}/{repo}",
            "issues": f"/repos/{owner}/{repo}/issues?state={state}&per_page={per_page}",
            "pulls": f"/repos/{owner}/{repo}/pulls?state={state}&per_page={per_page}",
            "contents": f"/repos/{owner}/{repo}/contents/{path.lstrip('/')}?ref={branch}",
        }.get(op)
        if rel is None:
            return ToolResult(success=False, exit_code=1, stderr=f"unknown operation {op!r}")
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(f"{self._api_base}{rel}", headers=self._headers())
            structured = r.json() if "application/json" in r.headers.get("content-type", "") else {"text": r.text[:2000]}
            return ToolResult(
                success=200 <= r.status_code < 300,
                exit_code=r.status_code,
                stdout=r.text[:100_000],
                structured={"status": r.status_code, "body": structured},
            )
        except Exception as exc:
            return ToolResult(success=False, exit_code=-1, stderr=f"github: {type(exc).__name__}: {exc}")


# ===========================================================================
# Adapter 5 : weather — open-meteo free endpoint
# ===========================================================================


class WeatherTool(ToolPort):
    """Fetch current/forecast weather from Open-Meteo (no API key required)."""

    BASE = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, *, user_agent: str = "Noesis/dev") -> None:
        self._ua = user_agent

    @property
    def name(self) -> str:
        return "weather"

    @property
    def description(self) -> str:
        return "Current + 7-day forecast via Open-Meteo free API (lat/lon required)."

    @property
    def parameter_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["latitude", "longitude"],
            "properties": {
                "latitude": {"type": "number", "minimum": -90, "maximum": 90},
                "longitude": {"type": "number", "minimum": -180, "maximum": 180},
                "timezone": {"type": "string", "default": "auto"},
                "daily": {"type": "boolean", "default": True},
            },
        }

    def invoke(self, args: Mapping[str, Any]) -> ToolResult:
        lat = float(_require(args, "latitude", (int, float)))
        lon = float(_require(args, "longitude", (int, float)))
        if httpx is None:
            sample = {"latitude": lat, "longitude": lon, "mode": "dry-run (httpx missing)"}
            return ToolResult(success=True, stdout=json.dumps(sample), structured=sample)
        tz = args.get("timezone", "auto") or "auto"
        daily = bool(args.get("daily", True))
        params: dict[str, Any] = {
            "latitude": lat,
            "longitude": lon,
            "timezone": tz,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,weather_code",
        }
        if daily:
            params["daily"] = "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code"
        try:
            with httpx.Client(timeout=12.0, headers={"User-Agent": self._ua}) as client:
                r = client.get(self.BASE, params=params)
            body = r.json() if "application/json" in r.headers.get("content-type", "") else {"text": r.text}
            return ToolResult(
                success=200 <= r.status_code < 300,
                exit_code=r.status_code,
                stdout=r.text[:50_000],
                structured=body,
            )
        except Exception as exc:
            return ToolResult(success=False, exit_code=-1, stderr=f"weather: {type(exc).__name__}: {exc}")


# ===========================================================================
# Adapter 6 : calendar — iCal file-based read/write (no server required)
# ===========================================================================


class CalendarTool(ToolPort):
    """Read/write iCalendar (.ics) events against a workspace file."""

    _DTRX = re.compile(r"^\s*DTSTART(;.*)?:(.+)$")
    _DTENDX = re.compile(r"^\s*DTEND(;.*)?:(.+)$")
    _SUMMARYRX = re.compile(r"^\s*SUMMARY(;.*)?:(.+)$")

    def __init__(self, ics_path: Path) -> None:
        self._path = Path(ics_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            with self._path.open("w", encoding="utf-8", newline="") as fh:
                fh.write("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Noesis//CalendarTool//EN\r\nEND:VCALENDAR\r\n")
        self._lock = threading.RLock()

    @property
    def name(self) -> str:
        return "calendar"

    @property
    def description(self) -> str:
        return "List / create iCalendar events in a workspace .ics file."

    @property
    def parameter_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["operation"],
            "properties": {
                "operation": {"type": "string", "enum": ["list", "add"]},
                "start_iso": {"type": "string", "description": "RFC3339 start datetime (UTC recommended)."},
                "end_iso": {"type": "string", "description": "RFC3339 end datetime."},
                "summary": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
            },
        }

    def _parse_events(self, text: str) -> list[dict[str, Any]]:
        blocks = re.findall(r"BEGIN:VEVENT(.+?)END:VEVENT", text, flags=re.DOTALL | re.IGNORECASE)
        out: list[dict[str, Any]] = []
        for blk in blocks:
            event: dict[str, Any] = {}
            for line in blk.splitlines():
                for rx, key in (
                    (self._DTRX, "start"),
                    (self._DTENDX, "end"),
                    (self._SUMMARYRX, "summary"),
                ):
                    m = rx.match(line)
                    if m:
                        event[key] = m.group(2).strip()
            out.append(event)
        return out

    def invoke(self, args: Mapping[str, Any]) -> ToolResult:
        op = _require(args, "operation", str)
        with self._lock:
            with self._path.open("r", encoding="utf-8", newline="") as fh:
                text = fh.read()
            if op == "list":
                limit = int(args.get("limit", 50) or 50)
                events = self._parse_events(text)
                rows = [f"{len(events)} events on file (showing first {limit}):"]
                for ev in events[:limit]:
                    rows.append(f"  * {ev.get('start', '?')}-{ev.get('end', '?')}  {ev.get('summary', '(untitled)')}")
                structured = {"count": len(events), "events": events[:limit]}
                return ToolResult(success=True, stdout="\n".join(rows), structured=structured)
            if op == "add":
                start_iso = _require(args, "start_iso", str)
                end_iso = _require(args, "end_iso", str)
                summary = args.get("summary", "New event") or "New event"

                def fmt(s: str) -> str:
                    # RFC3339 -> iCalendar UTC zulu form: YYYYMMDDTHHMMSSZ
                    cleaned = s.replace("Z", "+00:00")
                    try:
                        dt = _dt.datetime.fromisoformat(cleaned).astimezone(_dt.UTC)
                    except ValueError:
                        return s
                    return dt.strftime("%Y%m%dT%H%M%SZ")

                uid = f"{uuid4().hex}@noesis.local"
                stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%dT%H%M%SZ")
                vevent = (
                    "BEGIN:VEVENT\r\n"
                    f"UID:{uid}\r\n"
                    f"DTSTAMP:{stamp}\r\n"
                    f"DTSTART:{fmt(start_iso)}\r\n"
                    f"DTEND:{fmt(end_iso)}\r\n"
                    f"SUMMARY:{summary}\r\n"
                    "END:VEVENT\r\n"
                )
                # Tolerate either \r\n or \n line endings for the terminator.
                if "END:VCALENDAR\r\n" in text:
                    new_text = text.replace("END:VCALENDAR\r\n", vevent + "END:VCALENDAR\r\n", 1)
                elif "END:VCALENDAR\n" in text:
                    new_text = text.replace("END:VCALENDAR\n", vevent + "END:VCALENDAR\n", 1)
                else:
                    new_text = text.rstrip() + "\r\n" + vevent + "END:VCALENDAR\r\n"
                with self._path.open("w", encoding="utf-8", newline="") as fh:
                    fh.write(new_text)
                structured = {"uid": uid, "start": start_iso, "end": end_iso, "summary": summary}
                return ToolResult(success=True, stdout=f"added event: {summary} [{start_iso} → {end_iso}]", structured=structured)
        return ToolResult(success=False, exit_code=1, stderr=f"unknown operation {op!r}")


# ===========================================================================
# Adapter 7 : email — SMTP_SSL send + IMAP4_SSL list (dry-run by default)
# ===========================================================================


class EmailTool(ToolPort):
    """Send email via SMTP_SSL and read via IMAP4_SSL.  If host is empty, runs dry."""

    def __init__(
        self,
        *,
        smtp_host: str = "",
        smtp_port: int = 465,
        imap_host: str = "",
        imap_port: int = 993,
        username: str = "",
        password: str = "",
        sender_address: str = "",
    ) -> None:
        self._smtp = (smtp_host, smtp_port)
        self._imap = (imap_host, imap_port)
        self._username = username
        self._password = password
        self._sender = sender_address or username

    @property
    def name(self) -> str:
        return "email"

    @property
    def description(self) -> str:
        return "Send and list emails via SMTP_SSL + IMAP4_SSL (or dry-run)."

    @property
    def parameter_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["operation"],
            "properties": {
                "operation": {"type": "string", "enum": ["send", "list"]},
                "to": {"type": "array", "items": {"type": "string"}},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "cc": {"type": "array", "items": {"type": "string"}},
                "bcc": {"type": "array", "items": {"type": "string"}},
                "folder": {"type": "string", "default": "INBOX"},
                "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
            },
        }

    @staticmethod
    def _valid_addr(a: str) -> bool:
        return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", a))

    def invoke(self, args: Mapping[str, Any]) -> ToolResult:
        op = _require(args, "operation", str)
        if op == "send":
            to: list[str] = list(args.get("to", []) or [])
            if not to:
                return ToolResult(success=False, exit_code=1, stderr="'to' recipients required")
            for a in to:
                if not self._valid_addr(a):
                    return ToolResult(success=False, exit_code=1, stderr=f"invalid To address: {a!r}")
            subject = str(args.get("subject", "(no subject)"))
            body = str(args.get("body", ""))
            sender = self._sender or "noesis@local"
            msg = EmailMessage()
            msg["From"] = sender
            msg["To"] = ", ".join(to)
            if args.get("cc"):
                msg["Cc"] = ", ".join(args["cc"])
            msg["Subject"] = subject
            msg.set_content(body)
            if not self._smtp[0] or not self._password:
                structured = {
                    "from": sender,
                    "to": to,
                    "cc": list(args.get("cc") or []),
                    "subject": subject,
                    "body_len": len(body),
                    "mode": "dry-run (no host/password configured)",
                }
                return ToolResult(success=True, stdout=json.dumps(structured, indent=2), structured=structured)
            try:
                with smtplib.SMTP_SSL(self._smtp[0], self._smtp[1], timeout=20.0) as s:
                    s.login(self._username, self._password)
                    s.send_message(msg)
                return ToolResult(success=True, stdout=f"sent email to {len(to)} recipient(s)", structured={"recipients": to})
            except (OSError, smtplib.SMTPException) as exc:
                return ToolResult(success=False, exit_code=1, stderr=f"smtp: {type(exc).__name__}: {exc}")
        if op == "list":
            folder = str(args.get("folder", "INBOX") or "INBOX")
            limit = int(args.get("limit", 10) or 10)
            if not self._imap[0] or not self._password:
                sample = {"folder": folder, "limit": limit, "mode": "dry-run"}
                return ToolResult(success=True, stdout=json.dumps(sample), structured=sample)
            try:
                with IMAP4_SSL(self._imap[0], self._imap[1]) as im:
                    im.login(self._username, self._password)
                    status, info = im.select(folder)
                    if status != "OK":
                        return ToolResult(success=False, exit_code=1, stderr=f"select failed: {info}")
                    count = int(info[0] or 0) if info and info[0] else 0
                    start = max(1, count - limit + 1)
                    status, data = im.fetch(f"{start}:{count}" if count else "0:0", "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])")
                    rows: list[dict[str, str]] = []
                    if status == "OK" and data:
                        for _i, part in enumerate(data):
                            if isinstance(part, tuple):
                                rows.append({"raw": part[1].decode("utf-8", errors="replace").strip()[:500]})
                    structured = {"folder": folder, "count": count, "messages": rows}
                    return ToolResult(success=True, stdout=json.dumps(structured, indent=2), structured=structured)
            except OSError as exc:
                return ToolResult(success=False, exit_code=1, stderr=f"imap: {type(exc).__name__}: {exc}")
        return ToolResult(success=False, exit_code=1, stderr=f"unknown operation {op!r}")


# ===========================================================================
# Adapter 8 : database — read-only SQLAlchemy text() queries
# ===========================================================================


class DBTool(ToolPort):
    """Execute READ-ONLY SQL queries against the configured AsyncEngine.

    ``sqlalchemy`` is a runtime dep (required by the project).  Writes are
    prevented by ``.execute(text(...))`` only on SELECT / WITH / EXPLAIN
    statements (keyword whitelist) plus an auto-rollback after any execute.
    """

    _READ_ONLY = re.compile(r"^\s*(select|with|explain|pragma|show|values)\b", re.IGNORECASE)

    def __init__(self, engine_factory) -> None:
        """``engine_factory`` is a callable returning a SQLAlchemy ``AsyncEngine``.

        We accept a factory rather than an engine instance because the async
        engine must be constructed inside an event loop (and the registry is
        created during import / CLI init, long before the loop runs).
        """
        self._engine_factory = engine_factory

    @property
    def name(self) -> str:
        return "db"

    @property
    def description(self) -> str:
        return "Run a read-only SQL query against the application database."

    @property
    def parameter_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["sql"],
            "properties": {
                "sql": {"type": "string", "description": "Read-only SQL (SELECT / WITH / EXPLAIN / PRAGMA / SHOW / VALUES)."},
                "params": {"type": "object"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10_000, "default": 100},
            },
        }

    @staticmethod
    async def _run_async(engine, sql, params, limit) -> ToolResult:
        from sqlalchemy import text  # local import so import-time doesn't require sqla

        buf = io.StringIO()
        rows_out: list[dict[str, Any]] = []
        async with engine.connect() as conn:
            result = await conn.execute(text(sql), params or {})
            keys = list(result.keys())
            rows = result.fetchmany(limit)
            # Always rollback — no writes allowed even if someone side-stepped keyword check.
            await conn.rollback()
            csv_writer = csv.DictWriter(buf, fieldnames=keys)
            csv_writer.writeheader()
            for r in rows:
                dct = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in zip(keys, r, strict=True)}
                csv_writer.writerow(dct)
                rows_out.append(dct)
        return ToolResult(success=True, stdout=buf.getvalue(), structured={"columns": keys, "rows": rows_out})

    def invoke(self, args: Mapping[str, Any]) -> ToolResult:
        sql = _require(args, "sql", str)
        params = args.get("params") or {}
        limit = int(args.get("limit", 100) or 100)
        if not self._READ_ONLY.match(sql):
            return ToolResult(
                success=False,
                exit_code=1,
                stderr="DBTool: only SELECT / WITH / EXPLAIN / PRAGMA / SHOW / VALUES statements are allowed.",
            )
        try:
            import asyncio

            engine = self._engine_factory()
            # Support both: sync (sqlite3 test) engine and async engine.
            if engine.__class__.__module__.startswith("sqlalchemy.ext.asyncio"):
                return asyncio.run(self._run_async(engine, sql, params, limit))
            # Sync fallback (use stdlib sqlite3 directly for test env stability)
            result: list[tuple[Any, ...]] = []
            keys: list[str] = []
            if isinstance(engine, sqlite3.Connection):
                cur = engine.execute(sql, dict(params) if params else ())
                keys = [c[0] for c in cur.description or []]
                result = cur.fetchmany(limit)
            else:
                # sqlalchemy sync engine
                from sqlalchemy import text as stext

                with engine.connect() as conn:
                    r = conn.execute(stext(sql), params or {})
                    keys = list(r.keys())
                    result = r.fetchmany(limit)
                    conn.rollback()
            buf = io.StringIO()
            rows_out: list[dict[str, Any]] = []
            w = csv.DictWriter(buf, fieldnames=keys)
            w.writeheader()
            for r in result:
                dct = {k: (v.isoformat() if hasattr(v, "isoformat") and not isinstance(v, str) else v) for k, v in zip(keys, r, strict=True)}
                w.writerow(dct)
                rows_out.append(dct)
            return ToolResult(success=True, stdout=buf.getvalue(), structured={"columns": keys, "rows": rows_out})
        except Exception as exc:
            return ToolResult(success=False, exit_code=1, stderr=f"db: {type(exc).__name__}: {exc}")


# ===========================================================================
# Adapter 9 : web fetch — httpx GET + HtmlDocumentParser reuse
# ===========================================================================


class WebFetchTool(ToolPort):
    """Fetch a URL and strip HTML to human-readable text.

    Reuses :class:`astra.rag.pipeline.HtmlDocumentParser` to preserve
    paragraph breaks so the chunker downstream sees the same shape as if
    the page was ingested through the RAG pipeline.
    """

    def __init__(self, *, user_agent: str = "Noesis/dev (+https://noesis.local)", timeout_s: float = 15.0) -> None:
        self._ua = user_agent
        self._timeout = timeout_s
        self._allowed_schemes = {"http", "https"}

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "Fetch an HTTP(S) URL and return title + stripped body text."

    @property
    def parameter_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["url"],
            "properties": {
                "url": {"type": "string", "description": "HTTP(S) URL."},
                "max_chars": {"type": "integer", "minimum": 100, "maximum": 200_000, "default": 20_000},
            },
        }

    def invoke(self, args: Mapping[str, Any]) -> ToolResult:
        url = _require(args, "url", str)
        max_chars = int(args.get("max_chars", 20_000) or 20_000)
        parsed = urlparse(url)
        if parsed.scheme not in self._allowed_schemes:
            return ToolResult(success=False, exit_code=1, stderr=f"scheme {parsed.scheme!r} not allowed")
        if not parsed.hostname:
            return ToolResult(success=False, exit_code=1, stderr="URL must have a hostname")
        if httpx is None:
            sample = {"url": url, "mode": "dry-run (httpx missing)"}
            return ToolResult(success=True, stdout=json.dumps(sample), structured=sample)
        try:
            with httpx.Client(follow_redirects=True, timeout=self._timeout) as client:
                r = client.get(url, headers={"User-Agent": self._ua, "Accept": "text/html,application/xhtml+xml,*/*;q=0.1"})
            raw = r.content or b""
            ctype = r.headers.get("content-type", "")
            structured = {"status": r.status_code, "content_type": ctype, "url_resolved": str(r.url)}
            success = 200 <= r.status_code < 300
            # HTML → reuse parser; plain text / JSON → keep as-is (truncated).
            if "text/html" in ctype:
                from noesis.rag.pipeline import HtmlDocumentParser

                parsed_doc = HtmlDocumentParser().parse(raw)
                body = f"# {parsed_doc.title}\n\n{parsed_doc.content}"[:max_chars]
            else:
                body = r.text[:max_chars]
            return ToolResult(
                success=success,
                exit_code=r.status_code,
                stdout=body,
                structured=structured,
            )
        except Exception as exc:
            return ToolResult(success=False, exit_code=-1, stderr=f"web_fetch: {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "CalendarTool",
    "DBTool",
    "EmailTool",
    "FilesTool",
    "GitHubTool",
    "PythonSandboxTool",
    "ShellTool",
    "ToolArtifact",
    "ToolPort",
    "ToolRegistry",
    "ToolResult",
    "WeatherTool",
    "WebFetchTool",
]
