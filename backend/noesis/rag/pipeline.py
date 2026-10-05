"""
M2.4 Multi-document RAG pipeline — pure in-memory, zero external deps.

Two-layer architecture (10yr-ahead thinking — swap any layer without touching
any other):

    ┌──────────────┐    ┌───────────────┐    ┌─────────────────────────┐
    │ Document     │───▶│   Chunker     │───▶│ FragmentStore (inverted │
    │ Parser       │    │ (sliding win) │    │  index + BM25 stats)    │
    └──────────────┘    └───────────────┘    └────────────┬────────────┘
                                                          │
                                                  ┌───────▼──────┐
                                                  │ HybridSearch │
                                                  │  (RRF merge:  │
                                                  │  BM25 + vec) │
                                                  └──────────────┘
Every chunk returned by :meth:`HybridSearch.search` carries its own
:class:`Citation` back-ref, so the caller can always produce "X% from doc Y,
page 4, fragment #7" citations in the final LLM answer.
"""

from __future__ import annotations

import csv as _stdlib_csv
import hashlib
import io
import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Citation:
    """Full back-reference from a chunk → the source document / page / offset."""

    document_id: UUID
    document_title: str
    source_url: str | None = None
    content_sha256: str | None = None  # full-document hash (for tamper-detect)
    fragment_index: int = 0  # which chunk
    fragment_count: int = 1
    start_char: int = 0
    end_char: int = 0
    page: int | None = None


@dataclass
class Fragment:
    """One chunk: text + citation + optional semantic embedding."""

    fragment_id: UUID = field(default_factory=uuid4)
    text: str = ""
    citation: Citation | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    embedding: list[float] | None = None
    tags: set[str] = field(default_factory=set)


@dataclass
class ParsedDocument:
    """Result of DocumentParser.parse() — raw text + structured metadata."""

    document_id: UUID = field(default_factory=uuid4)
    title: str = ""
    author: str = ""
    language: str = "en"
    content: str = ""  # full document as one string
    mime_type: str = "text/plain"
    source_url: str | None = None
    content_sha256: str = ""  # populated by IngestPipeline
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Document parser port + 4 reference implementations
# ---------------------------------------------------------------------------


class DocumentParser(ABC):
    """Hexagonal port for each file type / ingest source."""

    supported_mime_types: tuple[str, ...] = ()
    supported_extensions: tuple[str, ...] = ()

    @abstractmethod
    def parse(self, raw: bytes, *, hint_filename: str | None = None) -> ParsedDocument: ...


# --- TXT / Markdown: plain text, trim + extract title from first line ------


class TextDocumentParser(DocumentParser):
    supported_mime_types = ("text/plain", "text/markdown", "text/x-markdown")
    supported_extensions = (".txt", ".md", ".markdown")

    _H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)

    def parse(self, raw: bytes, *, hint_filename: str | None = None) -> ParsedDocument:
        text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n")
        first_heading = None
        m = self._H1_RE.search(text)
        if m:
            first_heading = m.group(1).strip()
        title = first_heading or hint_filename or "(untitled document)"
        return ParsedDocument(
            title=title,
            content=text,
            mime_type="text/markdown" if (hint_filename or "").endswith((".md", ".markdown")) else "text/plain",
            source_url=hint_filename,
        )


# --- HTML: strip tags using regex (lightweight — no bs4 dep in base M2) -----


class HtmlDocumentParser(DocumentParser):
    supported_mime_types = ("text/html", "application/xhtml+xml")
    supported_extensions = (".html", ".htm", ".xhtml")

    _TAG_RE = re.compile(r"<[^>]+>")
    _TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
    _MULTI_NL = re.compile(r"\n{3,}")

    def parse(self, raw: bytes, *, hint_filename: str | None = None) -> ParsedDocument:
        html = raw.decode("utf-8", errors="replace")
        title_match = self._TITLE_RE.search(html)
        title = title_match.group(1).strip() if title_match else (hint_filename or "(untitled)")
        # Replace common block tags with newlines for readable paragraph boundaries.
        text = re.sub(r"(?i)<(br|/p|/div|/h[1-6]|/li|/tr|blockquote)\s*/?>", "\n", html)
        text = self._TAG_RE.sub("", text)
        # Decode &-entities (minimal set — covers most scraped content).
        for entity, decoded in (
            ("&amp;", "&"),
            ("&lt;", "<"),
            ("&gt;", ">"),
            ("&quot;", '"'),
            ("&#39;", "'"),
            ("&nbsp;", " "),
            ("&apos;", "'"),
        ):
            text = text.replace(entity, decoded)
        text = self._MULTI_NL.sub("\n\n", text).strip()
        return ParsedDocument(
            title=title,
            content=text,
            mime_type="text/html",
            source_url=hint_filename,
        )


