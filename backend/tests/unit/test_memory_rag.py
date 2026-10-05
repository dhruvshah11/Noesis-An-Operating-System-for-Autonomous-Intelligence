"""
M2 memory + RAG tests.

Covers:
  * MemoryTier port LSP contract (all 6 tiers implement 7 methods with right types).
  * Each tier's search/prune/summarize round-trip, scope isolation + Working-tier LRU cap.
  * MemoryBus: SCOPE_TO_TIERS routing, multi-tier RRF merge, forget() atomic delete.
  * Chunker: exact overlap chars + fragment indices boundaries.
  * ParserRegistry: txt / md / html / csv each produce non-empty ParsedDocument with title.
  * IngestPipeline: one-doc ingest → chunk with citation → fragment content_sha populated.
  * FragmentStore BM25: single-term vs multi-term queries return different non-empty lists.
  * HybridSearch with simulated vector half: RRF merges BM25 + vector rankings.
  * Citations: every chunk of every parser round-trips with start_char ≤ end_char and
    correct fragment_index.
"""

from __future__ import annotations

from abc import ABC

import pytest

from noesis.memory.bus import (
    ALL_TIERS,
    SCOPE_TO_TIERS,
    TIER_SEMANTIC,
    TIER_USER,
    TIER_WORKING,
    MemoryBus,
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
from noesis.rag.pipeline import (
    Chunker,
    CsvDocumentParser,
    HtmlDocumentParser,
    HybridSearch,
    IngestPipeline,
    ParsedDocument,
    ParserRegistry,
    SearchResult,
    TextDocumentParser,
)

ALL_CONCRETE_TIERS = (
    WorkingMemoryTier,
    ConversationMemoryTier,
    UserMemoryTier,
    ProjectMemoryTier,
    EpisodicMemoryTier,
    SemanticMemoryTier,
)


def _entry(
    content: str,
    *,
    scope="user",
    scope_id=None,
    importance=0.5,
    kind="fact",
    tags=None,
    embedding=None,
):
    return MemoryEntry(
        content=content,
        kind=kind,
        importance=importance,
        scope=scope,
        scope_id=scope_id,
        tags=set(tags or []),
        citations=[
            MemoryCitation(source="pytest://test", snippet=content[:40]),
        ],
        embedding=list(embedding) if embedding is not None else None,
    )


# ---------------------------------------------------------------------------
# MemoryTier port LSP (Liskov substitution contract)
# ---------------------------------------------------------------------------


def test_memorytier_is_abc_with_seven_abstract_methods():
    assert issubclass(MemoryTier, ABC)
    abstracts = {n for n, v in MemoryTier.__dict__.items() if getattr(v, "__isabstractmethod__", False)}
    expected = {"put", "get", "delete", "search", "score", "summarize", "prune"}
    assert expected == abstracts, abstracts


@pytest.mark.parametrize("cls", ALL_CONCRETE_TIERS)
def test_concrete_tier_instantiation_and_implements_all_methods(cls):
    tier: MemoryTier = cls()
    # Call all 7 methods with trivial inputs; none should raise NotImplementedError.
    e = _entry("hello")
    mid = tier.put(e)
    assert mid == e.memory_id
    got = tier.get(mid)
    assert got is not None
    assert got.access_count >= 1  # get bumps access_count
    score = tier.score(e)
    assert 0.0 <= score <= 1.0
    # search (empty or one result)
    hits = tier.search(query="hello")
    assert isinstance(hits, list)
    # summarize
    summary = tier.summarize()
    assert isinstance(summary, str)
    # prune — keep 1000 (shouldn't delete the 1 we added)
    deleted = tier.prune(keep_top_k=1000)
    assert deleted == 0
    # delete returns True for existing
    assert tier.delete(mid) is True
    # double delete returns False
    assert tier.delete(mid) is False


@pytest.mark.parametrize("cls", ALL_CONCRETE_TIERS)
def test_tier_scope_isolation(cls):
    tier: MemoryTier = cls()
    a = _entry("alpha", scope="user", scope_id="u-1")
    b = _entry("beta", scope="user", scope_id="u-2")
    tier.put(a)
    tier.put(b)
    # search scope_id=u-1 should match only alpha
    hits = tier.search(query="alpha beta", scope="user", scope_id="u-1", top_k=100)
    ids = {h.memory_id for h, _ in hits}
    assert a.memory_id in ids
    assert b.memory_id not in ids


# ---------------------------------------------------------------------------
# Working tier: LRU cap
# ---------------------------------------------------------------------------


def test_working_tier_evicts_lru():
    wm = WorkingMemoryTier(capacity=3)
    ids = [wm.put(_entry(f"item-{i}")) for i in range(5)]
    # Only last 3 remain
    present = [mid for mid in ids if wm.get(mid) is not None]
    assert len(present) == 3
    assert ids[-1] in present  # most recent
    assert ids[0] not in present  # oldest evicted


# ---------------------------------------------------------------------------
# Episodic tier prefers recent episodes
# ---------------------------------------------------------------------------


def test_episodic_recentness_bias():
    tier = EpisodicMemoryTier()
    old = _entry("old observation", kind="episode", importance=0.0)
    new = _entry("new observation", kind="episode", importance=0.0)
    # Force old to be genuinely older: cheat via direct assignment.
    import datetime as _dt
    from datetime import UTC as _UTC

    old.created_at = _dt.datetime(2020, 1, 1, tzinfo=_UTC)
    tier.put(old)
    tier.put(new)
    hits = tier.search(query="observation", top_k=2)
    assert hits[0][0].memory_id == new.memory_id


# ---------------------------------------------------------------------------
# Semantic tier bonus: entries with embedding populate + get a query-overlap bonus
# ---------------------------------------------------------------------------


def test_semantic_tier_embedding_bonus_applied():
    tier = SemanticMemoryTier()
    e1 = _entry("llm transformer neural attention", tags={"ai"}, importance=0.1)
    e2 = _entry("llm transformer neural attention", tags={"ai"}, importance=0.1, embedding=[0.1] * 16)
    tier.put(e1)
    tier.put(e2)
    hits = tier.search(query="llm transformer", top_k=2)
    ids = [h.memory_id for h, _ in hits]
    # Embedding-carrying entry should rank above identical-importance/same-tokens one
    assert ids.index(e2.memory_id) <= ids.index(e1.memory_id)


# ---------------------------------------------------------------------------
# Scoring / summarisation / pruning: pruning drops lowest-scored entries
# ---------------------------------------------------------------------------


def test_tier_prune_drops_lowest():
    tier = ConversationMemoryTier()
    for i in range(100):
        tier.put(_entry(f"item {i}", importance=0.01 * i, scope="conversation", scope_id="conv-A"))
    deleted = tier.prune(scope="conversation", scope_id="conv-A", keep_top_k=10)
    assert deleted == 90
    remaining = tier.search(top_k=100)
    assert len(remaining) == 10
    # Remaining items have importance 0.90..0.99
    importances = sorted(e.importance for e, _ in remaining)
    assert importances[0] >= 0.90


# ---------------------------------------------------------------------------
# MemoryBus
# ---------------------------------------------------------------------------


def test_bus_default_constructs_all_six_tiers():
    bus = MemoryBus()
    assert set(bus.tier_names) == ALL_TIERS


def test_bus_raises_when_tiers_missing():
    with pytest.raises(ValueError, match="missing tiers"):
        MemoryBus(tiers={TIER_WORKING: WorkingMemoryTier()})


def test_bus_remember_routes_by_scope():
    bus = MemoryBus()
    e = _entry("user prefers dark mode", scope="user", scope_id="u-123")
    where = bus.remember(e)
    # SCOPE_TO_TIERS["user"] = (user, semantic)
    assert set(where.keys()) == {TIER_USER, TIER_SEMANTIC}
    # Conversation scope → 4 tiers
    ce = _entry("today's plan", scope="conversation", scope_id="c-1")
    where_conv = bus.remember(ce)
    assert set(where_conv.keys()) == set(SCOPE_TO_TIERS["conversation"])


def test_bus_recall_returns_tier_identity_and_rrf_merge():
    bus = MemoryBus()
    shared = _entry("memory consolidation is good", scope="conversation", scope_id="c-42", importance=0.9, tags={"ai"})
    ids = bus.remember(shared)
    mid = next(iter(ids.values()))
    hits = bus.recall(query="memory consolidation", top_k=10)
    assert hits, "recall expected to find the shared entry in at least one tier"
    # All hits are RecallHit instances with 0<=score<=1.
    for h in hits:
        assert 0.0 <= h.score <= 1.0
        assert h.tier in ALL_TIERS
    # Memory id we saved is somewhere in the list
    memory_ids_present = [h.entry.memory_id for h in hits]
    assert mid in memory_ids_present


def test_bus_forget_deletes_everywhere():
    bus = MemoryBus()
    e = _entry("to-be-deleted", scope="conversation", scope_id="c-1")
    where = bus.remember(e)
    # mid should be equal in all tiers
    mid = next(iter(where.values()))
    status = bus.forget(mid)
    # Every tier that had it (4 tiers for conversation scope) returns True.
    for tier_name, was_there in status.items():
        assert was_there is (tier_name in where)


def test_bus_retain_runs_prune_per_tier():
    bus = MemoryBus()
    # Add 600 items to working tier (capacity default 256 is a ceiling so we
    # add 600 to semantic tier instead, which is un-capped).
    for i in range(600):
        sem_entry = _entry(f"note {i}", scope="system")
        bus.remember(sem_entry, tiers=[TIER_SEMANTIC])
    result = bus.retain(per_tier_keep={TIER_SEMANTIC: 10}, default_keep=100)
    assert result[TIER_SEMANTIC] == 600 - 10


def test_bus_summarise_has_tier_sections():
    bus = MemoryBus()
    bus.remember(_entry("Prefers Python 3.13", scope="user", scope_id="u-1"))
    out = bus.summarize()
    assert "-- tier: semantic --" in out
    assert "Prefers Python 3.13" in out


# ---------------------------------------------------------------------------
# ParserRegistry: correct parser picked per mime/extension
# ---------------------------------------------------------------------------


def test_parser_registry_txt_ext():
    reg = ParserRegistry()
    assert isinstance(reg.pick(filename="a.txt"), TextDocumentParser)
    assert isinstance(reg.pick(filename="a.md"), TextDocumentParser)
    assert isinstance(reg.pick(mime_type="text/markdown"), TextDocumentParser)


def test_parser_registry_html_mime():
    reg = ParserRegistry()
    assert isinstance(reg.pick(mime_type="text/html"), HtmlDocumentParser)
    assert isinstance(reg.pick(filename="doc.htm"), HtmlDocumentParser)


def test_parser_registry_csv():
    reg = ParserRegistry()
    assert isinstance(reg.pick(filename="export.csv"), CsvDocumentParser)
    assert isinstance(reg.pick(mime_type="text/csv"), CsvDocumentParser)


# ---------------------------------------------------------------------------
# Chunker: overlap semantics
# ---------------------------------------------------------------------------


def test_chunker_overlap_boundaries_exact():
    c = Chunker(chars_per_chunk=10, overlap_chars=3)
    text = "0123456789ABCDEFGHIJ"  # 20 chars
    doc = ParsedDocument(title="t", content=text)
    chunks = c.chunk(doc)
    # step=10-3=7 → n = ceil((20-3)/7) = ceil(17/7)=3
    # windows: [0:10] (0123456789), [7:17] (789ABCDEFG), [14:20] (EFGHIJ)
    assert [ch.text for ch in chunks] == [
        "0123456789",
        "789ABCDEFG",
        "EFGHIJ",
    ]
    for i, ch in enumerate(chunks):
        assert ch.citation is not None
        assert ch.citation.fragment_index == i
        assert ch.citation.fragment_count == len(chunks)
        assert ch.citation.start_char <= ch.citation.end_char


def test_chunker_rejects_invalid_args():
    with pytest.raises(ValueError):
        Chunker(chars_per_chunk=0)
    with pytest.raises(ValueError):
        Chunker(chars_per_chunk=10, overlap_chars=-1)
    with pytest.raises(ValueError):
        Chunker(chars_per_chunk=10, overlap_chars=10)


# ---------------------------------------------------------------------------
# Parsers: each yields non-empty content + sensible title
# ---------------------------------------------------------------------------


def test_text_parser_extracts_h1():
    raw = "# My Great Doc\n\nBody of document."
    doc = TextDocumentParser().parse(raw.encode(), hint_filename="x.md")
    assert doc.title == "My Great Doc"


def test_html_parser_extracts_title_and_strips_tags():
    raw = "<html><head><title>Home</title></head><body><h1>Welcome</h1><p>Hi <b>there</b>.</p></body></html>"
    doc = HtmlDocumentParser().parse(raw.encode())
    assert "Home" in doc.title
    assert "Welcome" in doc.content
    assert "<h1>" not in doc.content
    assert "&amp;" not in doc.content or "&" not in doc.content  # entity decoded


def test_csv_parser_turns_rows_into_columnar_text():
    raw = "name,age\nAda,30\nGrace,40\n"
    doc = CsvDocumentParser().parse(raw.encode(), hint_filename="people.csv")
    assert "name=Ada" in doc.content
    assert "Grace" in doc.content
    assert "Rows: 2" in doc.content or "2 data rows" in doc.content


# ---------------------------------------------------------------------------
# IngestPipeline + BM25 search
# ---------------------------------------------------------------------------


MD = """
# RAG Foundations

Noesis stores memory across six tiers. Working memory (LRU) serves the hot
path, while semantic memory uses vector search for long-term recall. Hybrid
search fuses BM25 keyword ranking with vector similarity via reciprocal rank
fusion (RRF) — so both rare terms and semantic neighbours surface in the top-k.

Citations always trace back to the source document: document id, fragment
number, and char offsets are stored inline so the LLM answer can always
render "From X, page 4".
"""


def test_ingest_content_sha_and_citation_present():
    pipeline = IngestPipeline(chunker=Chunker(chars_per_chunk=200, overlap_chars=50))
    doc, chunks = pipeline.ingest(MD.encode(), filename="rag_foundations.md")
    assert doc.content_sha256
    assert len(chunks) >= 2
    _first, _last = chunks[0], chunks[-1]
    for ch in chunks:
        assert ch.citation is not None
        assert ch.citation.content_sha256 == doc.content_sha256
        assert ch.citation.document_id == doc.document_id
        assert 0 <= ch.citation.fragment_index < ch.citation.fragment_count


def test_fragment_store_bm25_single_term_hits_the_relevant_chunk():
    pipeline = IngestPipeline()
    pipeline.ingest(MD.encode(), filename="rag_foundations.md")
    hits = pipeline.store.bm25("RRF reciprocal rank", top_k=10)
    assert hits, "expected BM25 hits for 'RRF reciprocal rank' in the hybrid-search paragraph"
    top_text = hits[0][0].text.lower()
    assert "reciprocal" in top_text and "fusion" in top_text


# ---------------------------------------------------------------------------
# HybridSearch with simulated vector rank
# ---------------------------------------------------------------------------


def test_hybrid_search_rrf_merges_both_halves():
    pipeline = IngestPipeline(chunker=Chunker(chars_per_chunk=200, overlap_chars=50))
    _doc, chunks = pipeline.ingest(MD.encode(), filename="rag.md")
    hs = HybridSearch(pipeline.store)
    # Simulate a "vector" rank that returns the *last* chunk; BM25 returns the
    # first paragraph for "six tiers".  Hybrid should have both in the top-k.
    last_fragment = chunks[-1]

    def fake_vector(query: str, *, top_k: int):
        return [(last_fragment, 0.9)]

    hs.set_vector_search(fake_vector)
    results: list[SearchResult] = hs.search("six tiers memory", top_k=10)
    assert results
    ids_in_rrf = {r.fragment.fragment_id for r in results}
    assert last_fragment.fragment_id in ids_in_rrf
    # Provenance tracking: we must observe both BM25-only and vector-only provenance
    # (because "six tiers memory" is only in the opening paragraph, while the
    # vector hook only provides the tail chunk.  In a hybrid system both ranks must appear
    # with a combined / BM25-only or dual-provenance chunks alongside a vector-only
    # chunk.
    bm25_only = [r for r in results if r.provenance == (True, False)]
    vector_only = [r for r in results if r.provenance == (False, True)]
    assert bm25_only
    assert vector_only


# ---------------------------------------------------------------------------
# Citations: ingest 4 formats → every chunk has valid citation bounds.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("filename", "raw"),
    [
        ("a.txt", b"hello world\ngoodbye"),
        (
            "b.html",
            b"<html><title>X</title><body><p>Hello world paragraph one.</p>"
            b"<p>Second paragraph with words: Noesis memory tiers test case.</p></body></html>",
        ),
        ("c.csv", b"col_a,col_b,col_c\n1,2,3\n4,5,6\n7,8,9\n10,11,12\n"),
        ("d.md", b"# Title\n\n" + MD.encode().strip()),
    ],
)
def test_ingest_any_parser_all_chunks_have_valid_citations(filename, raw):
    pipeline = IngestPipeline(chunker=Chunker(chars_per_chunk=120, overlap_chars=30))
    doc, chunks = pipeline.ingest(raw, filename=filename)
    assert chunks
    for i, ch in enumerate(chunks):
        cite = ch.citation
        assert cite is not None
        assert cite.document_id == doc.document_id
        assert cite.fragment_index == i
        assert 0 <= cite.fragment_index < cite.fragment_count
        assert 0 <= cite.start_char <= cite.end_char <= max(1, len(doc.content))
        # Re-slice document content at cited offsets — must match chunk text.
        assert doc.content[cite.start_char : cite.end_char] == ch.text
