#!/usr/bin/env python3
"""
Phase 2: attach unified diffs to clean records as resolution.patch.

Not run as part of v1 cleaning. Clean schema 1.0 omits patch until this
script is executed intentionally.

Usage:
  python3 scripts/buildimage/enrich_patches.py
  python3 scripts/buildimage/enrich_patches.py --limit 5

Fetches `gh pr diff <number> --repo <repository>` for each clean record
and writes the unified diff onto `resolution.patch`. Large diffs can be
stored under data/buildimage/clean/patches/ instead by passing
`--sidecar`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLEAN_DIR = ROOT / "data" / "buildimage" / "clean"
PATCH_DIR = CLEAN_DIR / "patches"


def fetch_diff(repository: str, pr_number: int) -> str:
    cmd = ["gh", "pr", "diff", str(pr_number), "--repo", repository]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"gh failed for {repository}#{pr_number}")
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description="Attach PR unified diffs to clean records.")
    parser.add_argument("--limit", type=int, default=0, help="Max records to enrich (0 = all).")
    parser.add_argument(
        "--sidecar",
        action="store_true",
        help="Write diffs to clean/patches/pr-<repo>-<n>.diff and set patch to that path.",
    )
    args = parser.parse_args()

    files = sorted(CLEAN_DIR.glob("issue-*.json"), key=lambda p: int(p.stem.split("-")[1]))
    if args.limit:
        files = files[: args.limit]
    if not files:
        print("No clean records found. Run scripts/buildimage/clean_buildimage.py first.")
        return 1

    if args.sidecar:
        PATCH_DIR.mkdir(parents=True, exist_ok=True)

    updated = 0
    failed = 0
    for path in files:
        with path.open() as fh:
            record = json.load(fh)
        resolution = record.get("resolution") or {}
        repo = resolution.get("repository")
        pr_number = resolution.get("pr_number")
        if not repo or not pr_number:
            continue
        try:
            diff = fetch_diff(repo, pr_number)
        except Exception as exc:
            print(f"FAIL {path.name}: {exc}")
            failed += 1
            continue

        if args.sidecar:
            safe_repo = repo.replace("/", "_")
            patch_path = PATCH_DIR / f"pr-{safe_repo}-{pr_number}.diff"
            patch_path.write_text(diff)
            resolution["patch"] = str(patch_path.relative_to(ROOT))
        else:
            resolution["patch"] = diff
        record["resolution"] = resolution
        with path.open("w") as fh:
            json.dump(record, fh, indent=2)
            fh.write("\n")
        updated += 1
        print(f"OK {path.name} ({len(diff)} bytes)")

    print(f"Updated {updated}, failed {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