# --- CSV: each row becomes a structured fragment-like text block ------------


class CsvDocumentParser(DocumentParser):
    supported_mime_types = ("text/csv", "application/csv")
    supported_extensions = (".csv", ".tsv")

    def parse(self, raw: bytes, *, hint_filename: str | None = None) -> ParsedDocument:
        ext = (hint_filename or "").rsplit(".", 1)[-1].lower()
        delimiter = "\t" if ext == "tsv" else ","
        text = raw.decode("utf-8-sig", errors="replace")
        reader = _stdlib_csv.reader(io.StringIO(text), delimiter=delimiter)
        rows: list[list[str]] = list(reader)
        if not rows:
            return ParsedDocument(title=hint_filename or "(empty csv)", content="", mime_type="text/csv")
        header = rows[0]
        body_lines: list[str] = []
        body_lines.append(f"# CSV table — {len(header)} columns, {len(rows) - 1} data rows")
        body_lines.append("Columns: " + ", ".join(header))
        body_lines.append("")
        for i, row in enumerate(rows[1:], start=1):
            pairs = [f"{h}={v}" for h, v in zip(header, row, strict=False) if v]
            body_lines.append(f"Row {i}: " + " | ".join(pairs))
        return ParsedDocument(
            title=hint_filename or "(csv table)",
            content="\n".join(body_lines),
            mime_type="text/csv",
            source_url=hint_filename,
            metadata={"rows": len(rows) - 1, "columns": header},
        )


# --- Registry ----------------------------------------------------------------


class ParserRegistry:
    """Pick a DocumentParser based on mime/extension/filename.  No deps on magic libs."""

    def __init__(self) -> None:
        self._parsers: list[DocumentParser] = [
            TextDocumentParser(),
            HtmlDocumentParser(),
            CsvDocumentParser(),
        ]

    def register(self, parser: DocumentParser) -> None:
        self._parsers.insert(0, parser)

    def pick(
        self,
        *,
        mime_type: str | None = None,
        filename: str | None = None,
    ) -> DocumentParser:
        if mime_type:
            mt = mime_type.split(";")[0].strip().lower()
            for p in self._parsers:
                if mt in p.supported_mime_types:
                    return p
        if filename:
            ext = filename.lower()
            for p in self._parsers:
                if any(ext.endswith(s) for s in p.supported_extensions):
                    return p
        # Default: plain text parser.  Always produces a ParsedDocument — never raises.
        return TextDocumentParser()


# ---------------------------------------------------------------------------
# Chunker — sliding window with overlap
# ---------------------------------------------------------------------------


class Chunker:
    """Split a ParsedDocument into N overlapping chunks (token-count naive, char-count exact)."""

    def __init__(
        self,
        *,
        chars_per_chunk: int = 800,
        overlap_chars: int = 200,
    ) -> None:
        if chars_per_chunk <= 0:
            raise ValueError(f"Chunker: chars_per_chunk must be >0, got {chars_per_chunk}")
        if overlap_chars < 0:
            raise ValueError(f"Chunker: overlap_chars must be >=0, got {overlap_chars}")
        if overlap_chars >= chars_per_chunk:
            raise ValueError(f"Chunker: overlap_chars ({overlap_chars}) must be < chars_per_chunk ({chars_per_chunk})")
        self.chars_per_chunk = chars_per_chunk
        self.overlap_chars = overlap_chars

    def chunk(self, doc: ParsedDocument) -> list[Fragment]:
        text = doc.content or ""
        if not text:
            return []
        step = self.chars_per_chunk - self.overlap_chars
        fragments: list[Fragment] = []
        n = (len(text) - self.overlap_chars + step - 1) // step
        n = max(1, n)
        for i in range(n):
            start = i * step
            end = min(len(text), start + self.chars_per_chunk)
            citation = Citation(
                document_id=doc.document_id,
                document_title=doc.title,
                source_url=doc.source_url,
                content_sha256=doc.content_sha256 or None,
                fragment_index=i,
                fragment_count=n,
                start_char=start,
                end_char=end,
            )
            fragments.append(Fragment(text=text[start:end], citation=citation))
        return fragments


