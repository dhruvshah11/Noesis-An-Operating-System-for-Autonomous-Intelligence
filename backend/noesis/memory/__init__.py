"""
Memory subsystem — 6-tier stores, bus orchestrator, promotion pipeline.

Public surface:
  - ``tiers``: :class:`MemoryTier` port + 6 concrete adapters + :class:`MemoryEntry` domain model.
  - ``bus``: :class:`MemoryBus` cross-tier fan-out / RRF merge.
  - ``promotion``: :class:`PromotionController` 6-tier promotion pipeline with SHA-256 provenance chain.
"""

from noesis.memory.bus import (
    ALL_TIERS,
    SCOPE_TO_TIERS,
    TIER_CONVERSATION,
    TIER_EPISODIC,
    TIER_PROJECT,
    TIER_SEMANTIC,
    TIER_USER,
    TIER_WORKING,
    MemoryBus,
    RecallHit,
)
from noesis.memory.promotion import (
    TIER_GYAN,
    TIER_INDRIYA,
    TIER_NAMES,
    TIER_PAALAK,
    TIER_SADHANA,
    TIER_SMRITI,
    TIER_YOJANA,
    GyānCorpus,
    PromotionController,
    PromotionEvent,
    PromotionReport,
    PromotionStats,
    PromotionThresholds,
)
from noesis.memory.tiers import (
    ConversationMemoryTier,
    EpisodicMemoryTier,
    MemoryCitation,
    MemoryEntry,
    MemoryTier,
    ProjectMemoryTier,
    SemanticMemoryTier,
    UserMemoryTier,
    WorkingMemoryTier,
)

__all__ = [
    "ALL_TIERS",
    "SCOPE_TO_TIERS",
    "TIER_CONVERSATION",
    "TIER_EPISODIC",
    "TIER_GYAN",
    "TIER_INDRIYA",
    "TIER_NAMES",
    "TIER_PAALAK",
    "TIER_PROJECT",
    "TIER_SADHANA",
    "TIER_SEMANTIC",
    "TIER_SMRITI",
    "TIER_USER",
    "TIER_WORKING",
    "TIER_YOJANA",
    "ConversationMemoryTier",
    "EpisodicMemoryTier",
    "GyānCorpus",
    "MemoryBus",
    "MemoryCitation",
    "MemoryEntry",
    "MemoryTier",
    "ProjectMemoryTier",
    "PromotionController",
    "PromotionEvent",
    "PromotionReport",
    "PromotionStats",
    "PromotionThresholds",
    "RecallHit",
    "SemanticMemoryTier",
    "UserMemoryTier",
    "WorkingMemoryTier",
]
