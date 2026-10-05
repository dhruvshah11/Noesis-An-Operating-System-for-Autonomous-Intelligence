"""
noesis.plugins — Plugin Ecosystem.

Every capability in Noesis is installable as a plugin.  This module ships:

  * 12 hook groups  (``hookspec.py``) — the extension contract.
  * PluginManager   (``manager.py``) — lifecycle, discovery, load, dispatch.
  * PluginManifest  (``manifest.py``) — capability-marketplace metadata.
  * CapabilityAPI   (``capability.py``) — WASM-safe bridge so plugins call
    syscalls through their own ``CapabilityToken`` (plugins are sandboxed).

Why not pluggy directly?
------------------------
Pluggy is great (it's what pytest uses!) — we mirror its ``@hookspec`` /
``@hookimpl`` idiom deliberately so the on-ramp is zero-learning-curve for
Python veterans.  But we extend it with:
  1. **Async hook support** (pluggy sync-only by default).
  2. **Manifest signing** (plugins can be validated before load).
  3. **Capability gating** — a plugin cannot spawn agents / invoke tools
     unless the kernel minted a token for it.
  4. **Discovery from disk** — recursive scan of ``$PWD/plugins`` +
     ``site-packages/noesis_plugins_*`` entry-points + WASM bundles.

Hook groups
-----------
  1. ``kernel``        — lifecycle (boot, shutdown).
  2. ``agent_registry``— register custom agent implementations.
  3. ``tool_registry`` — register tools (browser, slack, robotics, …).
  4. ``llm_provider``  — extend model providers (e.g. add XAI, Groq).
  5. ``model_router``  — inject custom routing logic.
  6. ``memory_store``  — register alternate MemoryZone implementations.
  7. ``vector_store``  — plug pgvector / milvus / vespa.
  8. ``rag_pipeline``  — chunking / reranking / query rewriting stages.
  9. ``security``      — prompt-injection scanners, policy engines.
 10. ``observability`` — export telemetry to OTLP / Datadog / Prometheus.
 11. ``authz``         — RBAC hook (enterprise).
 12. ``cli``           — contribute Typer subcommands.
"""

from .capability import PluginCapabilityAPI
from .hookspec import HookGroup, NoesisPluginHookSpec
from .manager import PluginLifecycleState, PluginLoadError, PluginManager
from .manifest import PluginManifest

__all__ = [
    "HookGroup",
    "NoesisPluginHookSpec",
    "PluginCapabilityAPI",
    "PluginLifecycleState",
    "PluginLoadError",
    "PluginManager",
    "PluginManifest",
]