# ---------------------------------------------------------------------------
# FragmentStore — inverted index + per-term document frequencies for BM25
# ---------------------------------------------------------------------------


class FragmentStore:
    """In-memory inverted index.  Used by the BM25 half of HybridSearch."""

    def __init__(self, *, bm25_k1: float = 1.5, bm25_b: float = 0.75) -> None:
        self._frags: dict[UUID, Fragment] = {}
        self._docs: dict[UUID, ParsedDocument] = {}
        # term -> dict[fragment_id -> count_in_frag]
        self._term_index: dict[str, dict[UUID, int]] = {}
        self._frag_len: dict[UUID, int] = {}
        self._total_len = 0
        self._bm25_k1 = bm25_k1
        self._bm25_b = bm25_b
        self._TOKEN_RE = re.compile(r"\w+")

    # -------- ingestion -----------------------------------------------------
    def add_document(self, doc: ParsedDocument, chunks: list[Fragment]) -> None:
        self._docs[doc.document_id] = doc
        for f in chunks:
            self._frags[f.fragment_id] = f
            tokens = [t.lower() for t in self._TOKEN_RE.findall(f.text)]
            self._frag_len[f.fragment_id] = len(tokens)
            self._total_len += len(tokens)
            counts: dict[str, int] = {}
            for tok in tokens:
                counts[tok] = counts.get(tok, 0) + 1
            for tok, freq in counts.items():
                self._term_index.setdefault(tok, {})[f.fragment_id] = freq

    # -------- BM25 query ----------------------------------------------------
    def bm25(self, query: str, *, top_k: int = 20) -> list[tuple[Fragment, float]]:
        if not self._frags:
            return []
        query_tokens = [t.lower() for t in self._TOKEN_RE.findall(query)]
        n_frags = len(self._frags)
        avg_dl = self._total_len / n_frags
        scores: dict[UUID, float] = {}
        for qt in query_tokens:
            posting = self._term_index.get(qt)
            if not posting:
                continue
            # IDF = ln( (N - n_t + 0.5) / (n_t + 0.5) + 1 )  (Okapi)
            n_t = len(posting)
            idf = math.log((n_frags - n_t + 0.5) / (n_t + 0.5) + 1.0)
            for frag_id, f_tf in posting.items():
                dl = self._frag_len[frag_id]
                # TF saturation with dl-norm.
                denom = f_tf + self._bm25_k1 * (1 - self._bm25_b + self._bm25_b * dl / max(1e-9, avg_dl))
                contrib = idf * (f_tf * (self._bm25_k1 + 1)) / max(1e-9, denom)
                scores[frag_id] = scores.get(frag_id, 0.0) + contrib
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        return [(self._frags[fid], score) for fid, score in ranked]


# ---------------------------------------------------------------------------
# Hybrid Search — BM25 + vector-similarity fused with RRF
# ---------------------------------------------------------------------------


@dataclass
class SearchResult:
    fragment: Fragment
    score: float  # 0..1 global merged score
    bm25_rank: int | None = None
    vector_rank: int | None = None
    provenance: tuple[bool, bool] = (False, False)  # (from_bm25, from_vector)


