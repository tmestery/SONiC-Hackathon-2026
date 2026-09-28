#!/usr/bin/env python3
"""
Report how often clean sonic-mgmt records share the same primary resolving PR.

Primary PR = resolution.repository + resolution.pr_number (schema 1.0).

Writes a Markdown report (default: data/management/shared_pr_report.md)
and prints a short summary to stdout.

Usage:
  python scripts/management/report_shared_prs.py
  python scripts/management/report_shared_prs.py --out path/to/report.md
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLEAN_DIR = ROOT / "data" / "management" / "clean"
DEFAULT_OUT = ROOT / "data" / "management" / "shared_pr_report.md"


def load_records(clean_dir: Path) -> list[dict]:
    records = []
    for path in sorted(clean_dir.glob("issue-*.json"), key=lambda p: int(p.stem.split("-")[1])):
        with path.open(encoding="utf-8") as fh:
            records.append(json.load(fh))
    return records


def pr_key(repository: str | None, pr_number: int | None) -> str:
    repo = repository or "unknown"
    return f"{repo}#{pr_number}"


def analyze(records: list[dict]) -> dict:
    by_pr: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        res = record.get("resolution") or {}
        key = pr_key(res.get("repository"), res.get("pr_number"))
        by_pr[key].append(record)

    shared = {k: v for k, v in by_pr.items() if len(v) > 1}
    unique_only = {k: v for k, v in by_pr.items() if len(v) == 1}

    size_hist = Counter(len(v) for v in by_pr.values())
    issues_on_shared = sum(len(v) for v in shared.values())

    # Split membership for shared groups
    split_counts = Counter()
    for group in shared.values():
        for rec in group:
            split_counts[rec.get("split") or "null"] += 1

    # related_prs: how often another clean issue's primary PR appears as related
    primary_keys = set(by_pr.keys())
    related_hits: list[dict] = []
    for record in records:
        issue_n = record["issue"]["number"]
        primary = pr_key(
            (record.get("resolution") or {}).get("repository"),
            (record.get("resolution") or {}).get("pr_number"),
        )
        for related in record.get("related_prs") or []:
            rkey = pr_key(related.get("repository"), related.get("pr_number"))
            if rkey in primary_keys and rkey != primary:
                related_hits.append(
                    {
                        "issue": issue_n,
                        "primary_pr": primary,
                        "related_pr": rkey,
                        "related_is_shared_primary": rkey in shared,
                    }
                )

    groups = []
    for key, group in sorted(shared.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        res0 = group[0].get("resolution") or {}
        groups.append(
            {
                "pr_key": key,
                "repository": res0.get("repository"),
                "pr_number": res0.get("pr_number"),
                "pr_url": res0.get("url"),
                "pr_title": res0.get("title"),
                "merged_at": res0.get("merged_at"),
                "issue_count": len(group),
                "issues": [
                    {
                        "number": r["issue"]["number"],
                        "title": r["issue"].get("title"),
                        "url": r["issue"].get("url"),
                        "closed_at": r["issue"].get("closed_at"),
                        "split": r.get("split"),
                        "has_diagnostic_signal": (r.get("quality") or {}).get(
                            "has_diagnostic_signal"
                        ),
                        "issue_type": (r.get("metadata") or {}).get("issue_type"),
                    }
                    for r in sorted(group, key=lambda r: r["issue"]["number"])
                ],
            }
        )

    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "source": "sonic-mgmt",
        "clean_dir": str(CLEAN_DIR.relative_to(ROOT)).replace("\\", "/"),
        "totals": {
            "clean_records": len(records),
            "unique_primary_prs": len(by_pr),
            "prs_used_by_exactly_one_issue": len(unique_only),
            "prs_shared_by_two_or_more_issues": len(shared),
            "issues_pointing_at_a_shared_pr": issues_on_shared,
            "issues_with_unique_primary_pr": len(records) - issues_on_shared,
            "pct_issues_on_shared_pr": round(100.0 * issues_on_shared / len(records), 2)
            if records
            else 0.0,
            "pct_prs_that_are_shared": round(100.0 * len(shared) / len(by_pr), 2)
            if by_pr
            else 0.0,
        },
        "issues_per_pr_histogram": dict(sorted(size_hist.items())),
        "shared_issue_split_counts": dict(split_counts),
        "related_pr_cross_links": {
            "count": len(related_hits),
            "examples": related_hits[:25],
        },
        "shared_groups": groups,
    }


def render_markdown(report: dict) -> str:
    t = report["totals"]
    lines: list[str] = []
    lines.append("# sonic-mgmt shared primary-PR report")
    lines.append("")
    lines.append(f"Generated: `{report['generated_at']}`")
    lines.append(f"Source records: `{report['clean_dir']}/issue-*.json`")
    lines.append("")
    lines.append(
        "A **shared primary PR** means two or more clean records list the same "
        "`resolution.repository` + `resolution.pr_number` (the resolving PR chosen "
        "during cleaning)."
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    lines.append(f"| Clean records | {t['clean_records']} |")
    lines.append(f"| Unique primary PRs | {t['unique_primary_prs']} |")
    lines.append(
        f"| PRs used by exactly one issue | {t['prs_used_by_exactly_one_issue']} |"
    )
    lines.append(
        f"| PRs shared by 2+ issues | {t['prs_shared_by_two_or_more_issues']} |"
    )
    lines.append(
        f"| Issues pointing at a shared PR | {t['issues_pointing_at_a_shared_pr']} "
        f"({t['pct_issues_on_shared_pr']}%) |"
    )
    lines.append(
        f"| Issues with a unique primary PR | {t['issues_with_unique_primary_pr']} |"
    )
    lines.append(
        f"| Share of PRs that are multi-issue | {t['pct_prs_that_are_shared']}% |"
    )
    lines.append("")
    lines.append("## Issues-per-PR histogram")
    lines.append("")
    lines.append("| Issues sharing a PR | Number of PRs |")
    lines.append("| ---: | ---: |")
    for size, count in report["issues_per_pr_histogram"].items():
        lines.append(f"| {size} | {count} |")
    lines.append("")

    if report["shared_issue_split_counts"]:
        lines.append("## Split membership of issues on shared PRs")
        lines.append("")
        lines.append("| `split` | Issues |")
        lines.append("| --- | ---: |")
        for split, count in sorted(report["shared_issue_split_counts"].items()):
            lines.append(f"| `{split}` | {count} |")
        lines.append("")

    related = report["related_pr_cross_links"]
    lines.append("## Related-PR cross-links")
    lines.append("")
    lines.append(
        f"Cases where an issue's `related_prs` entry is another clean record's "
        f"primary PR: **{related['count']}**."
    )
    lines.append("")
    if related["examples"]:
        lines.append("| Issue | Primary PR | Related PR (also a primary elsewhere) |")
        lines.append("| ---: | --- | --- |")
        for ex in related["examples"]:
            lines.append(
                f"| {ex['issue']} | `{ex['primary_pr']}` | `{ex['related_pr']}` |"
            )
        if related["count"] > len(related["examples"]):
            lines.append("")
            lines.append(
                f"_Showing {len(related['examples'])} of {related['count']} "
                f"cross-links._"
            )
        lines.append("")

    lines.append("## Shared PR groups (full list)")
    lines.append("")
    if not report["shared_groups"]:
        lines.append("No shared primary PRs found.")
        lines.append("")
        return "\n".join(lines)

    for group in report["shared_groups"]:
        title = group.get("pr_title") or "(no title)"
        url = group.get("pr_url") or ""
        lines.append(
            f"### `{group['pr_key']}` — {group['issue_count']} issues"
        )
        lines.append("")
        if url:
            lines.append(f"- PR: [{title}]({url})")
        else:
            lines.append(f"- PR title: {title}")
        lines.append(f"- Merged at: `{group.get('merged_at')}`")
        lines.append("")
        lines.append("| Issue | Split | Diagnostic | Type | Title |")
        lines.append("| ---: | --- | --- | --- | --- |")
        for issue in group["issues"]:
            issue_link = f"[{issue['number']}]({issue['url']})" if issue.get("url") else str(issue["number"])
            title_cell = (issue.get("title") or "").replace("|", "\\|")
            split_val = issue.get("split")
            split_cell = "null" if split_val is None else split_val
            type_val = issue.get("issue_type")
            type_cell = "null" if type_val is None else type_val
            lines.append(
                f"| {issue_link} | `{split_cell}` | "
                f"{issue.get('has_diagnostic_signal')} | "
                f"`{type_cell}` | {title_cell} |"
            )
        lines.append("")

    lines.append("## Takeaways")
    lines.append("")
    lines.append(
        f"- Most resolving PRs are 1:1 with issues "
        f"({t['prs_used_by_exactly_one_issue']}/{t['unique_primary_prs']} PRs)."
    )
    lines.append(
        f"- {t['prs_shared_by_two_or_more_issues']} PRs close multiple tracked issues; "
        f"those PRs cover {t['issues_pointing_at_a_shared_pr']} clean records "
        f"({t['pct_issues_on_shared_pr']}%)."
    )
    lines.append(
        "- Shared primaries usually mean one fix closed several related tickets "
        "(same root cause / batch tracking). For training, duplicate resolution "
        "text across those issues can overweight that PR's wording."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report clean records that share the same primary resolving PR."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Markdown report path (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Optional path to also write the raw analysis JSON.",
    )
    args = parser.parse_args()

    records = load_records(CLEAN_DIR)
    if not records:
        raise SystemExit(f"No clean records in {CLEAN_DIR}")

    report = analyze(records)
    markdown = render_markdown(report)

    out_path: Path = args.out
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")

    if args.json:
        json_path = args.json if args.json.is_absolute() else ROOT / args.json
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with json_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
            fh.write("\n")

    t = report["totals"]
    print(f"Clean records: {t['clean_records']}")
    print(f"Unique primary PRs: {t['unique_primary_prs']}")
    print(f"Shared PRs (2+ issues): {t['prs_shared_by_two_or_more_issues']}")
    print(
        f"Issues on shared PRs: {t['issues_pointing_at_a_shared_pr']} "
        f"({t['pct_issues_on_shared_pr']}%)"
    )
    print(f"Histogram (issues-per-PR → #PRs): {report['issues_per_pr_histogram']}")
    print(f"Wrote report: {out_path}")
    if args.json:
        print(f"Wrote JSON: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
