"""
PluginManager — discovery, lifecycle, dispatch.

Lifecycle states (analogous to systemd units):
  LOADED → VERIFIED → REGISTERED → HOOKS_RUNNING → SHUTTING_DOWN → UNLOADED
                   ↘ FAILED

Plug-ins can be loaded from 3 sources (in priority order):
  1. ``PluginManager.register_instance()`` — Python object (in-process, fastest).
  2. ``PluginManager.load_from_manifest(manifest)`` — imports ``entry_point``.
  3. ``PluginManager.discover(dirs=[…])`` — finds ``manifest.json``s under directories + scans entry points group ``noesis.plugins.v1``.

Dispatch for async hooks uses a gather-all loop with a per-hook timeout.
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.metadata as ilm
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from noesis.logging import get_logger

from ..kernel.capabilities import Capability, CapabilityOp
from .capability import PluginCapabilityAPI
from .manifest import PluginManifest

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Awaitable, Callable

    from ..kernel import AgentHandle, Kernel, capabilities
    from .hookspec import NoesisPluginHookSpec

log = get_logger(__name__)

ENTRY_POINT_GROUP = "noesis.plugins.v1"


class PluginLifecycleState(StrEnum):
    LOADED = "loaded"
    VERIFIED = "verified"
    REGISTERED = "registered"
    HOOKS_RUNNING = "hooks_running"
    SHUTTING_DOWN = "shutting_down"
    UNLOADED = "unloaded"
    FAILED = "failed"


class PluginLoadError(RuntimeError):
    def __init__(self, plugin_id: str, reason: str, cause: Exception | None = None) -> None:
        super().__init__(f"Plugin {plugin_id!r}: {reason}")
        self.plugin_id = plugin_id
        self.reason = reason
        self.__cause__ = cause


@dataclass(slots=True)
class _PluginRecord:
    manifest: PluginManifest
    instance: NoesisPluginHookSpec | None
    handle: AgentHandle
    state: PluginLifecycleState = PluginLifecycleState.LOADED
    caps_api: PluginCapabilityAPI | None = None
    failure_reason: str | None = None


class PluginManager:
    """The Noesis plugin runtime."""

    def __init__(self, kernel: Kernel, *, per_hook_timeout_s: float = 30.0) -> None:
        self._kernel = kernel
        self._plugins: dict[str, _PluginRecord] = {}
        self._per_hook_timeout_s = per_hook_timeout_s
        self._dispatch_lock = asyncio.Lock()

    # ----------------------------------------------------------------------- Query

    def __contains__(self, plugin_id: str) -> bool:
        return plugin_id in self._plugins

    def state_of(self, plugin_id: str) -> PluginLifecycleState:
        if plugin_id not in self._plugins:
            raise KeyError(plugin_id)
        return self._plugins[plugin_id].state

    def list_plugins(self) -> list[tuple[str, PluginLifecycleState, PluginManifest]]:
        return [(rid, rec.state, rec.manifest) for rid, rec in sorted(self._plugins.items())]

    # ----------------------------------------------------------------------- Registration

    def register_instance(
        self,
        plugin: NoesisPluginHookSpec,
        manifest: PluginManifest,
    ) -> AgentHandle:
        """Register an in-process Python object as a plugin."""
        self._check_conflicts(manifest)
        token, handle = self._allocate_plugin_identity(manifest)
        rec = _PluginRecord(manifest=manifest, instance=plugin, handle=handle)
        rec.caps_api = PluginCapabilityAPI(kernel=self._kernel, plugin_id=manifest.id, plugin_agent_handle=handle, token=token)
        rec.state = PluginLifecycleState.REGISTERED
        self._plugins[manifest.id] = rec
        log.info("plugins.registered", id=manifest.id, version=manifest.version, hooks=manifest.kind_human)
        return handle

    async def load_from_manifest(self, manifest: PluginManifest) -> AgentHandle:
        """Load a plugin by manifest — uses manifest.entry_point import path."""
        self._check_conflicts(manifest)
        if manifest.sha256_manifest and manifest.compute_sha256() != manifest.sha256_manifest:
            raise PluginLoadError(manifest.id, "sha256_manifest mismatch")
        try:
            module = importlib.import_module(manifest.entry_point) if manifest.entry_point else None
            plugin_instance = getattr(module, "PLUGIN", None) if module else None
        except Exception as exc:
            raise PluginLoadError(manifest.id, f"import failed: {exc}", exc) from exc
        if plugin_instance is None:
            # Fallback: call create(caps) if it exists.
            factory = getattr(module, "create_plugin", None) if module else None
            if factory is None:
                raise PluginLoadError(manifest.id, "no PLUGIN attribute / create_plugin() factory")
            token, handle = self._allocate_plugin_identity(manifest)
            caps_api = PluginCapabilityAPI(kernel=self._kernel, plugin_id=manifest.id, plugin_agent_handle=handle, token=token)
            plugin_instance = await self._call_safely(factory, caps_api)
            rec = _PluginRecord(manifest=manifest, instance=plugin_instance, handle=handle, caps_api=caps_api, state=PluginLifecycleState.REGISTERED)
        else:
            token, handle = self._allocate_plugin_identity(manifest)
            caps_api = PluginCapabilityAPI(kernel=self._kernel, plugin_id=manifest.id, plugin_agent_handle=handle, token=token)
            rec = _PluginRecord(manifest=manifest, instance=plugin_instance, handle=handle, caps_api=caps_api, state=PluginLifecycleState.REGISTERED)
        self._plugins[manifest.id] = rec
        log.info("plugins.loaded", id=manifest.id, version=manifest.version)
        return handle

    async def discover(
        self,
        dirs: list[str | Path] | None = None,
        *,
        include_entry_points: bool = True,
    ) -> list[PluginManifest]:
        """Scan directories + Python entry points; return manifests of loaded plugins."""
        loaded: list[PluginManifest] = []
        if dirs:
            for d in dirs:
                for manifest_path in Path(d).rglob("manifest.json"):
                    try:
                        m = PluginManifest.from_disk(manifest_path)
                    except Exception as exc:
                        log.warning("plugins.discover_bad_manifest", path=str(manifest_path), exc=str(exc))
                        continue
                    if m.id in self._plugins:
                        continue
                    try:
                        await self.load_from_manifest(m)
                    except PluginLoadError as exc:
                        log.warning("plugins.discover_load_failed", id=m.id, exc=str(exc))
                        continue
                    loaded.append(m)
        if include_entry_points:
            for ep in ilm.entry_points(group=ENTRY_POINT_GROUP):
                try:
                    entry = ep.load()
                except Exception as exc:
                    log.warning("plugins.entrypoint_load_fail", ep=ep.name, exc=str(exc))
                    continue
                if callable(entry):
                    manifest = entry() if not _iscoroutine(entry) else None
                    if isinstance(manifest, PluginManifest) and manifest.id not in self._plugins:
                        await self.load_from_manifest(manifest)
                        loaded.append(manifest)
        return loaded

    # ----------------------------------------------------------------------- Lifecycle

    async def boot_all(self) -> None:
        for rid, rec in list(self._plugins.items()):
            if rec.state != PluginLifecycleState.REGISTERED:
                continue
            try:
                await self.call_hook("on_kernel_boot", self._kernel, rec.manifest)
                rec.state = PluginLifecycleState.HOOKS_RUNNING
            except Exception as exc:
                rec.state = PluginLifecycleState.FAILED
                rec.failure_reason = str(exc)
                log.error("plugins.boot_failed", id=rid, exc=str(exc))

    async def shutdown_all(self) -> None:
        for rid, rec in list(self._plugins.items()):
            if rec.state in {PluginLifecycleState.HOOKS_RUNNING, PluginLifecycleState.REGISTERED}:
                rec.state = PluginLifecycleState.SHUTTING_DOWN
                try:
                    await self.call_hook("on_kernel_shutdown", self._kernel, rec.manifest)
                except Exception as exc:
                    log.warning("plugins.shutdown_failed", id=rid, exc=str(exc))
                rec.state = PluginLifecycleState.UNLOADED
        # Leave entries in place for introspection.

    async def unload(self, plugin_id: str, *, remove_from_registry: bool = False) -> bool:
        """Unload a single plugin, calling shutdown hooks if still running.

        Returns True if a plugin was actually unloaded; False if it wasn't
        present.  ``remove_from_registry=True`` also deletes the record from
        ``_plugins`` so subsequent ``list_plugins`` calls won't include it
        (default False retains the record in ``UNLOADED`` state for audit).
        """
        rec = self._plugins.get(plugin_id)
        if rec is None:
            return False
        if rec.state in {PluginLifecycleState.HOOKS_RUNNING, PluginLifecycleState.REGISTERED}:
            rec.state = PluginLifecycleState.SHUTTING_DOWN
            try:
                if rec.instance is not None:
                    fn = getattr(rec.instance, "on_kernel_shutdown", None)
                    if callable(fn):
                        await self._call_with_timeout(fn, self._kernel, rec.manifest)
            except Exception as exc:  # pragma: no cover - best effort
                log.warning("plugins.unload_hook_failed", id=plugin_id, exc=str(exc))
        rec.state = PluginLifecycleState.UNLOADED
        log.info("plugins.unloaded", id=plugin_id)
        if remove_from_registry:
            del self._plugins[plugin_id]
        return True

    # ------------------------------------------------------------------- Verify

    @staticmethod
    def verify_manifest_directory(path: str | Path) -> list[tuple[Path, PluginManifest | None, str]]:
        """Static verifier: rglob every ``manifest.json`` in ``path`` and validate.

        Returns a list of ``(manifest_path, parsed_manifest_or_None, status_string)``
        tuples: ``status_string`` ∈ ``{ok, no_manifest, invalid:<reason>,
        missing_entry_point, sha_mismatch}``.

        The CLI ``noesis plugins verify`` command uses this for sysadmins to
        validate plugins directories **before** loading them into a kernel.
        """
        target = Path(path)
        results: list[tuple[Path, PluginManifest | None, str]] = []
        if not target.exists():
            results.append((target, None, "invalid:directory_does_not_exist"))
            return results
        manifests = sorted(target.rglob("manifest.json"))
        if not manifests:
            results.append((target, None, "no_manifest_found"))
            return results
        for mp in manifests:
            try:
                manifest = PluginManifest.from_disk(mp)
            except Exception as exc:
                results.append((mp, None, f"invalid:parse:{type(exc).__name__}:{exc}"))
                continue
            status_bits: list[str] = []
            if manifest.sha256_manifest and manifest.compute_sha256() != manifest.sha256_manifest:
                status_bits.append("sha_mismatch")
            if manifest.entry_point:
                try:
                    import importlib.util

                    spec = importlib.util.find_spec(manifest.entry_point.split(".", 1)[0])
                    if spec is None:
                        status_bits.append("missing_entry_point_module")
                except (ModuleNotFoundError, ValueError):
                    status_bits.append("missing_entry_point_module")
            if status_bits:
                results.append((mp, manifest, ",".join(status_bits)))
            else:
                results.append((mp, manifest, "ok"))
        return results

    # ----------------------------------------------------------------------- Dispatch

    async def call_hook(self, hook_name: str, *args: Any, **kwargs: Any) -> list[Any]:
        """Dispatch a hook to every plugin that implements it.

        Returns a list of non-None return values (all plugins).  Failures are
        logged but never propagated — a single bad plugin can't crash the
        kernel.
        """
        results: list[Any] = []
        async with self._dispatch_lock:
            coros: list[Awaitable[Any]] = []
            for rec in self._plugins.values():
                if rec.instance is None:
                    continue
                fn = getattr(rec.instance, hook_name, None)
                if not callable(fn):
                    continue
                coros.append(self._call_with_timeout(fn, *args, **kwargs))
            if not coros:
                return []
            gathered = await asyncio.gather(*coros, return_exceptions=True)
            for rid, outcome in zip(self._plugins, gathered, strict=False):
                if isinstance(outcome, Exception):
                    log.warning("plugins.hook_failed", id=rid, hook=hook_name, exc=str(outcome))
                elif outcome is not None:
                    results.append(outcome)
        return results

    # ----------------------------------------------------------------------- Internals

    def _check_conflicts(self, manifest: PluginManifest) -> None:
        for existing_id, _existing in self._plugins.items():
            if any(c in manifest.conflicts_with for c in (existing_id, manifest.id)):
                raise PluginLoadError(manifest.id, f"conflicts with loaded plugin {existing_id}")
            if any(missing_id not in self._plugins for missing_id in manifest.depends_on):
                raise PluginLoadError(manifest.id, f"missing required dependencies {[d for d in manifest.depends_on if d not in self._plugins]}")

    def _allocate_plugin_identity(self, manifest: PluginManifest) -> tuple[capabilities.CapabilityToken, AgentHandle]:
        requested_ops: list[CapabilityOp] = []
        for op_val in manifest.caps_requested:
            try:
                requested_ops.append(CapabilityOp(op_val))
            except ValueError:
                log.warning("plugins.unknown_cap", id=manifest.id, cap=op_val)
        caps = [Capability(op=op) for op in requested_ops]
        run_id = uuid4()
        handle = self._kernel.spawn_agent(
            agent_id=f"plugin::{manifest.id}::{manifest.version}",
            agent_type="plugin",
            run_id=run_id,
            capabilities=caps,
            workspace_id=None,
        )
        token = self._kernel._agents[(handle.agent_id, handle.run_id)].token
        return token, handle

    async def _call_with_timeout(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        coro = fn(*args, **kwargs)
        if not _iscoroutine(coro):
            return coro
        try:
            return await asyncio.wait_for(coro, timeout=self._per_hook_timeout_s)
        except TimeoutError as exc:
            raise TimeoutError(f"Plugin hook {getattr(fn, '__name__', repr(fn))} timed out") from exc

    async def _call_safely(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        coro = fn(*args, **kwargs)
        if _iscoroutine(coro):
            coro = await coro
        return coro


def _iscoroutine(o: object) -> bool:
    import inspect

    return inspect.iscoroutinefunction(o) or inspect.iscoroutine(o)


__all__ = [
    "ENTRY_POINT_GROUP",
    "PluginLifecycleState",
    "PluginLoadError",
    "PluginManager",
]
