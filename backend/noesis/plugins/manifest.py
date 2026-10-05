"""
PluginManifest — capability metadata for the Noesis Marketplace.

Every plugin MUST ship a ``manifest.json`` that conforms to this shape.  It
describes the plugin's identity, required capabilities, hook groups it
implements, and (for marketplace distribution) provenance/signer checksums.
Rules:
  * ``id`` must be DNS-reverse: ``com.example.foobar``.
  * ``caps_requested`` is an allow-list — the kernel will NOT mint a token
    broader than this, protecting users from exfil.
  * ``signature`` = Ed25519 signature over ``canonical_json()`` (§Zero Trust).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from .hookspec import HookGroup


class PluginManifest(BaseModel):
    """Capability-marketplace manifest."""

    model_config = ConfigDict(extra="forbid")

    # Identity
    id: str = Field(pattern=r"^[a-z0-9]([a-z0-9.-]{0,253}[a-z0-9])?$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$")
    name: str
    description: str = ""
    author: str = ""
    license: str = "MIT"
    homepage: str = ""
    repository: str = ""
    keywords: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    # Contract
    hook_groups: tuple[HookGroup, ...] = ()
    entry_point: str = ""  # importable Python module, e.g. "noesis_plugins_foobar.plugin"
    # wasm bundle path (relative to manifest), or Extism wasm module
    wasm_entry: str | None = None

    # Capabilities
    caps_requested: tuple[str, ...] = ()  # CapabilityOp values this plugin wants.
    max_tool_invocations_per_run: int | None = None
    max_memory_tokens: int | None = None

    # Security / marketplace
    signature: str | None = None
    signer_issuer: str | None = None
    sha256_manifest: str | None = None
    verified: bool = False

    # Dependencies — other plugins required to be loaded first.
    depends_on: tuple[str, ...] = ()
    conflicts_with: tuple[str, ...] = ()

    # Compatibility
    min_noesis_version: str = "0.1.0"
    max_noesis_version: str | None = None

    # Marketplace metadata (optional)
    categories: tuple[str, ...] = ()
    pricing: str | None = None
    screenshots: tuple[str, ...] = ()

    # ----------------------------------------------------- Serialisation

    @classmethod
    def from_disk(cls, path: str | Path) -> PluginManifest:
        import orjson

        raw = Path(path).read_bytes()
        return cls.model_validate(orjson.loads(raw))

    def canonical_json(self) -> bytes:
        import orjson

        # Exclude security-result fields so signatures can be re-verified.
        dump = self.model_dump(mode="json", exclude={"signature", "verified", "sha256_manifest"})
        return orjson.dumps(dump, option=orjson.OPT_SORT_KEYS)

    def compute_sha256(self) -> str:
        return hashlib.sha256(self.canonical_json()).hexdigest()

    @property
    def kind_human(self) -> str:
        return "+".join(sorted({g.value for g in self.hook_groups})) or "none"


# ---------------------------------------------------------------------------
# Pydantic v2 — resolve TYPE_CHECKING forward refs.
# PluginManifest.hook_groups references HookGroup which is imported under
# TYPE_CHECKING; rebuild here so runtime validation succeeds without needing
# callers to remember to rebuild before `model_validate` runs.
# ---------------------------------------------------------------------------
def _rebuild() -> None:  # pragma: no cover - import-time housekeeping
    from .hookspec import HookGroup as _HookGroup

    try:
        PluginManifest.model_rebuild(force=True, _types_namespace={"HookGroup": _HookGroup})
    except Exception:
        pass


_rebuild()
del _rebuild


__all__ = ["PluginManifest"]
