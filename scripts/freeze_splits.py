#!/usr/bin/env python3
"""
Freeze a combined train/test split across buildimage, management, and swss.

Strategy:
  - Eligible: quality.has_diagnostic_signal == true
  - Sort by issue.closed_at (fallback created_at), oldest → newest
  - Oldest 75% → train, newest 25% → test (temporal holdout)
  - Non-diagnostic records get split: null (excluded from both)

Writes:
  - data/splits.json  (source of truth; lists record ids)
  - data/manifest.json (aggregate of all clean records)

Also stamps each data/<dataset>/clean/issue-*.json and updates that
dataset's clean/manifest.json.

Re-run is refused unless --force. Use --apply-only to re-stamp from an
existing freeze without rebuilding.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SPLITS_FILE = DATA_DIR / "splits.json"
MANIFEST_FILE = DATA_DIR / "manifest.json"
TRAIN_RATIO = 0.75

DATASETS = (
    ("sonic-buildimage", DATA_DIR / "buildimage" / "clean"),
    ("sonic-mgmt", DATA_DIR / "management" / "clean"),
    ("sonic-swss", DATA_DIR / "swss" / "clean"),
)


def splits_file_ready(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def load_dataset_records(clean_dir: Path) -> list[tuple[Path, dict]]:
    loaded: list[tuple[Path, dict]] = []
    for path in sorted(clean_dir.glob("issue-*.json"), key=lambda p: int(p.stem.split("-")[1])):
        with path.open(encoding="utf-8") as fh:
            loaded.append((path, json.load(fh)))
    return loaded


def load_all_records() -> list[tuple[Path, dict]]:
    records: list[tuple[Path, dict]] = []
    for _source, clean_dir in DATASETS:
        if not clean_dir.exists():
            continue
        records.extend(load_dataset_records(clean_dir))
    return records


def sort_key(record: dict) -> tuple[str, str]:
    issue = record.get("issue") or {}
    closed = issue.get("closed_at") or issue.get("created_at") or ""
    return (closed, record.get("id") or "")


def source_counts(records: list[dict], train_ids: set[str], test_ids: set[str]) -> dict:
    by_source: dict[str, Counter] = {}
    for record in records:
        source = record.get("source") or "unknown"
        counts = by_source.setdefault(
            source,
            Counter(eligible=0, train=0, test=0, excluded_no_diagnostic_signal=0),
        )
        rid = record.get("id")
        diagnostic = bool((record.get("quality") or {}).get("has_diagnostic_signal"))
        if not diagnostic:
            counts["excluded_no_diagnostic_signal"] += 1
            continue
        counts["eligible"] += 1
        if rid in train_ids:
            counts["train"] += 1
        elif rid in test_ids:
            counts["test"] += 1
    return {src: dict(counts) for src, counts in by_source.items()}


def build_splits(records: list[dict]) -> dict:
    eligible = [r for r in records if (r.get("quality") or {}).get("has_diagnostic_signal")]
    eligible.sort(key=sort_key)

    n = len(eligible)
    if n < 2:
        raise SystemExit(f"Need at least 2 diagnostic records to split; found {n}")

    n_train = int(n * TRAIN_RATIO)
    n_train = max(1, min(n - 1, n_train))
    train = eligible[:n_train]
    test = eligible[n_train:]
    train_ids = [r["id"] for r in train]
    test_ids = [r["id"] for r in test]

    return {
        "schema_version": "1.0",
        "sources": [source for source, _ in DATASETS],
        "method": "temporal_closed_at",
        "description": (
            "Eligible records have has_diagnostic_signal=true across "
            "buildimage, management, and swss. "
            "Sorted by issue.closed_at (fallback created_at), oldest first. "
            f"Oldest {TRAIN_RATIO:.0%} → train; newest {1 - TRAIN_RATIO:.0%} → test. "
            "Ids are schema 1.0 record ids (e.g. buildimage-119). "
            "Test is frozen — never train on it."
        ),
        "train_ratio": TRAIN_RATIO,
        "frozen_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "counts": {
            "eligible": n,
            "train": len(train),
            "test": len(test),
            "excluded_no_diagnostic_signal": len(records) - n,
            "by_source": source_counts(records, set(train_ids), set(test_ids)),
        },
        "cutoff_closed_at": test[0]["issue"].get("closed_at") or test[0]["issue"].get("created_at"),
        "train": train_ids,
        "test": test_ids,
    }


def assign_split(record_id: str | None, splits: dict) -> str | None:
    if not record_id:
        return None
    if record_id in (splits.get("train") or []):
        return "train"
    if record_id in (splits.get("test") or []):
        return "test"
    return None


def apply_splits(loaded: list[tuple[Path, dict]], splits: dict) -> None:
    for path, record in loaded:
        record["split"] = assign_split(record.get("id"), splits)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2)
            fh.write("\n")


def update_dataset_manifests(splits: dict) -> None:
    train_set = set(splits.get("train") or [])
    test_set = set(splits.get("test") or [])
    by_source = (splits.get("counts") or {}).get("by_source") or {}
    for source, clean_dir in DATASETS:
        manifest_path = clean_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        with manifest_path.open(encoding="utf-8") as fh:
            manifest = json.load(fh)
        for entry in manifest.get("records") or []:
            rid = entry.get("id")
            if rid in train_set:
                entry["split"] = "train"
            elif rid in test_set:
                entry["split"] = "test"
            else:
                entry["split"] = None
        manifest["splits"] = {
            "file": "data/splits.json",
            "method": splits.get("method"),
            "frozen_at": splits.get("frozen_at"),
            "counts": splits.get("counts"),
            "cutoff_closed_at": splits.get("cutoff_closed_at"),
            "source_counts": by_source.get(source),
        }
        with manifest_path.open("w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
            fh.write("\n")


def write_aggregate_manifest(loaded: list[tuple[Path, dict]], splits: dict) -> None:
    severity = Counter()
    priority = Counter()
    issue_type = Counter()
    diagnostic_true = 0
    records_out = []
    by_source: dict[str, dict] = {}

    for _path, record in loaded:
        source = record.get("source") or "unknown"
        meta = record.get("metadata") or {}
        quality = record.get("quality") or {}
        issue = record.get("issue") or {}
        resolution = record.get("resolution") or {}
        diagnostic = bool(quality.get("has_diagnostic_signal"))
        if diagnostic:
            diagnostic_true += 1
        severity[meta.get("severity") or "null"] += 1
        priority[meta.get("priority") or "null"] += 1
        issue_type[meta.get("issue_type") or "null"] += 1

        records_out.append(
            {
                "id": record.get("id"),
                "source": source,
                "issue_number": issue.get("number"),
                "pr_number": resolution.get("pr_number"),
                "repository": resolution.get("repository"),
                "closed_at": issue.get("closed_at"),
                "severity": meta.get("severity"),
                "priority": meta.get("priority"),
                "issue_type": meta.get("issue_type"),
                "has_diagnostic_signal": diagnostic,
                "split": record.get("split"),
            }
        )

        bucket = by_source.setdefault(
            source,
            {
                "clean_records": 0,
                "has_diagnostic_signal": 0,
            },
        )
        bucket["clean_records"] += 1
        if diagnostic:
            bucket["has_diagnostic_signal"] += 1

    records_out.sort(key=lambda e: (e.get("closed_at") or "", e.get("id") or ""))

    for source, clean_dir in DATASETS:
        local = clean_dir / "manifest.json"
        if not local.exists() or source not in by_source:
            continue
        with local.open(encoding="utf-8") as fh:
            local_manifest = json.load(fh)
        by_source[source]["raw_issues_examined"] = local_manifest.get("raw_issues_examined")
        by_source[source]["skipped_no_merged_pr"] = local_manifest.get("skipped_no_merged_pr")
        by_source[source]["skipped_empty_pr_description"] = local_manifest.get(
            "skipped_empty_pr_description"
        )
        by_source[source]["cleaned_at"] = local_manifest.get("cleaned_at")

    manifest = {
        "schema_version": "1.0",
        "sources": [source for source, _ in DATASETS],
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "splits_file": "data/splits.json",
        "clean_records": len(records_out),
        "counts": {
            "severity": dict(severity),
            "priority": dict(priority),
            "issue_type": dict(issue_type),
            "has_diagnostic_signal": diagnostic_true,
            "no_diagnostic_signal": len(records_out) - diagnostic_true,
            "by_source": by_source,
        },
        "splits": {
            "method": splits.get("method"),
            "frozen_at": splits.get("frozen_at"),
            "counts": splits.get("counts"),
            "cutoff_closed_at": splits.get("cutoff_closed_at"),
        },
        "records": records_out,
    }
    with MANIFEST_FILE.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze combined train/test splits for all labeled datasets."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing data/splits.json freeze (dangerous).",
    )
    parser.add_argument(
        "--apply-only",
        action="store_true",
        help="Re-stamp clean records from existing data/splits.json without rebuilding.",
    )
    args = parser.parse_args()

    loaded = load_all_records()
    if not loaded:
        raise SystemExit("No clean records found under data/{buildimage,management,swss}/clean/")

    records = [record for _path, record in loaded]

    if args.apply_only:
        if not splits_file_ready(SPLITS_FILE):
            raise SystemExit(f"Missing {SPLITS_FILE}; run without --apply-only first.")
        with SPLITS_FILE.open(encoding="utf-8") as fh:
            splits = json.load(fh)
        apply_splits(loaded, splits)
        update_dataset_manifests(splits)
        write_aggregate_manifest(loaded, splits)
        print(f"Re-applied splits from {SPLITS_FILE}")
        print(f"train={splits['counts']['train']} test={splits['counts']['test']}")
        return 0

    if splits_file_ready(SPLITS_FILE) and not args.force:
        raise SystemExit(
            f"{SPLITS_FILE} already exists. Refusing to overwrite the freeze.\n"
            "Use --apply-only to re-stamp clean records, or --force to rebuild (not recommended)."
        )

    splits = build_splits(records)
    with SPLITS_FILE.open("w", encoding="utf-8") as fh:
        json.dump(splits, fh, indent=2)
        fh.write("\n")

    apply_splits(loaded, splits)
    update_dataset_manifests(splits)
    write_aggregate_manifest(loaded, splits)

    print(f"Froze splits → {SPLITS_FILE}")
    print(f"Aggregate manifest → {MANIFEST_FILE}")
    print(
        f"eligible={splits['counts']['eligible']} "
        f"train={splits['counts']['train']} "
        f"test={splits['counts']['test']} "
        f"excluded={splits['counts']['excluded_no_diagnostic_signal']}"
    )
    print(f"test starts at closed_at >= {splits['cutoff_closed_at']}")
    for source, counts in (splits["counts"].get("by_source") or {}).items():
        print(
            f"  {source}: train={counts.get('train')} test={counts.get('test')} "
            f"excluded={counts.get('excluded_no_diagnostic_signal')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
