"""
PluginCapabilityAPI — WASM-safe bridge back into the kernel.

Every plugin receives a ``caps: PluginCapabilityAPI`` instance; it is the
*only* way a plugin can do IO.  We expose 6 methods — a tiny surface area:

  1. ``syscall(call, payload)``  — invoke a kernel syscall (§kernel.SysCall).
  2. ``publish_event(topic, payload)`` — fire an event on the kernel bus.
  3. ``trace(name, payload)``    — emit an OTel trace span.
  4. ``spawn_agent(spec)``       — ask the kernel to start a sub-agent (requires SPAWN cap).
  5. ``tool_invoke(name, args)`` — call a registered tool.
  6. ``clock()``                 — deterministic wall-clock (test-friendly).

WASM / Extism plugins call these via the ABI:
    ``plugin_call(i64 handle, const char* method, const char* json_args) -> char* json_result``.
The C-bindings are a thin wrapper around the 6 methods here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from ..kernel import AgentHandle, Kernel, SysCall, SysCallResult

if TYPE_CHECKING:  # pragma: no cover
    from ..kernel.capabilities import CapabilityToken


@dataclass(slots=True)
class PluginCapabilityAPI:
    """Sandboxed API bridge — one instance per loaded plugin."""

    kernel: Kernel
    plugin_id: str
    plugin_agent_handle: AgentHandle
    token: CapabilityToken
    extra: dict[str, Any] = field(default_factory=dict)

    # ----------------------------------------------------------- Syscalls
    async def syscall(self, call: SysCall | str, payload: dict[str, Any] | None = None) -> SysCallResult:
        call_e = SysCall(call) if isinstance(call, str) else call
        return await self.kernel.syscall(self.plugin_agent_handle, call_e, payload)

    # ----------------------------------------------------------- Events
    async def publish_event(self, topic: str, payload: dict[str, Any]) -> None:
        res = await self.syscall(SysCall.BROADCAST_EVENT, {"topic": topic, "payload": dict(payload)})
        if not res.success:
            raise RuntimeError(f"Plugin {self.plugin_id} failed to publish {topic}: {res.error}")

    # ----------------------------------------------------------- Observability
    async def trace(self, name: str, payload: dict[str, Any] | None = None) -> None:
        await self.syscall(SysCall.TRACE_EVENT, {"name": name, "payload": dict(payload or {})})

    # ----------------------------------------------------------- Agent spawn
    async def spawn_agent(self, spec: dict[str, Any]) -> dict[str, Any]:
        res = await self.syscall(SysCall.SPAWN_AGENT, dict(spec))
        if not res.success:
            raise RuntimeError(f"Plugin {self.plugin_id} spawn_agent failed: {res.error}")
        return res.payload or {}

    # ----------------------------------------------------------- Tools
    async def tool_invoke(self, name: str, args: dict[str, Any] | None = None) -> Any:
        res = await self.syscall(SysCall.TOOL_INVOKE, {"tool": name, "args": dict(args or {})})
        if not res.success:
            raise RuntimeError(f"Plugin {self.plugin_id} tool_invoke({name}) failed: {res.error}")
        return (res.payload or {}).get("result")

    # ----------------------------------------------------------- Clock
    def clock(self) -> datetime:
        return datetime.now(UTC)

    # Convenience for logging helpers used widely
    def trace_id(self) -> str:
        return uuid4().hex


__all__ = ["PluginCapabilityAPI"]
