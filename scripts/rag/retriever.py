"""
Shared BM25 retrieval over data/rag/ for training + eval prompts.

Index only SONiC docs (never clean/ issue-PR labels).
"""

from __future__ import annotations

import json
import pickle
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"[a-z0-9_]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "")]


def truncate(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 3)].rstrip() + "..."


@dataclass(frozen=True)
class Hit:
    id: str
    path: str
    title: str
    text: str
    score: float
    start_line: int
    end_line: int

    def to_meta(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("text", None)
        return d


class Bm25Index:
    def __init__(
        self,
        *,
        bm25: Any,
        chunk_ids: list[str],
        chunks: dict[str, dict[str, Any]],
        rag_dir: Path,
    ) -> None:
        self.bm25 = bm25
        self.chunk_ids = chunk_ids
        self.chunks = chunks
        self.rag_dir = rag_dir

    @classmethod
    def load(cls, rag_dir: Path) -> "Bm25Index":
        rag_dir = Path(rag_dir)
        chunks_file = rag_dir / "chunks.jsonl"
        bm25_file = rag_dir / "index" / "bm25.pkl"
        if not chunks_file.exists() or not bm25_file.exists():
            raise FileNotFoundError(
                f"RAG index missing under {rag_dir}. Run:\n"
                "  python3 scripts/rag/fetch_docs.py\n"
                "  python3 scripts/rag/build_index.py"
            )
        chunks: dict[str, dict[str, Any]] = {}
        with chunks_file.open(encoding="utf-8") as fh:
            for line in fh:
                chunk = json.loads(line)
                chunks[chunk["id"]] = chunk
        with bm25_file.open("rb") as fh:
            payload = pickle.load(fh)
        return cls(
            bm25=payload["bm25"],
            chunk_ids=list(payload["chunk_ids"]),
            chunks=chunks,
            rag_dir=rag_dir,
        )

    def search(self, query: str, *, top_k: int = 5) -> list[Hit]:
        tokens = tokenize(query)
        if not tokens or top_k <= 0:
            return []
        scores = self.bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[
            :top_k
        ]
        hits: list[Hit] = []
        for idx, score in ranked:
            if score <= 0:
                continue
            chunk = self.chunks.get(self.chunk_ids[idx])
            if not chunk:
                continue
            hits.append(
                Hit(
                    id=str(chunk.get("id") or ""),
                    path=str(chunk.get("path") or ""),
                    title=str(chunk.get("title") or ""),
                    text=str(chunk.get("text") or ""),
                    score=float(score),
                    start_line=int(chunk.get("start_line") or 0),
                    end_line=int(chunk.get("end_line") or 0),
                )
            )
        return hits


def record_query(record: dict[str, Any], *, max_query_chars: int = 1500) -> str:
    issue = record.get("issue") or {}
    failure = record.get("failure") or {}
    title = (issue.get("title") or "").strip()
    body = (failure.get("body") or "").strip()
    query = f"{title}\n{body}".strip() if title or body else ""
    return truncate(query, max_query_chars)


def format_rag_context(
    hits: list[Hit],
    *,
    max_chars_per_chunk: int = 800,
) -> str:
    if not hits:
        return ""
    blocks: list[str] = []
    for i, hit in enumerate(hits, start=1):
        body = truncate(hit.text, max_chars_per_chunk)
        header = f"[{i}] {hit.path} — {hit.title} (score={hit.score:.3f})"
        blocks.append(f"{header}\n{body}" if body else header)
    return "Retrieved SONiC documentation:\n\n" + "\n\n".join(blocks)


def build_user_content(
    record: dict[str, Any],
    *,
    rag_context: str = "",
) -> str:
    issue = record.get("issue") or {}
    failure = record.get("failure") or {}
    title = (issue.get("title") or "").strip()
    body = (failure.get("body") or "").strip()
    base = f"Title: {title}\n\nFailure report:\n{body}".strip()
    rag_context = (rag_context or "").strip()
    if rag_context:
        return f"{base}\n\n{rag_context}".strip()
    return base


def rag_cfg_enabled(cfg: dict[str, Any] | None) -> bool:
    rag = (cfg or {}).get("rag") if isinstance(cfg, dict) else None
    if not isinstance(rag, dict):
        return False
    return bool(rag.get("enabled", False))


def load_index_from_cfg(root: Path, cfg: dict[str, Any] | None) -> Bm25Index | None:
    if not rag_cfg_enabled(cfg):
        return None
    rag = (cfg or {}).get("rag") or {}
    rag_rel = rag.get("rag_dir") or "data/rag"
    return Bm25Index.load(root / rag_rel)


def retrieve_for_record(
    index: Bm25Index,
    record: dict[str, Any],
    *,
    top_k: int = 4,
    max_query_chars: int = 1500,
    max_chars_per_chunk: int = 800,
) -> tuple[str, list[Hit], str]:
    """Return (query, hits, formatted rag_context)."""
    query = record_query(record, max_query_chars=max_query_chars)
    hits = index.search(query, top_k=top_k)
    context = format_rag_context(hits, max_chars_per_chunk=max_chars_per_chunk)
    return query, hits, context
