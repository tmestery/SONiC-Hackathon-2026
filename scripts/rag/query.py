#!/usr/bin/env python3
"""
Query the local BM25 RAG index.

Usage:
  python3 scripts/rag/query.py "orchagent crash warm reboot"
  python3 scripts/rag/query.py "BGP ECMP" --top 5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from rag.retriever import Bm25Index  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Query the SONiC RAG BM25 index.")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--top", type=int, default=5, help="Number of hits (default 5)")
    parser.add_argument(
        "--rag-dir",
        type=Path,
        default=ROOT / "data" / "rag",
        help="RAG corpus directory (default: data/rag)",
    )
    args = parser.parse_args()

    try:
        index = Bm25Index.load(args.rag_dir)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    hits = index.search(args.query, top_k=args.top)
    print(f"Query: {args.query!r}\n")
    if not hits:
        print("No hits.")
        return 0
    for rank, hit in enumerate(hits, start=1):
        preview = " ".join(hit.text.split())
        if len(preview) > 220:
            preview = preview[:217] + "..."
        print(f"{rank}. score={hit.score:.3f}  {hit.path}  [{hit.title}]")
        print(f"   {hit.id}  lines {hit.start_line}-{hit.end_line}")
        print(f"   {preview}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
