#!/usr/bin/env python3
"""
Publish the frozen SONiC RCA train/test splits as a Hugging Face dataset.

Default repo: <hf-username>/sonic-rca-benchmark

Usage (from repo root, venv active):
  python scripts/publish_hf_benchmark.py
  python scripts/publish_hf_benchmark.py --repo-id tmesttttttttt/sonic-rca-benchmark --private
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from datasets import Dataset, DatasetDict, Features, Sequence, Value
from huggingface_hub import HfApi, whoami

ROOT = Path(__file__).resolve().parents[1]
SPLITS_FILE = ROOT / "data" / "splits.json"
SOURCE_DIRS = {
    "sonic-buildimage": ROOT / "data" / "buildimage" / "clean",
    "sonic-mgmt": ROOT / "data" / "management" / "clean",
    "sonic-swss": ROOT / "data" / "swss" / "clean",
}
PREFIX_DIRS = {
    "buildimage": ROOT / "data" / "buildimage" / "clean",
    "management": ROOT / "data" / "management" / "clean",
    "swss": ROOT / "data" / "swss" / "clean",
}

FEATURES = Features(
    {
        "id": Value("string"),
        "source": Value("string"),
        "split": Value("string"),
        "issue_number": Value("int64"),
        "issue_url": Value("string"),
        "issue_title": Value("string"),
        "issue_created_at": Value("string"),
        "issue_closed_at": Value("string"),
        "failure_body": Value("string"),
        "gold_description": Value("string"),
        "resolution_pr_number": Value("int64"),
        "resolution_repository": Value("string"),
        "resolution_url": Value("string"),
        "resolution_title": Value("string"),
        "resolution_merged_at": Value("string"),
        "resolution_files": [
            {
                "path": Value("string"),
                "additions": Value("int64"),
                "deletions": Value("int64"),
            }
        ],
        "severity": Value("string"),
        "priority": Value("string"),
        "issue_type": Value("string"),
        "platform": Value("string"),
        "target_releases": Sequence(Value("string")),
        "topics": Sequence(Value("string")),
        "has_diagnostic_signal": Value("bool"),
    }
)

DATASET_CARD = """---
language:
- en
license: apache-2.0
task_categories:
- text-generation
- question-answering
pretty_name: SONiC RCA Benchmark
tags:
- sonic
- networking
- root-cause-analysis
- benchmark
- llm
- slm
size_categories:
- 1K<n<10K
---

# SONiC RCA Benchmark

