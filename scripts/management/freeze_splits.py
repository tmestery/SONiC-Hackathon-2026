#!/usr/bin/env python3
"""
Freeze train/test splits for data/management/clean/.

Strategy:
  - Eligible: quality.has_diagnostic_signal == true
  - Random shuffle with fixed seed (42)
  - 75% → train, 25% → test
  - Non-diagnostic records get split: null (excluded from both)

Writes data/management/splits.json (source of truth) and stamps each
clean/issue-*.json with a top-level "split" field.

Re-run is idempotent only if you pass --force (refusing to overwrite
an existing freeze by default).
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLEAN_DIR = ROOT / "data" / "management" / "clean"
SPLITS_FILE = ROOT / "data" / "management" / "splits.json"
TRAIN_RATIO = 0.75
SEED = 42


def load_records() -> list[dict]:
    records = []
    for path in sorted(CLEAN_DIR.glob("issue-*.json"), key=lambda p: int(p.stem.split("-")[1])):
        with path.open(encoding="utf-8") as fh:
            records.append(json.load(fh))
    return records


def build_splits(records: list[dict]) -> dict:
    eligible = [r for r in records if (r.get("quality") or {}).get("has_diagnostic_signal")]
    rng = random.Random(SEED)
    rng.shuffle(eligible)

    n = len(eligible)
    if n < 2:
        raise SystemExit(f"Need at least 2 diagnostic records to split; found {n}")

    n_train = int(n * TRAIN_RATIO)
    # Ensure both sides non-empty
    n_train = max(1, min(n - 1, n_train))
    train = eligible[:n_train]
    test = eligible[n_train:]

    return {
        "schema_version": "1.0",
        "source": "sonic-mgmt",
        "method": "random",
        "description": (
            "Eligible records have has_diagnostic_signal=true. "
            f"Random shuffle (seed={SEED}). "
            f"{TRAIN_RATIO:.0%} → train; {1 - TRAIN_RATIO:.0%} → test. "
            "Test is frozen — never train on it."
        ),
        "train_ratio": TRAIN_RATIO,
        "seed": SEED,
        "frozen_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "counts": {
            "eligible": n,
            "train": len(train),
            "test": len(test),
            "excluded_no_diagnostic_signal": len(records) - n,
        },
        "train": [r["issue"]["number"] for r in train],
        "test": [r["issue"]["number"] for r in test],
    }


def apply_splits(records: list[dict], splits: dict) -> None:
    train_set = set(splits["train"])
    test_set = set(splits["test"])
    for record in records:
        number = record["issue"]["number"]
        if number in train_set:
            record["split"] = "train"
        elif number in test_set:
            record["split"] = "test"
        else:
            record["split"] = None
        out = CLEAN_DIR / f"issue-{number}.json"
        with out.open("w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2)
            fh.write("\n")


def update_manifest(splits: dict) -> None:
    manifest_path = CLEAN_DIR / "manifest.json"
    if not manifest_path.exists():
        return
    with manifest_path.open(encoding="utf-8") as fh:
        manifest = json.load(fh)
    split_by_issue = {n: "train" for n in splits["train"]}
    split_by_issue.update({n: "test" for n in splits["test"]})
    for entry in manifest.get("records") or []:
        entry["split"] = split_by_issue.get(entry["issue_number"])
    manifest["splits"] = {
        "file": "data/management/splits.json",
        "method": splits["method"],
        "frozen_at": splits["frozen_at"],
        "counts": splits["counts"],
        "seed": splits.get("seed"),
    }
    with manifest_path.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze management train/test splits.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing splits.json freeze (dangerous).",
    )
    parser.add_argument(
        "--apply-only",
        action="store_true",
        help="Re-stamp clean records from existing splits.json without rebuilding.",
    )
    args = parser.parse_args()

    records = load_records()
    if not records:
        raise SystemExit(f"No clean records in {CLEAN_DIR}")

    if args.apply_only:
        if not SPLITS_FILE.exists():
            raise SystemExit(f"Missing {SPLITS_FILE}; run without --apply-only first.")
        with SPLITS_FILE.open(encoding="utf-8") as fh:
            splits = json.load(fh)
        apply_splits(records, splits)
        update_manifest(splits)
        print(f"Re-applied splits from {SPLITS_FILE}")
        print(f"train={splits['counts']['train']} test={splits['counts']['test']}")
        return 0

    if SPLITS_FILE.exists() and SPLITS_FILE.stat().st_size > 0 and not args.force:
        raise SystemExit(
            f"{SPLITS_FILE} already exists. Refusing to overwrite the freeze.\n"
            "Use --apply-only to re-stamp clean records, or --force to rebuild (not recommended)."
        )

    splits = build_splits(records)
    with SPLITS_FILE.open("w", encoding="utf-8") as fh:
        json.dump(splits, fh, indent=2)
        fh.write("\n")

    apply_splits(records, splits)
    update_manifest(splits)

    print(f"Froze splits → {SPLITS_FILE}")
    print(
        f"eligible={splits['counts']['eligible']} "
        f"train={splits['counts']['train']} "
        f"test={splits['counts']['test']} "
        f"excluded={splits['counts']['excluded_no_diagnostic_signal']}"
    )
    print(f"seed={splits['seed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
