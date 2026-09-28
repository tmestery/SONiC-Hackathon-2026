#!/usr/bin/env python3
"""
Transform data/swss/raw/ into schema 1.0 records in data/swss/clean/.

Does not modify raw/. See data/swss/format.md for the schema.
"""

from __future__ import annotations

import json
import random
import re
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "swss" / "raw"
CLEAN_DIR = ROOT / "data" / "swss" / "clean"
MANIFEST_FILE = CLEAN_DIR / "manifest.json"
SPLIT_FILE = CLEAN_DIR / "split.json"
SCHEMA_VERSION = "1.0"
SOURCE = "sonic-swss"
SPLIT_SEED = 42
SPLIT_TRAIN_RATIO = 0.75

HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U0001F1E6-\U0001F1FF]+",
)
WS_RE = re.compile(r"[ \t]+\n")
MULTI_NL_RE = re.compile(r"\n{3,}")

IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b"
)
IPV6_RE = re.compile(
    r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b"
)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
SECRET_RE = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|access[_-]?key)\b(\s*[:=]\s*)\S+"
)
HOSTNAME_RE = re.compile(
    r"\b(?:[a-zA-Z0-9-]+\.)+(?:internal|corp|local|lan|lab)\b",
    re.IGNORECASE,
)

SEVERITY_LINE_RE = re.compile(
    r"(?im)^\s*(?:\*{0,2}|#{1,3}\s*)Importance or Severity(?:\*{0,2})?\s*:?\s*(.+)$"
)
# Also match free-form "Severity: Medium" lines used in some sonic-swss issues.
SEVERITY_ALT_RE = re.compile(
    r"(?im)^\s*(?:\*{0,2}|#{1,3}\s*)Severity(?:\*{0,2})?\s*:?\s*(.+)$"
)
PLATFORM_LINE_RE = re.compile(
    r"(?im)^\s*(?:\*{0,2}|#{1,3}\s*)Is it platform specific(?:\*{0,2})?\s*:?\s*(.+)$"
)
PLATFORM_ALT_RE = re.compile(
    r"(?im)^\s*(?:\*{0,2}|#{1,3}\s*)Platform(?:\*{0,2})?\s*:?\s*(.+)$"
)

DIAGNOSTIC_RE = re.compile(
    r"(?i)\b(error|traceback|exception|assert|assertionerror|failed|failure|fatal|"
    r"panic|segfault|core dump|coredump|crash|timeout|not found|unable to|"
    r"show techsupport|show version|orchagent|syncd|swss#|sairedis|valgrind|"
    r"asan|sanitizer|deadlock|memory leak)\b|"
    r"\bFAILED\b"
)

PRIORITY_LABELS = {"P0", "P1", "P2", "P3"}
ISSUE_TYPE_RANK = {
    "bug": 0,
    "regression": 1,
    "enhancement": 2,
    "build": 3,
    "question": 4,
}

CONSUMED_TOPIC_LABELS = {
    "triaged",
    "pending triage",
    "p0",
    "p1",
    "p2",
    "p3",
    "bug",
    "enhancement",
    "regression",
    "build",
    "question",
    "help wanted",
    "awaiting info",
    "feature request",
    "testing",
    "cleanup",
    "docs",
}

PLATFORM_FROM_LABEL = {
    "brcm": "broadcom",
    "brcmsai": "broadcom",
    "broadcom": "broadcom",
    "nvidia": "nvidia",
    "mellanox": "mellanox",
    "cisco": "cisco",
    "arista": "arista",
    "nokia": "nokia",
    "dellemc": "dellemc",
    "dell": "dellemc",
    "celestica": "celestica",
    "micas": "micas",
    "marvell": "marvell",
    "intel": "intel",
    "sonic-vpp": "vpp",
    "vpp": "vpp",
    "vs": "vs",
    "virtual switch": "vs",
    "kvm": "kvm",
    "super micro": "supermicro",
    "dvs": "vs",
}

GENERIC_PLATFORM_RE = re.compile(r"(?i)\b(generic|no|n/?a|not specific|none)\b")