Public benchmark for **automated root-cause analysis of [SONiC](https://sonicfoundation.dev/) test failures**.

Given an issue title + failure report, a model must produce a diagnosis / fix explanation in the style of a resolving pull-request description. Gold labels are the cleaned PR descriptions from real merged fixes.

## Task

| Role | Field |
|---|---|
| **Input** | `issue_title` + `failure_body` |
| **Output (gold)** | `gold_description` (`resolution.description`) |
| **Holdout** | `test` split — **do not train on it** |

Optional retrieval context may come from SONiC docs (see the companion GitHub repo); this dataset contains the labeled failure↔fix pairs only.

## Splits (frozen)

Temporal holdout over records with `has_diagnostic_signal=true` from:

- [sonic-buildimage](https://github.com/sonic-net/sonic-buildimage)
- [sonic-mgmt](https://github.com/sonic-net/sonic-mgmt)
- [sonic-swss](https://github.com/sonic-net/sonic-swss)

Sorted by `issue_closed_at` (oldest → newest): **oldest 75% → train**, **newest 25% → test**.

| Split | Count |
|---|---|
| train | {train_n} |
| test | {test_n} |

Frozen at: `{frozen_at}`

## Scoring

The reference harness scores model predictions against `gold_description` with LLM judges (root cause, fix approach, diagnostic fidelity) on a 0–1 scale. See the GitHub evaluation package for the exact prompts and protocol.

## Load

```python
from datasets import load_dataset

ds = load_dataset("tmesttttttttt/sonic-rca-benchmark")
print(ds["train"][0]["issue_title"])
print(ds["test"][0]["gold_description"][:200])
```

## Source code

- Dataset + eval harness: [tmestery/SONiC-RCA](https://github.com/tmestery/SONiC-RCA) (SONiC Hackathon 2026)

## Citation

```bibtex
@misc{{sonic-rca-benchmark-2026,
  title  = {{SONiC RCA Benchmark}},
  author = {{Mestery, Tyler and Hart, Mason and Pham, Andy}},
  year   = {{2026}},
  url    = {{https://huggingface.co/datasets/{repo_id}}}
}}
```
"""


def record_path_for_id(record_id: str) -> Path:
    prefix, _, num = record_id.partition("-")
    if prefix not in PREFIX_DIRS or not num.isdigit():
        raise ValueError(f"Bad record id: {record_id!r}")
    return PREFIX_DIRS[prefix] / f"issue-{num}.json"


def _str_or_empty(value: Any) -> str:
    return "" if value is None else str(value)


def _int_or_neg1(value: Any) -> int:
    if value is None or value == "":
        return -1
    return int(value)


def flatten(record: dict[str, Any]) -> dict[str, Any]:
    issue = record.get("issue") or {}
    failure = record.get("failure") or {}
    resolution = record.get("resolution") or {}
    metadata = record.get("metadata") or {}
    quality = record.get("quality") or {}
    files_raw = resolution.get("files") or []
    files = []
    for item in files_raw:
        if not isinstance(item, dict):
            continue
        files.append(
            {
                "path": _str_or_empty(item.get("path")),
                "additions": _int_or_neg1(item.get("additions")),
                "deletions": _int_or_neg1(item.get("deletions")),
            }
        )
    return {
        "id": record["id"],
        "source": _str_or_empty(record.get("source")),
        "split": _str_or_empty(record.get("split")),
        "issue_number": _int_or_neg1(issue.get("number")),
        "issue_url": _str_or_empty(issue.get("url")),
        "issue_title": _str_or_empty(issue.get("title")),
        "issue_created_at": _str_or_empty(issue.get("created_at")),
        "issue_closed_at": _str_or_empty(issue.get("closed_at")),
        "failure_body": _str_or_empty(failure.get("body")),
        "gold_description": _str_or_empty(resolution.get("description")),
        "resolution_pr_number": _int_or_neg1(resolution.get("pr_number")),
        "resolution_repository": _str_or_empty(resolution.get("repository")),
        "resolution_url": _str_or_empty(resolution.get("url")),
        "resolution_title": _str_or_empty(resolution.get("title")),
        "resolution_merged_at": _str_or_empty(resolution.get("merged_at")),
        "resolution_files": files,
        "severity": _str_or_empty(metadata.get("severity")),
        "priority": _str_or_empty(metadata.get("priority")),
        "issue_type": _str_or_empty(metadata.get("issue_type")),
        "platform": _str_or_empty(metadata.get("platform")),
        "target_releases": list(metadata.get("target_releases") or []),
        "topics": list(metadata.get("topics") or []),
        "has_diagnostic_signal": bool(quality.get("has_diagnostic_signal")),
    }


def load_split_rows(ids: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for record_id in ids:
        path = record_path_for_id(record_id)
        if not path.exists():
            missing.append(record_id)
            continue
        with path.open(encoding="utf-8") as fh:
            record = json.load(fh)
        rows.append(flatten(record))
    if missing:
        preview = ", ".join(missing[:10])
        raise SystemExit(f"Missing {len(missing)} clean records (e.g. {preview})")
    return rows


def build_dataset(splits_file: Path) -> tuple[DatasetDict, dict[str, Any]]:
    with splits_file.open(encoding="utf-8") as fh:
        splits = json.load(fh)
    train_rows = load_split_rows(list(splits.get("train") or []))
    test_rows = load_split_rows(list(splits.get("test") or []))
    ds = DatasetDict(
        {
            "train": Dataset.from_list(train_rows, features=FEATURES),
            "test": Dataset.from_list(test_rows, features=FEATURES),
        }
    )
    return ds, splits


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-id",
        default=None,
        help="HF dataset repo id (default: <you>/sonic-rca-benchmark)",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="Create/update as a private dataset",
    )
    parser.add_argument(
        "--splits-file",
        type=Path,
        default=SPLITS_FILE,
        help=f"Path to splits.json (default: {SPLITS_FILE})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    info = whoami()
    username = info.get("name") or info.get("fullname")
    if not username:
        raise SystemExit("Could not resolve Hugging Face username (hf auth login?)")
    repo_id = args.repo_id or f"{username}/sonic-rca-benchmark"

    print(f"Building dataset from {args.splits_file} …")
    ds, splits = build_dataset(args.splits_file)
    print(f"  train={len(ds['train'])}  test={len(ds['test'])}")

    card = DATASET_CARD.format(
        train_n=len(ds["train"]),
        test_n=len(ds["test"]),
        frozen_at=splits.get("frozen_at") or "unknown",
        repo_id=repo_id,
    )

    api = HfApi()
    api.create_repo(
        repo_id=repo_id,
        repo_type="dataset",
        private=args.private,
        exist_ok=True,
    )
    print(f"Pushing to https://huggingface.co/datasets/{repo_id} …")
    ds.push_to_hub(repo_id, private=args.private)
    api.upload_file(
        path_or_fileobj=card.encode("utf-8"),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="dataset",
        commit_message="Add / update SONiC RCA benchmark dataset card",
    )
    # Preserve freeze metadata next to the parquet shards.
    meta = {
        "schema_version": splits.get("schema_version"),
        "sources": splits.get("sources"),
        "method": splits.get("method"),
        "description": splits.get("description"),
        "train_ratio": splits.get("train_ratio"),
        "frozen_at": splits.get("frozen_at"),
        "counts": splits.get("counts"),
        "cutoff_closed_at": splits.get("cutoff_closed_at"),
        "github": "https://github.com/tmestery/SONiC-RCA",
    }
    api.upload_file(
        path_or_fileobj=(json.dumps(meta, indent=2) + "\n").encode("utf-8"),
        path_in_repo="splits_meta.json",
        repo_id=repo_id,
        repo_type="dataset",
        commit_message="Add freeze metadata",
    )
    print(f"Done → https://huggingface.co/datasets/{repo_id}")


if __name__ == "__main__":
    main()
