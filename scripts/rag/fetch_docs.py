#!/usr/bin/env python3
"""
Fetch SONiC documentation into data/rag/sources/.

Sparse-clones sonic-net/SONiC (doc/ only) and copies markdown/text files.
Also pulls a few high-value wiki pages into sources/wiki/.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / ".cache" / "sonic-docs"
SOURCES_DIR = ROOT / "data" / "rag" / "sources"
REPO_URL = "https://github.com/sonic-net/SONiC.git"
WIKI_PAGES = {
    "Architecture.md": "https://raw.githubusercontent.com/wiki/sonic-net/SONiC/Architecture.md",
    "Home.md": "https://raw.githubusercontent.com/wiki/sonic-net/SONiC/Home.md",
}


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def sparse_clone() -> Path:
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
    CACHE_DIR.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--sparse",
            REPO_URL,
            str(CACHE_DIR),
        ]
    )
    run(["git", "sparse-checkout", "set", "doc"], cwd=CACHE_DIR)
    return CACHE_DIR


def copy_docs(repo_dir: Path) -> int:
    doc_root = repo_dir / "doc"
    if not doc_root.is_dir():
        raise SystemExit(f"Missing doc/ in clone: {doc_root}")

    if SOURCES_DIR.exists():
        shutil.rmtree(SOURCES_DIR)
    SOURCES_DIR.mkdir(parents=True)

    copied = 0
    for path in doc_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".txt", ".rst"}:
            continue
        rel = path.relative_to(doc_root)
        dest = SOURCES_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        copied += 1
    return copied


def write_commit(repo_dir: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    sha = result.stdout.strip()
    (SOURCES_DIR / "SOURCE_COMMIT.txt").write_text(
        f"repository: sonic-net/SONiC\n"
        f"path: doc/\n"
        f"commit: {sha}\n"
        f"url: {REPO_URL}\n"
    )
    return sha


def fetch_wiki() -> int:
    wiki_dir = SOURCES_DIR / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    ok = 0
    for name, url in WIKI_PAGES.items():
        dest = wiki_dir / name
        try:
            print(f"+ fetch {url}")
            # Prefer curl (system certs); fall back to urllib.
            result = subprocess.run(
                ["curl", "-fsSL", url],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                text = result.stdout
            else:
                with urllib.request.urlopen(url, timeout=60) as resp:
                    text = resp.read().decode("utf-8", errors="replace")
            if text.lstrip().startswith("404") or "<!DOCTYPE html>" in text[:200].lower():
                print(f"  skip (not found): {name}")
                continue
            dest.write_text(text)
            ok += 1
        except Exception as exc:
            print(f"  skip {name}: {exc}")
    return ok


def main() -> int:
    repo_dir = sparse_clone()
    n_docs = copy_docs(repo_dir)
    sha = write_commit(repo_dir)
    n_wiki = fetch_wiki()
    print(f"Copied {n_docs} doc files + {n_wiki} wiki pages")
    print(f"Source commit: {sha}")
    print(f"Sources: {SOURCES_DIR}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Command failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