def strip_html_comments(text: str) -> str:
    text = HTML_COMMENT_RE.sub("", text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = WS_RE.sub("\n", text)
    text = MULTI_NL_RE.sub("\n\n", text)
    return text.strip()


SHORTCODE_RE = re.compile(r":[a-z0-9_+-]+:", re.IGNORECASE)


def strip_emoji(text: str) -> str:
    text = SHORTCODE_RE.sub("", text)
    return EMOJI_RE.sub("", text).strip()


def normalize_label(label: str) -> str:
    label = strip_emoji(label)
    label = re.sub(r"\s+", " ", label).strip(" :-")
    return label


def scrub(text: str) -> str:
    text = IPV4_RE.sub("<IP>", text)
    text = IPV6_RE.sub("<IPV6>", text)
    text = EMAIL_RE.sub("<EMAIL>", text)
    text = HOSTNAME_RE.sub("<HOSTNAME>", text)
    text = SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}<REDACTED>", text)
    return text


def first_token(value: str) -> str:
    value = value.strip().strip("*").strip()
    value = re.split(r"[—\-–:,;(]", value, maxsplit=1)[0]
    return value.strip().lower()


def parse_severity(body: str, labels: list[str]) -> str | None:
    for pattern in (SEVERITY_LINE_RE, SEVERITY_ALT_RE):
        match = pattern.search(body)
        if match:
            token = first_token(match.group(1))
            for level in ("critical", "high", "medium", "low"):
                if token == level or token.startswith(level):
                    return level
    for label in labels:
        if normalize_label(label).lower() == "critical":
            return "critical"
    return None


def parse_platform_from_body(body: str) -> str | None:
    for pattern in (PLATFORM_LINE_RE, PLATFORM_ALT_RE):
        match = pattern.search(body)
        if not match:
            continue
        token = first_token(match.group(1))
        if not token or token in {":", "-", "n/a"}:
            continue
        if GENERIC_PLATFORM_RE.search(token):
            return "generic"
        mapped = PLATFORM_FROM_LABEL.get(token)
        if mapped:
            return mapped
        if re.fullmatch(r"[a-z0-9][a-z0-9._/-]{0,40}", token):
            return token
    return None


def parse_platform_from_labels(labels: list[str]) -> str | None:
    for label in labels:
        raw = normalize_label(label)
        lower = raw.lower()
        if lower.startswith("platform:"):
            name = raw.split(":", 1)[1].strip().lower()
            return PLATFORM_FROM_LABEL.get(name, name.replace(" ", "-"))
        if lower in PLATFORM_FROM_LABEL:
            return PLATFORM_FROM_LABEL[lower]
    return None


def parse_priority(labels: list[str]) -> str | None:
    found = [normalize_label(lab) for lab in labels if normalize_label(lab) in PRIORITY_LABELS]
    if not found:
        return None
    return sorted(found)[0]


def parse_issue_type(labels: list[str]) -> str | None:
    types: list[str] = []
    for label in labels:
        name = normalize_label(label).lower()
        if name in ISSUE_TYPE_RANK:
            types.append(name)
        elif name == "feature request":
            types.append("enhancement")
    if not types:
        return None
    return sorted(types, key=lambda t: ISSUE_TYPE_RANK[t])[0]


def parse_target_releases(labels: list[str]) -> list[str]:
    releases: list[str] = []
    seen: set[str] = set()
    for label in labels:
        name = normalize_label(label)
        lower = name.lower()
        if "master branch" in lower:
            if "master" not in seen:
                releases.append("master")
                seen.add("master")
            continue
        match = re.search(r"(?:issue|issues|request|included)\s+for\s+(\d{6})", lower)
        if match:
            rel = match.group(1)
            if rel not in seen:
                releases.append(rel)
                seen.add(rel)
            continue
        match = re.search(r"request for (\d{6}) branch", lower)
        if match:
            rel = match.group(1)
            if rel not in seen:
                releases.append(rel)
                seen.add(rel)
            continue
        match = re.search(r"included in (\d{6}) branch", lower)
        if match:
            rel = match.group(1)
            if rel not in seen:
                releases.append(rel)
                seen.add(rel)
            continue
        match = re.search(r"^(\d{6,8})\s+issue$", lower)
        if match:
            rel = match.group(1)[:6]
            if rel not in seen:
                releases.append(rel)
                seen.add(rel)
    return releases


