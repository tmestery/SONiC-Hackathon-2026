# sonic-buildimage Dataset

Dataset mined from [sonic-net/sonic-buildimage](https://github.com/sonic-net/sonic-buildimage), focusing on closed issues that have linked pull requests resolving them.

## Overview

In SONiC, build issues, image configuration regressions, daemon startup failures, and test environment problems are tracked in `sonic-buildimage` issues. When an issue is resolved by a linked pull request, the pair provides:

1. **Failure Signature & Context** (from the Issue): Bug reports, environment details, traceback logs, and reproduction steps.
2. **True Root Cause & Resolution** (from the linked PR): Developer analysis ("Why I did it", "How I did it") in the PR description, plus the files the PR changed.

This pairing is labeled data for SLM **training, validation, and testing**, and for a public benchmark later. It is **not** a RAG corpus. Retrieval context comes only from [`data/rag/`](../rag/).

## Directory Layout

```
data/buildimage/
├── raw/                      # Unprocessed mined data (immutable)
│   ├── issue-<number>.json   # Per-issue raw payload with linked PRs
│   └── manifest.json         # Index of all mined issues and linked PRs
├── clean/                    # Schema 1.0 records for train/val/test
│   ├── issue-<number>.json
│   └── manifest.json
├── format.md                 # Schema for entries in clean/
└── readme.md                 # This documentation
```

See [`format.md`](format.md) for field definitions. Rebuild clean records with:

```
python3 scripts/buildimage/clean_buildimage.py
```

## Raw Data Specification (`raw/`)

Each record in `raw/issue-<number>.json` contains the unedited GitHub API payload capturing both the issue and its resolving PR(s):

```json
{
  "number": 29542,
  "title": "[rsyslog] Read hostname from CONFIG_DB directly...",
  "state": "CLOSED",
  "url": "https://github.com/sonic-net/sonic-buildimage/issues/29542",
  "createdAt": "2026-09-14T20:24:21Z",
  "closedAt": "2026-09-24T00:03:45Z",
  "author": "...",
  "labels": ["Triaged", "MSFT"],
  "assignees": ["..."],
  "milestone": null,
  "body": "Full markdown issue description with error logs / tracebacks...",
  "comments": [
    {
      "author": "...",
      "createdAt": "...",
      "body": "..."
    }
  ],
  "linkedPullRequests": [
    {
      "number": 29543,
      "repository": "sonic-net/sonic-buildimage",
      "url": "https://github.com/sonic-net/sonic-buildimage/pull/29543",
      "title": "[rsyslog]: Read hostname from CONFIG_DB",
      "state": "MERGED",
      "merged": true,
      "mergedAt": "2026-09-24T00:03:44Z",
      "createdAt": "2026-09-14T20:25:33Z",
      "author": "...",
      "body": "PR description covering 'Why I did it' and 'How I did it'...",
      "files": [
        {
          "path": "files/image_config/rsyslog/rsyslog-config.sh",
          "additions": 5,
          "deletions": 9
        }
      ],
      "comments": [...]
    }
  ]
}
```

### Key Properties

- **Traceability**: Every record's filename matches `issue-<number>.json`, mapping directly to `https://github.com/sonic-net/sonic-buildimage/issues/<number>`.
- **Cross-Repository Linkage**: Some `sonic-buildimage` issues are resolved by PRs in related repositories (e.g. `sonic-swss`, `sonic-sairedis`, `sonic-platform-daemons`). The `linkedPullRequests[].repository` field preserves the exact repository origin.
- **Manifest**: `raw/manifest.json` provides a complete registry of mined issues, issue titles, creation/close timestamps, and linked PR summaries for quick querying without reading every file.

## Mining Methodology

Data was mined using the GitHub GraphQL API via `scripts/buildimage/mine_buildimage.py`:

- **Filter**: All issues in `sonic-net/sonic-buildimage` with `state: CLOSED` where `closedByPullRequestsReferences.totalCount > 0`.
- **Query mechanism**: Cursor-based GraphQL pagination querying batches of 35 issues per page to maximize retrieval speed while staying well within API complexity limits.
- **Reproducibility**: Re-run `python3 scripts/buildimage/mine_buildimage.py` to refresh or verify mined entries.

## Mining Statistics

- **Mined date**: September 28, 2026
- **Total closed issues scanned**: 2,964
- **Closed issues with linked PRs**: 997 records
- **Total raw JSON files saved**: 997 issue files + 1 manifest (`data/buildimage/raw/`)
- **Total raw data size**: ~15 MB

## Clean records (`clean/`)

Each `clean/issue-<number>.json` is one issue plus its primary **merged** linked PR.

| Use | Fields |
|---|---|
| Model input | `issue.title` + `failure.body` |
| Label | `resolution.description` (PR body, HTML comments stripped) |
| Auxiliary | `resolution.files` |
| Audit | `issue.url`, `resolution.url` |
| Filter / splits | `metadata` (severity, priority, issue_type, platform, target_releases, topics), dates, `quality.has_diagnostic_signal` |

**How the resolving PR is chosen.** Among `linkedPullRequests` with `merged == true`, take the latest `mergedAt`. Other linked PRs are listed in `related_prs` without bodies. Cross-repo PRs keep `repository` + `url`. Issues with no merged PR are skipped (13 in the current mine). Discussion comments stay in `raw/` only — they often name the fix.

**Metadata.** Derived during clean, never guessed:

- `severity` from issue body `Importance or Severity`
- `priority` / `issue_type` / `target_releases` / `topics` from labels (emoji shortcodes stripped)
- `platform` from `Is it platform specific`, else vendor/platform labels

**Train/val/test.** Prefer `quality.has_diagnostic_signal == true` (error/traceback/fail/log-like text in the issue body). Explicit `split` values are not assigned in v1.

**RAG.** Do not index these records. Use [`data/rag/`](../rag/) only.

### Clean statistics (schema 1.0)

- **Cleaned date**: September 28, 2026
- **Raw issues examined**: 997
- **Clean records written**: 984
- **Skipped (no merged PR)**: 13
- **With diagnostic signal**: 854

Rebuild with `python3 scripts/buildimage/clean_buildimage.py`. Counts by severity/priority/type are in `clean/manifest.json`.

## Unified diffs (not in v1)

`resolution.patch` is omitted until diffs are fetched on purpose:

```
python3 scripts/buildimage/enrich_patches.py --limit 5
```

Use `--sidecar` to write large diffs under `clean/patches/` instead of inlining them. Do not run this as part of ordinary cleaning.

## Ground Rules

1. **`raw/` is immutable**: Never manually edit or prune files inside `raw/`.
2. **`clean/` is derived**: Only write it via `scripts/buildimage/clean_buildimage.py`. Keep records conformant to [`format.md`](format.md).
3. **Data hygiene**: IPs, internal hostnames, emails, and obvious secrets are scrubbed in `failure.body` and `resolution.description`.
