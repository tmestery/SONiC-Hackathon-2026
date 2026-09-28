#!/usr/bin/env python3
"""
Query the local BM25 RAG index.

Usage:
  python3 scripts/rag/query.py "orchagent crash warm reboot"
  python3 scripts/rag/query.py "BGP ECMP" --top 5
"""

from __future__ import annotations

import argparse
import json
import pickle
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAG_DIR = ROOT / "data" / "rag"
CHUNKS_FILE = RAG_DIR / "chunks.jsonl"
BM25_FILE = RAG_DIR / "index" / "bm25.pkl"
TOKEN_RE = re.compile(r"[a-z0-9_]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def load_chunks() -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    with CHUNKS_FILE.open(encoding="utf-8") as fh:
        for line in fh:
            chunk = json.loads(line)
            by_id[chunk["id"]] = chunk
    return by_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Query the SONiC RAG BM25 index.")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--top", type=int, default=5, help="Number of hits (default 5)")
    args = parser.parse_args()

    if not BM25_FILE.exists() or not CHUNKS_FILE.exists():
        print(
            "Index missing. Run:\n"
            "  python3 scripts/rag/fetch_docs.py\n"
            "  python3 scripts/rag/build_index.py",
            file=sys.stderr,
        )
        return 1

    with BM25_FILE.open("rb") as fh:
        payload = pickle.load(fh)
    bm25 = payload["bm25"]
    chunk_ids = payload["chunk_ids"]
    chunks = load_chunks()

    scores = bm25.get_scores(tokenize(args.query))
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[: args.top]

    print(f"Query: {args.query!r}\n")
    for rank, (idx, score) in enumerate(ranked, start=1):
        chunk = chunks[chunk_ids[idx]]
        preview = " ".join(chunk["text"].split())
        if len(preview) > 220:
            preview = preview[:217] + "..."
        print(f"{rank}. score={score:.3f}  {chunk['path']}  [{chunk['title']}]")
        print(f"   {chunk['id']}  lines {chunk['start_line']}-{chunk['end_line']}")
        print(f"   {preview}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