def is_consumed_label(label: str) -> bool:
    name = normalize_label(label)
    lower = name.lower()
    if lower in CONSUMED_TOPIC_LABELS:
        return True
    if name in PRIORITY_LABELS:
        return True
    if lower.startswith("platform:"):
        return True
    if lower in PLATFORM_FROM_LABEL:
        return True
    if "master branch" in lower:
        return True
    if re.search(r"(?:issue|issues|request|included)\s+for\s+\d{6}", lower):
        return True
    if re.search(r"(?:request for|included in)\s+\d{6}\s+branch", lower):
        return True
    if re.search(r"^\d{6,8}\s+issue$", lower):
        return True
    return False


def parse_topics(labels: list[str]) -> list[str]:
    topics: list[str] = []
    seen: set[str] = set()
    for label in labels:
        if is_consumed_label(label):
            continue
        name = normalize_label(label)
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        topics.append(name)
    return topics


def select_primary_pr(prs: list[dict]) -> dict | None:
    merged = [pr for pr in prs if pr.get("merged")]
    if not merged:
        return None

    def sort_key(pr: dict) -> str:
        return pr.get("mergedAt") or ""

    return max(merged, key=sort_key)


def has_diagnostic_signal(body: str) -> bool:
    return bool(DIAGNOSTIC_RE.search(body or ""))


def related_pr_entry(pr: dict) -> dict:
    return {
        "pr_number": pr.get("number"),
        "repository": pr.get("repository"),
        "url": pr.get("url"),
        "title": pr.get("title"),
        "merged": bool(pr.get("merged")),
    }


def clean_issue(raw: dict) -> dict | None:
    prs = raw.get("linkedPullRequests") or []
    primary = select_primary_pr(prs)
    if primary is None:
        return None

    description = scrub(strip_html_comments(primary.get("body") or ""))
    if not description:
        return None

    failure_body = scrub(strip_html_comments(raw.get("body") or ""))
    labels = raw.get("labels") or []

    platform = parse_platform_from_body(raw.get("body") or "")
    if platform is None:
        platform = parse_platform_from_labels(labels)

    number = raw["number"]
    related = [related_pr_entry(pr) for pr in prs if pr.get("number") != primary.get("number")]

    files = []
    for item in primary.get("files") or []:
        files.append(
            {
                "path": item.get("path"),
                "additions": item.get("additions"),
                "deletions": item.get("deletions"),
            }
        )

    return {
        "id": f"swss-{number}",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "issue": {
            "number": number,
            "url": raw.get("url"),
            "title": raw.get("title"),
            "created_at": raw.get("createdAt"),
            "closed_at": raw.get("closedAt"),
        },
        "metadata": {
            "severity": parse_severity(raw.get("body") or "", labels),
            "priority": parse_priority(labels),
            "issue_type": parse_issue_type(labels),
            "platform": platform,
            "target_releases": parse_target_releases(labels),
            "topics": parse_topics(labels),
        },
        "failure": {
            "body": failure_body,
        },
        "resolution": {
            "pr_number": primary.get("number"),
            "repository": primary.get("repository"),
            "url": primary.get("url"),
            "title": primary.get("title"),
            "merged_at": primary.get("mergedAt"),
            "description": description,
            "files": files,
        },
        "related_prs": related,
        "quality": {
            "has_diagnostic_signal": has_diagnostic_signal(failure_body),
            "notes": None,
        },
        "split": None,
    }


