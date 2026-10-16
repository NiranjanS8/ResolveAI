"""Knowledge-base ingestion: load internal documents, chunk, embed and upsert.

The agent's knowledge comes from the company's own policy and support
documents. This module walks a documents folder, splits each file into chunks
and keeps ``knowledge_chunks`` in sync, so re-indexing after an edit is a
no-op for unchanged content and a replace for changed content.

Chunks are keyed by ``source_id`` (the document path) plus ``content_hash``, so
ingestion is idempotent and safe to re-run.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from uuid import uuid4

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.embeddings import (
    EMBEDDING_MODELS,
    active_provider,
    embed_text,
    embedding_dimension,
)
from app.db.session import SyncSessionLocal
from app.models.base import KnowledgeChunk

REPO_ROOT = Path(__file__).resolve().parents[3]

SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".html", ".htm"}
IGNORED_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv"}

# Chunks written by the feedback loop come from resolved tickets, not from
# documents, so pruning must never remove them.
PRUNE_PROTECTED_SOURCE_TYPES = {"feedback"}

SOURCE_TYPE_BY_DIR = {
    "policies": "policy",
    "policy": "policy",
    "support": "support",
    "faqs": "faq",
    "faq": "faq",
    "guides": "guide",
    "products": "product",
    "internal": "internal",
}
DEFAULT_SOURCE_TYPE = "doc"


def knowledge_dir() -> Path:
    """Documents folder, overridable via the ``KNOWLEDGE_DIR`` setting."""
    if settings.KNOWLEDGE_DIR:
        return Path(settings.KNOWLEDGE_DIR).expanduser().resolve()
    return REPO_ROOT / "knowledge"


def embedding_model_label() -> str:
    provider = active_provider()
    if not provider:
        return "local-deterministic"
    return EMBEDDING_MODELS[provider][0]


@dataclass(frozen=True)
class SourceDocument:
    source_id: str
    title: str
    source_path: str
    source_type: str
    text: str


@dataclass(frozen=True)
class ChunkRecord:
    source_id: str
    source_type: str
    doc_title: str
    source_path: str
    chunk_index: int
    content: str
    content_hash: str


@dataclass
class IngestReport:
    documents: int = 0
    chunks_total: int = 0
    inserted: int = 0
    unchanged: int = 0
    pruned: int = 0
    embedding_model: str = ""
    dimension: int = 0


class _HTMLToText(HTMLParser):
    """Minimal HTML -> text conversion that keeps block structure."""

    _SKIP = {"script", "style", "noscript", "template"}
    _BLOCK = {
        "p", "div", "br", "li", "ul", "ol", "tr", "table", "section", "article",
        "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._title: list[str] = []
        self._heading: list[str] = []
        self._heading_seen = False
        self._capture: str | None = None
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self._SKIP:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._capture = "title"
        elif tag == "h1" and not self._heading_seen:
            self._capture = "heading"
            self._heading_seen = True
        if tag in self._BLOCK:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag == self._capture:
            self._capture = None
        if tag in self._BLOCK:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._capture == "title":
            self._title.append(data)
        elif self._capture == "heading":
            self._heading.append(data)
        text = data.strip()
        if text:
            self._parts.append(f"{text} ")

    def text(self) -> str:
        return _normalize_whitespace("".join(self._parts))

    def title(self) -> str | None:
        for parts in (self._title, self._heading):
            candidate = " ".join("".join(parts).split())
            if candidate:
                return candidate
        return None


def _normalize_whitespace(text: str) -> str:
    """Collapse inline runs of whitespace and drop blank-line runs."""
    lines = [re.sub(r"[ \t\u00a0]+", " ", line).strip() for line in text.splitlines()]
    collapsed: list[str] = []
    for line in lines:
        if not line and collapsed and not collapsed[-1]:
            continue
        collapsed.append(line)
    return "\n".join(collapsed).strip()


def _read_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    return raw.replace("\r\n", "\n").replace("\r", "\n")


def _humanize(stem: str) -> str:
    return re.sub(r"[-_]+", " ", stem).strip().title()


def _markdown_title(text: str) -> str | None:
    match = re.search(r"^\s{0,3}#\s+(.+?)\s*#*\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def _first_line_title(text: str) -> str | None:
    for line in text.splitlines():
        candidate = line.strip()
        if candidate and len(candidate) <= 120:
            return candidate
        if candidate:
            return None
    return None


def _source_type_for(relative_path: Path) -> str:
    parts = relative_path.parts
    if len(parts) > 1:
        return SOURCE_TYPE_BY_DIR.get(parts[0].lower(), DEFAULT_SOURCE_TYPE)
    return DEFAULT_SOURCE_TYPE


def _load_document(path: Path, relative_path: Path) -> SourceDocument:
    raw = _read_text(path)
    suffix = path.suffix.lower()

    if suffix in {".html", ".htm"}:
        parser = _HTMLToText()
        parser.feed(raw)
        text = parser.text()
        title = parser.title()
    elif suffix in {".md", ".markdown"}:
        text = raw.strip()
        title = _markdown_title(raw)
    else:
        text = raw.strip()
        title = _first_line_title(raw)

    return SourceDocument(
        source_id=relative_path.with_suffix("").as_posix(),
        title=(title or _humanize(path.stem)).strip(),
        source_path=relative_path.as_posix(),
        source_type=_source_type_for(relative_path),
        text=text,
    )


def load_documents(root: Path | None = None) -> list[SourceDocument]:
    """Load every supported document under ``root``, sorted by path."""
    root = Path(root) if root is not None else knowledge_dir()
    if not root.exists():
        raise FileNotFoundError(f"Knowledge directory not found: {root}")

    documents: list[SourceDocument] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        relative_path = path.relative_to(root)
        if any(part in IGNORED_DIRS for part in relative_path.parts):
            continue

        document = _load_document(path, relative_path)
        if not document.text:
            continue
        documents.append(document)
    return documents


def _splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.KNOWLEDGE_CHUNK_SIZE,
        chunk_overlap=settings.KNOWLEDGE_CHUNK_OVERLAP,
        separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", ". ", " "],
        length_function=len,
    )


def _chunk_document(
    document: SourceDocument, splitter: RecursiveCharacterTextSplitter
) -> list[ChunkRecord]:
    """Split a document into overlapping chunks, each carrying its title."""
    records: list[ChunkRecord] = []
    for index, piece in enumerate(splitter.split_text(document.text)):
        piece = piece.strip()
        if not piece:
            continue
        content = f"{document.title}\n{piece}"
        records.append(
            ChunkRecord(
                source_id=document.source_id,
                source_type=document.source_type,
                doc_title=document.title,
                source_path=document.source_path,
                chunk_index=index,
                content=content,
                content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            )
        )
    return records


def _stored_hashes(rows) -> list[str]:
    return sorted(row.content_hash for row in rows if row.content_hash)


def ingest(
    root: Path | None = None, *, prune: bool = True, dry_run: bool = False
) -> IngestReport:
    """Sync ``knowledge_chunks`` with the documents under ``root``.

    Documents whose chunk set is unchanged are left alone; changed documents
    have their chunks replaced. With ``prune``, chunks whose document is gone
    are removed (feedback-loop chunks are always kept).
    """
    root = Path(root) if root is not None else knowledge_dir()
    splitter = _splitter()

    desired: dict[str, list[ChunkRecord]] = {}
    for document in load_documents(root):
        desired[document.source_id] = _chunk_document(document, splitter)

    report = IngestReport(
        documents=len(desired),
        chunks_total=sum(len(chunks) for chunks in desired.values()),
        embedding_model=embedding_model_label(),
        dimension=embedding_dimension(),
    )

    with SyncSessionLocal() as db:
        existing_rows = db.execute(
            select(
                KnowledgeChunk.id,
                KnowledgeChunk.source_id,
                KnowledgeChunk.source_type,
                KnowledgeChunk.content_hash,
            )
        ).all()
        by_source = defaultdict(list)
        for row in existing_rows:
            by_source[row.source_id].append(row)

        stale_source_ids = [sid for sid in by_source if sid not in desired]

        if dry_run:
            for source_id, chunks in desired.items():
                if _stored_hashes(by_source.get(source_id, [])) == sorted(
                    chunk.content_hash for chunk in chunks
                ):
                    report.unchanged += len(chunks)
                else:
                    report.inserted += len(chunks)
            report.pruned = sum(len(by_source[sid]) for sid in stale_source_ids)
            return report

        for source_id, chunks in desired.items():
            current = by_source.get(source_id, [])
            if _stored_hashes(current) == sorted(chunk.content_hash for chunk in chunks):
                report.unchanged += len(chunks)
                continue

            if current:
                db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.source_id == source_id))

            for chunk in chunks:
                db.add(
                    KnowledgeChunk(
                        id=uuid4(),
                        source_id=chunk.source_id,
                        source_type=chunk.source_type,
                        content=chunk.content,
                        embedding=embed_text(chunk.content),
                        embedding_model=report.embedding_model,
                        doc_title=chunk.doc_title,
                        source_path=chunk.source_path,
                        chunk_index=chunk.chunk_index,
                        content_hash=chunk.content_hash,
                        meta={
                            "title": chunk.doc_title,
                            "source_path": chunk.source_path,
                            "chunk_index": chunk.chunk_index,
                        },
                    )
                )
                report.inserted += 1
            db.flush()

        if prune:
            for source_id in stale_source_ids:
                rows = by_source[source_id]
                if any(row.source_type in PRUNE_PROTECTED_SOURCE_TYPES for row in rows):
                    continue
                db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.source_id == source_id))
                report.pruned += len(rows)

        db.commit()

    return report