class HybridSearch:
    """Merge BM25 keyword rank + (optional) semantic rank through RRF."""

    def __init__(self, store: FragmentStore, *, rrf_k: int = 60) -> None:
        self._store = store
        self._rrf_k = rrf_k
        # Optional override for semantic search.  When None (M2 default) we
        # simulate a "perfect" semantic vector rank as BM25-with-embedding-
        # bonus so hybrid == pure BM25 behaviour in tests.  Plugging a
        # VectorStorePort is a one-line setter.
        self._vector_search: Any = None  # type: ignore[assignment]

    def set_vector_search(self, fn) -> None:
        """Set a ``fn(query, top_k) -> list[(Fragment, sim_score)]`` callback."""
        self._vector_search = fn

    def search(self, query: str, *, top_k: int = 20) -> list[SearchResult]:
        if not query:
            return []
        # --- run both halves ------------------------------------------------
        bm25_results = self._store.bm25(query, top_k=max(top_k * 3, 50))
        vec_results = list(self._vector_search(query, top_k=max(top_k * 3, 50))) if self._vector_search is not None else []

        rrf: dict[UUID, float] = {}
        provenance: dict[UUID, list[bool]] = {}
        rank_map: dict[UUID, list[int | None]] = {}
        for rank, (frag, _score) in enumerate(bm25_results, start=1):
            rrf[frag.fragment_id] = 1.0 / (self._rrf_k + rank)
            provenance.setdefault(frag.fragment_id, [False, False])[0] = True
            rank_map.setdefault(frag.fragment_id, [None, None])[0] = rank
        for rank, (frag, _score) in enumerate(vec_results, start=1):
            rrf[frag.fragment_id] = rrf.get(frag.fragment_id, 0.0) + 1.0 / (self._rrf_k + rank)
            provenance.setdefault(frag.fragment_id, [False, False])[1] = True
            rank_map.setdefault(frag.fragment_id, [None, None])[1] = rank
        if not rrf:
            return []
        max_score = max(rrf.values())
        merged = sorted(rrf.items(), key=lambda kv: kv[1], reverse=True)
        # Need a fragment dict covering BM25 + vector results.
        frags_by_id: dict[UUID, Fragment] = {f.fragment_id: f for f, _s in bm25_results}
        for f, _s in vec_results:
            frags_by_id[f.fragment_id] = f
        out: list[SearchResult] = []
        for fid, s in merged[:top_k]:
            bm25_r, vec_r = rank_map.get(fid, [None, None])
            bm25_hit, vec_hit = provenance.get(fid, [False, False])
            out.append(
                SearchResult(
                    fragment=frags_by_id[fid],
                    score=s if max_score == 0 else s / max_score,
                    bm25_rank=bm25_r,
                    vector_rank=vec_r,
                    provenance=(bm25_hit, vec_hit),
                )
            )
        return out


# ---------------------------------------------------------------------------
# IngestPipeline — one-shot glue: bytes → parse → hash → chunk → store.
# ---------------------------------------------------------------------------


class IngestPipeline:
    """End-to-end ingest: raw bytes → registered in FragmentStore with citations wired."""

    def __init__(
        self,
        *,
        store: FragmentStore | None = None,
        parsers: ParserRegistry | None = None,
        chunker: Chunker | None = None,
    ) -> None:
        self._store = store or FragmentStore()
        self._parsers = parsers or ParserRegistry()
        self._chunker = chunker or Chunker()

    @property
    def store(self) -> FragmentStore:
        return self._store

    @property
    def chunker(self) -> Chunker:
        return self._chunker

    @property
    def parsers(self) -> ParserRegistry:
        return self._parsers

    def ingest(
        self,
        raw: bytes,
        *,
        mime_type: str | None = None,
        filename: str | None = None,
        override_id: UUID | None = None,
        override_title: str | None = None,
    ) -> tuple[ParsedDocument, list[Fragment]]:
        parser = self._parsers.pick(mime_type=mime_type, filename=filename)
        doc = parser.parse(raw, hint_filename=filename)
        if override_id is not None:
            doc.document_id = override_id
        if override_title is not None:
            doc.title = override_title
        doc.content_sha256 = hashlib.sha256(doc.content.encode("utf-8")).hexdigest()
        chunks = self._chunker.chunk(doc)
        self._store.add_document(doc, chunks)
        return doc, chunks


__all__ = [
    "Chunker",
    "Citation",
    "CsvDocumentParser",
    "DocumentParser",
    "Fragment",
    "FragmentStore",
    "HtmlDocumentParser",
    "HybridSearch",
    "IngestPipeline",
    "ParsedDocument",
    "ParserRegistry",
    "SearchResult",
    "TextDocumentParser",
]
