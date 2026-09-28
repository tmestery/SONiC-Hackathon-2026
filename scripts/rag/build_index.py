#!/usr/bin/env python3
"""
Chunk data/rag/sources/ and build a BM25 index under data/rag/index/.
"""

from __future__ import annotations

import json
import pickle
import re
import time
from pathlib import Path

from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parents[2]
RAG_DIR = ROOT / "data" / "rag"
SOURCES_DIR = RAG_DIR / "sources"
CHUNKS_FILE = RAG_DIR / "chunks.jsonl"
INDEX_DIR = RAG_DIR / "index"
BM25_FILE = INDEX_DIR / "bm25.pkl"
META_FILE = INDEX_DIR / "meta.json"

TARGET_CHARS = 1000
OVERLAP_CHARS = 150
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
FRONT_MATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
TOKEN_RE = re.compile(r"[a-z0-9_]+", re.IGNORECASE)


def strip_front_matter(text: str) -> str:
    return FRONT_MATTER_RE.sub("", text, count=1)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def first_heading(text: str, fallback: str) -> str:
    match = HEADING_RE.search(text)
    if match:
        return match.group(2).strip()
    return fallback


def split_sections(text: str) -> list[tuple[str, str]]:
    """Return list of (section_title, section_body)."""
    matches = list(HEADING_RE.finditer(text))
    if not matches:
        return [("", text.strip())]

    sections: list[tuple[str, str]] = []
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append(("", preamble))

    for i, match in enumerate(matches):
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append((title, body))
    return sections


def window_chunks(text: str, target: int = TARGET_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= target:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + target)
        if end < len(text):
            # Prefer breaking on paragraph or sentence boundary.
            window = text[start:end]
            break_at = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"))
            if break_at > target // 3:
                end = start + break_at + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def line_span(full_text: str, chunk: str) -> tuple[int, int]:
    idx = full_text.find(chunk)
    if idx < 0:
        return 1, full_text.count("\n") + 1
    start_line = full_text[:idx].count("\n") + 1
    end_line = start_line + chunk.count("\n")
    return start_line, end_line


def iter_source_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(SOURCES_DIR.rglob("*")):
        if not path.is_file():
            continue
        if path.name == "SOURCE_COMMIT.txt":
            continue
        if path.suffix.lower() not in {".md", ".txt", ".rst"}:
            continue
        files.append(path)
    return files


def build_chunks() -> list[dict]:
    chunks: list[dict] = []
    chunk_id = 0
    for path in iter_source_files():
        rel = str(path.relative_to(SOURCES_DIR)).replace("\\", "/")
        raw = path.read_text(encoding="utf-8", errors="replace")
        text = strip_front_matter(raw).replace("\r\n", "\n")
        file_title = first_heading(text, path.stem.replace("_", " ").replace("-", " "))

        for section_title, section_body in split_sections(text):
            title = section_title or file_title
            for piece in window_chunks(section_body):
                # Prefer locating within the full file for line numbers.
                start_line, end_line = line_span(text, piece)
                chunks.append(
                    {
                        "id": f"rag-{chunk_id:06d}",
                        "path": rel,
                        "title": title,
                        "text": piece,
                        "start_line": start_line,
                        "end_line": end_line,
                    }
                )
                chunk_id += 1
    return chunks


def read_source_commit() -> str | None:
    commit_file = SOURCES_DIR / "SOURCE_COMMIT.txt"
    if not commit_file.exists():
        return None
    for line in commit_file.read_text().splitlines():
        if line.startswith("commit:"):
            return line.split(":", 1)[1].strip()
    return None


def main() -> int:
    if not SOURCES_DIR.is_dir() or not any(SOURCES_DIR.iterdir()):
        raise SystemExit(
            f"No sources in {SOURCES_DIR}. Run: python3 scripts/rag/fetch_docs.py"
        )

    chunks = build_chunks()
    if not chunks:
        raise SystemExit("No chunks produced from sources.")

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with CHUNKS_FILE.open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    tokenized = [tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(tokenized)
    with BM25_FILE.open("wb") as fh:
        pickle.dump({"bm25": bm25, "chunk_ids": [c["id"] for c in chunks]}, fh)

    meta = {
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "chunk_count": len(chunks),
        "source_files": len(iter_source_files()),
        "source_commit": read_source_commit(),
        "target_chars": TARGET_CHARS,
        "overlap_chars": OVERLAP_CHARS,
        "chunks_file": str(CHUNKS_FILE.relative_to(ROOT)),
        "bm25_file": str(BM25_FILE.relative_to(ROOT)),
    }
    META_FILE.write_text(json.dumps(meta, indent=2) + "\n")

    print(f"Wrote {len(chunks)} chunks → {CHUNKS_FILE}")
    print(f"BM25 index → {BM25_FILE}")
    print(f"Meta → {META_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
