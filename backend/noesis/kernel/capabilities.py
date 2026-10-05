"""
Capability-based security for the Noesis Kernel.

Design choices (with trade-offs):
--------------------------------
  * MAC (Mandatory Access Control) instead of ACLs.  Every agent is issued a
    single :class:`CapabilityToken` at spawn time; the kernel *never* reads
    that token (agents are opaque).  The token is an immutable, opaque
    identifier — the authoritative capability table lives in the kernel.
    This prevents confused-deputy attacks where Agent A asks Agent B to
    perform a privileged action on its behalf.

  * Capabilities are *fine-grained*.  ``TOOL_INVOKE:search:*`` is separate
    from ``TOOL_INVOKE:shell:*`` and from ``MEMORY_WRITE:semantic``.

  * ``allow_all`` exists but is only usable by the kernel's own supervisor
    thread.  We refuse to mint it for any user-spawned agent.

Trade-offs:
  - ➕ Impossible for plugins to elevate privilege unless kernel explicitly grants.
  - ➕ Debug-friendly: every denied syscall produces a structured log line with
    the exact missing (op, target) pair.
  - ➖ Spawning an agent requires pre-declaring its capability set (small
    ergonomic hit; worth the security).
  - ➖ First version does not do delegated / delegable capabilities (that's a
    SH-2 workstream; keep surface area small for v1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid4


class CapabilityOp(StrEnum):
    """Every capability a token can carry."""

    # --- System-level
    SPAWN_AGENT = "spawn_agent"
    KILL_AGENT = "kill_agent"
    ADMIN = "admin"

    # --- Memory
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    MEMORY_PRUNE = "memory_prune"

    # --- Tool execution
    TOOL_INVOKE = "tool_invoke"
    TOOL_REGISTER = "tool_register"

    # --- Knowledge
    RAG_SEARCH = "rag_search"
    RAG_INGEST = "rag_ingest"

    # --- Communication
    SEND_MESSAGE = "send_message"
    BROADCAST_EVENT = "broadcast_event"

    # --- Model
    MODEL_INFERENCE = "model_inference"

    # --- Workspace / enterprise
    WORKSPACE_READ = "workspace_read"
    WORKSPACE_WRITE = "workspace_write"


@dataclass(frozen=True, slots=True)
class Capability:
    """One allowed (operation, target) pair.  ``target`` is glob-matched."""

    op: CapabilityOp
    target: str = "*"

    def allows(self, op: CapabilityOp, target: str) -> bool:
        if self.op != op:
            return False
        if self.target == "*":
            return True
        # Case-insensitive glob match (simple '*' wildcard semantics only).
        parts = self.target.split("*")
        if len(parts) == 1:
            return self.target.lower() == target.lower()
        # parts = [prefix, middle0, ..., suffix] — walk them in order.
        hay = target.lower()
        idx = 0
        for n, part in enumerate(parts):
            if not part:
                continue
            found = hay.find(part.lower(), idx)
            if found < 0:
                return False
            if n == 0 and found != 0:
                return False
            idx = found + len(part)
        tail = parts[-1]
        return not (tail and not target.lower().endswith(tail.lower()))


@dataclass(frozen=True, slots=True)
class CapabilityToken:
    """An opaque, unforgeable token returned by ``Kernel.spawn_agent``.

    The kernel never serialises the full capability set — only the ``id`` is
    ever passed over the UAP wire.  Plugins must present the original token
    to make syscalls (or have the kernel mint a sub-token via
    ``Kernel.mint_subtoken`` for fan-out).
    """

    id: UUID = field(default_factory=uuid4)
    owner_agent_id: str = ""
    workspace_id: str | None = None


class PermissionDenied(Exception):
    """Raised by the kernel when a syscall targets a (op,target) the token lacks.

    Structured so observability dashboards can top-N "most denied agents".
    """

    def __init__(
        self,
        *,
        token_id: UUID,
        op: CapabilityOp,
        target: str,
        details: str = "",
    ) -> None:
        super().__init__(f"PermDenied[token={token_id} op={op.value} target={target}]: {details or 'capability not present'}")
        self.token_id = token_id
        self.op = op
        self.target = target
        self.details = details


def allow_all() -> list[Capability]:
    """Supervisor-only capability list.  DO NOT hand to user agents."""
    return [Capability(op=op) for op in CapabilityOp]
