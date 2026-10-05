"""
12 hook groups + 32 hookspec signatures — the complete extension surface.

Mirror of pluggy's ``@hookspec`` decorator semantics, implemented as plain
dataclasses so non-Python (WASM / Extism) plugins can match the names with
string equality.  Each hookspec is declared *once* here; plugins implement
using either:

   (a) class inheritance from :class:`NoesisPluginHookSpec` (Python)
   (b) a `hooks: list[str]` in their manifest (WASM / external plugins)
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Awaitable, Callable

    from noesis.kernel import AgentContext, Kernel
    from noesis.kernel.capabilities import Capability
    from noesis.kernel.model_router import ModelProfile, ModelSchedulingDecision, RoutingConstraint
    from noesis.types import ChatMessage, ProviderResponse

    from .manifest import PluginManifest


class HookGroup(StrEnum):
    """Twelve hook groups — a plugin declares which groups it implements."""

    KERNEL = "kernel"
    AGENT_REGISTRY = "agent_registry"
    TOOL_REGISTRY = "tool_registry"
    LLM_PROVIDER = "llm_provider"
    MODEL_ROUTER = "model_router"
    MEMORY_STORE = "memory_store"
    VECTOR_STORE = "vector_store"
    RAG_PIPELINE = "rag_pipeline"
    SECURITY = "security"
    OBSERVABILITY = "observability"
    AUTHZ = "authz"
    CLI = "cli"


@runtime_checkable
class NoesisPluginHookSpec(Protocol):
    """Protocol listing every hook — plugins override any subset.

    Every hook is optional.  Hook signatures are deliberately small and
    stable: we never remove an argument, only append ``**_kw`` for growth.
    """

    # ---- kernel (lifecycle) ------------------------------------------------
    async def on_kernel_boot(self, kernel: Kernel, manifest: PluginManifest, **_kw: Any) -> None: ...
    async def on_kernel_shutdown(self, kernel: Kernel, manifest: PluginManifest, **_kw: Any) -> None: ...

    # ---- agent_registry ----------------------------------------------------
    async def register_agents(
        self,
        register: Callable[[str, type, tuple[Capability, ...]], Awaitable[None]],
        **_kw: Any,
    ) -> None: ...

    # ---- tool_registry -----------------------------------------------------
    async def register_tools(
        self,
        register: Callable[[str, Callable[..., Awaitable[Any]], str | None], Awaitable[None]],
        **_kw: Any,
    ) -> None: ...

    # ---- llm_provider ------------------------------------------------------
    async def register_llm_providers(
        self,
        register: Callable[[str, type], Awaitable[None]],
        **_kw: Any,
    ) -> None: ...

    async def chat_completion_interceptor(
        self,
        provider_id: str,
        messages: list[ChatMessage],
        *,
        tools: list[dict] | None,
        next_handler: Callable[..., Awaitable[ProviderResponse]],
        **_kw: Any,
    ) -> ProviderResponse: ...

    # ---- model_router ------------------------------------------------------
    async def register_model_profiles(
        self,
        register: Callable[[ModelProfile], Awaitable[None]],
        **_kw: Any,
    ) -> None: ...
    async def adjust_routing_scores(
        self,
        decision: ModelSchedulingDecision,
        constraint: RoutingConstraint,
        **_kw: Any,
    ) -> ModelSchedulingDecision: ...

    # ---- memory_store ------------------------------------------------------
    async def memory_get(self, zone: str, key: str, **_kw: Any) -> tuple[bool, Any]: ...
    async def memory_put(self, zone: str, key: str, value: Any, ttl_s: int | None, **_kw: Any) -> bool: ...
    async def memory_search(self, zone: str, query_embedding: list[float], top_k: int, **_kw: Any) -> list[Any]: ...

    # ---- vector_store ------------------------------------------------------
    async def vector_upsert(
        self, collection: str, ids: list[str], embeddings: list[list[float]], payloads: list[dict] | None, **_kw: Any
    ) -> None: ...
    async def vector_search(self, collection: str, query_embedding: list[float], top_k: int, **_kw: Any) -> list[dict]: ...

    # ---- rag_pipeline ------------------------------------------------------
    async def rag_chunk_document(self, raw: bytes, metadata: dict, **_kw: Any) -> list[tuple[str, dict]]: ...
    async def rag_rewrite_query(self, query: str, **_kw: Any) -> str: ...
    async def rag_rerank(self, query: str, candidates: list[dict], top_k: int, **_kw: Any) -> list[dict]: ...
    async def rag_cite_check(self, answer: str, context: list[dict], **_kw: Any) -> list[dict]: ...

    # ---- security ----------------------------------------------------------
    async def detect_prompt_injection(self, prompt: str, **_kw: Any) -> tuple[bool, float, list[str]]: ...
    async def policy_evaluate(
        self,
        actor: AgentContext,
        action: str,
        resource: str,
        **_kw: Any,
    ) -> tuple[bool, str]: ...
    async def sandbox_command(self, command: list[str], **_kw: Any) -> tuple[int, bytes, bytes]: ...

    # ---- observability -----------------------------------------------------
    async def span_export(self, spans: list[dict], **_kw: Any) -> None: ...
    async def metric_export(self, metrics: list[dict], **_kw: Any) -> None: ...
    async def uap_message_log(self, message: dict, **_kw: Any) -> None: ...

    # ---- authz -------------------------------------------------------------
    async def authz_check(
        self,
        workspace_id: str | None,
        user_id: str | None,
        action: str,
        resource: str,
        **_kw: Any,
    ) -> bool: ...

    # ---- cli ---------------------------------------------------------------
    def register_cli_commands(
        self,
        app: Any,  # typer.Typer
        kernel_factory: Callable[[], Awaitable[Kernel]],
        **_kw: Any,
    ) -> None: ...


# Alias — pluggy-style naming.
hookspec = NoesisPluginHookSpec

__all__ = ["HookGroup", "NoesisPluginHookSpec", "hookspec"]