def assign_splits(records: list[dict]) -> dict[str, str]:
    """Deterministically assign train/test to records with diagnostic signal.

    Records without diagnostic signal are excluded from train/val/test
    (see format.md) and keep split == None.
    """
    eligible_ids = sorted(
        (r["id"] for r in records if r["quality"]["has_diagnostic_signal"])
    )
    shuffled = eligible_ids[:]
    random.Random(SPLIT_SEED).shuffle(shuffled)

    train_count = round(len(shuffled) * SPLIT_TRAIN_RATIO)
    train_ids = set(shuffled[:train_count])

    return {rid: ("train" if rid in train_ids else "test") for rid in eligible_ids}


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    for old in CLEAN_DIR.glob("issue-*.json"):
        old.unlink()

    raw_files = sorted(RAW_DIR.glob("issue-*.json"), key=lambda p: int(p.stem.split("-")[1]))
    records = []
    skipped_no_merged = 0
    skipped_empty_desc = 0

    start = time.time()
    for path in raw_files:
        with path.open(encoding="utf-8") as fh:
            raw = json.load(fh)
        record = clean_issue(raw)
        if record is None:
            prs = raw.get("linkedPullRequests") or []
            if not any(pr.get("merged") for pr in prs):
                skipped_no_merged += 1
            else:
                skipped_empty_desc += 1
            continue
        records.append(record)

    split_assignments = assign_splits(records)

    written = []
    severity_counts = Counter()
    priority_counts = Counter()
    type_counts = Counter()
    diagnostic_true = 0

    for record in records:
        record["split"] = split_assignments.get(record["id"])

        out = CLEAN_DIR / f"issue-{record['issue']['number']}.json"
        with out.open("w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2)
            fh.write("\n")

        written.append(
            {
                "id": record["id"],
                "issue_number": record["issue"]["number"],
                "pr_number": record["resolution"]["pr_number"],
                "repository": record["resolution"]["repository"],
                "severity": record["metadata"]["severity"],
                "priority": record["metadata"]["priority"],
                "issue_type": record["metadata"]["issue_type"],
                "has_diagnostic_signal": record["quality"]["has_diagnostic_signal"],
                "split": record["split"],
            }
        )
        severity_counts[record["metadata"]["severity"] or "null"] += 1
        priority_counts[record["metadata"]["priority"] or "null"] += 1
        type_counts[record["metadata"]["issue_type"] or "null"] += 1
        if record["quality"]["has_diagnostic_signal"]:
            diagnostic_true += 1

    split_counts = Counter(split_assignments.values())

    manifest = {
        "source": SOURCE,
        "schema_version": SCHEMA_VERSION,
        "cleaned_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "raw_issues_examined": len(raw_files),
        "clean_records_written": len(written),
        "skipped_no_merged_pr": skipped_no_merged,
        "skipped_empty_pr_description": skipped_empty_desc,
        "counts": {
            "severity": dict(severity_counts),
            "priority": dict(priority_counts),
            "issue_type": dict(type_counts),
            "has_diagnostic_signal": diagnostic_true,
            "no_diagnostic_signal": len(written) - diagnostic_true,
            "split": {
                "train": split_counts.get("train", 0),
                "test": split_counts.get("test", 0),
                "excluded": len(written) - len(split_assignments),
            },
        },
        "records": written,
    }
    with MANIFEST_FILE.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")

    split_manifest = {
        "source": SOURCE,
        "schema_version": SCHEMA_VERSION,
        "seed": SPLIT_SEED,
        "train_ratio": SPLIT_TRAIN_RATIO,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "total_records": len(written),
        "eligible_for_split": len(split_assignments),
        "excluded_no_diagnostic_signal": len(written) - len(split_assignments),
        "counts": {
            "train": split_counts.get("train", 0),
            "test": split_counts.get("test", 0),
        },
        "assignments": {
            record["id"]: record["split"] for record in records
        },
    }
    with SPLIT_FILE.open("w", encoding="utf-8") as fh:
        json.dump(split_manifest, fh, indent=2)
        fh.write("\n")

    elapsed = time.time() - start
    print(f"Cleaned {len(written)} records in {elapsed:.1f}s")
    print(f"Skipped no merged PR: {skipped_no_merged}")
    print(f"Skipped empty PR description: {skipped_empty_desc}")
    print(f"Diagnostic signal: {diagnostic_true}/{len(written)}")
    print(f"Split: train={split_counts.get('train', 0)} test={split_counts.get('test', 0)} excluded={len(written) - len(split_assignments)}")
    print(f"Manifest: {MANIFEST_FILE}")
    print(f"Split file: {SPLIT_FILE}")


if __name__ == "__main__":
    main()
