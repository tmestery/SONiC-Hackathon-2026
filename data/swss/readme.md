# sonic-swss Dataset

Dataset mined from [sonic-net/sonic-swss](https://github.com/sonic-net/sonic-swss), focusing on closed issues that have linked pull requests resolving them.

## Overview

`sonic-swss` (switch state service) is the orchestration layer between CONFIG/APPL DB and the SAI-facing `syncd`/`orchagent` components. Issues here cover orchagent crashes, state sync bugs, VLAN/LAG/tunnel/route handling defects, and test failures in the `tests/` mock/VS test suite. When an issue is resolved by a linked pull request, the pair provides:

1. **Failure Signature & Context** (from the Issue): Bug reports, `swss#orchagent` / `syncd` log excerpts, `show techsupport` output, and reproduction steps.
2. **True Root Cause & Resolution** (from the linked PR): Developer analysis ("Why I did it", "How I did it") in the PR description, plus the files the PR changed.

This pairing is labeled data for SLM **training, validation, and testing**, and for a public benchmark later. It is **not** a RAG corpus. Retrieval context comes only from [`data/rag/`](../rag/).

## Directory Layout

```
data/swss/
├── raw/                      # Unprocessed mined data (immutable)
│   ├── issue-<number>.json   # Per-issue raw payload with linked PRs
│   └── manifest.json         # Index of all mined issues and linked PRs
├── clean/                    # Schema 1.0 records for train/test
│   ├── issue-<number>.json
│   └── manifest.json
├── format.md                 # Schema for entries in clean/
└── readme.md                 # This documentation
```

See [`format.md`](format.md) for field definitions. Rebuild clean records with:

```
python3 scripts/swss/clean_swss.py
```

Frozen splits live in [`../splits.json`](../splits.json) and are re-applied automatically if that file exists.

## Raw Data Specification (`raw/`)

Each record in `raw/issue-<number>.json` contains the unedited GitHub API payload capturing both the issue and its resolving PR(s):

```json
{
  "number": 1122,
  "title": "swss build fails if SAI library installed",
  "state": "CLOSED",
  "url": "https://github.com/sonic-net/sonic-swss/issues/1122",
  "createdAt": "2019-11-08T01:06:12Z",
  "closedAt": "2019-11-09T01:36:24Z",
  "author": "...",
  "labels": ["Bug :bug:"],
  "assignees": ["..."],
  "milestone": null,
  "body": "Full markdown issue description with logs / repro steps...",
  "comments": [
    {
      "author": "...",
      "createdAt": "...",
      "body": "..."
    }
  ],
  "linkedPullRequests": [
    {
      "number": 1123,
      "repository": "sonic-net/sonic-swss",
      "url": "https://github.com/sonic-net/sonic-swss/pull/1123",
      "title": "[tests] fix build against real SAI",
      "state": "MERGED",
      "merged": true,
      "mergedAt": "2019-11-09T01:36:23Z",
      "createdAt": "2019-11-08T01:10:00Z",
      "author": "...",
      "body": "PR description covering 'Why I did it' and 'How I did it'...",
      "files": [
        {
          "path": "tests/Makefile.am",
          "additions": 5,
          "deletions": 1
        }
      ],
      "comments": [...]
    }
  ]
}
```

### Key Properties

- **Traceability**: Every record's filename matches `issue-<number>.json`, mapping directly to `https://github.com/sonic-net/sonic-swss/issues/<number>`.
- **Cross-Repository Linkage**: Some `sonic-swss` issues are resolved by PRs in related repositories (e.g. `sonic-sairedis`, `sonic-buildimage`). The `linkedPullRequests[].repository` field preserves the exact repository origin.
- **Manifest**: `raw/manifest.json` provides a complete registry of mined issues, issue titles, creation/close timestamps, and linked PR summaries for quick querying without reading every file.

## Mining Methodology

Data was mined using the GitHub GraphQL API via `scripts/swss/mine_swss.py`, following the same cursor-paginated approach as [`buildimage/`](../buildimage/readme.md) and [`management/`](../management/readme.md):

- **Filter**: All issues in `sonic-net/sonic-swss` with `state: CLOSED` where `closedByPullRequestsReferences.totalCount > 0`.
- **Query mechanism**: Cursor-based GraphQL pagination querying batches of 35 issues per page.
- **Reproducibility**: Re-run `python3 scripts/swss/mine_swss.py` to refresh or verify mined entries.

## Mining Statistics

- **Mined date**: September 28, 2026
- **Total closed issues scanned**: 218
- **Closed issues with linked PRs**: 57 records
- **Total raw JSON files saved**: 57 issue files + 1 manifest (`data/swss/raw/`)

`sonic-swss` is a much smaller issue tracker than `sonic-buildimage`/`sonic-mgmt` — most swss-related bug reports and repro history live upstream in `sonic-buildimage` issues that get resolved by `sonic-swss` PRs (see [`buildimage/`](../buildimage/readme.md), which captures those cross-repo pairs already). This dataset covers the smaller set of issues filed directly against `sonic-swss`.

## Clean records (`clean/`)

Each `clean/issue-<number>.json` is one issue plus its primary **merged** linked PR, in the same schema as [`buildimage/format.md`](../buildimage/format.md) and [`management/format.md`](../management/format.md).

| Use | Fields |
|---|---|
| Model input | `issue.title` + `failure.body` |
| Label | `resolution.description` (PR body, HTML comments stripped) |
| Auxiliary | `resolution.files` |
| Audit | `issue.url`, `resolution.url` |
| Filter / splits | `metadata`, dates, `related_prs`, `quality.has_diagnostic_signal`, **`split`** |

**How the resolving PR is chosen.** Among `linkedPullRequests` with `merged == true`, take the latest `mergedAt`. Other linked PRs are listed in `related_prs` without bodies. Cross-repo PRs keep `repository` + `url`.

**Metadata.** Derived during clean, never guessed:

- `severity` from issue body `Importance or Severity` / `Severity` lines
- `priority` / `issue_type` / `target_releases` / `topics` from labels (emoji shortcodes stripped)
- `platform` from `Is it platform specific` / `Platform` body lines, else vendor/platform labels

**Diagnostic signal.** `quality.has_diagnostic_signal` looks for failure-oriented language plus swss-specific markers: `error`, `traceback`, `crash`, `segfault`, `timeout`, `orchagent`, `syncd`, `swss#`, `sairedis`, `valgrind`, `asan`/`sanitizer`, `deadlock`, `memory leak`, `show techsupport`, `FAILED`.

**Train/test (frozen).** Source of truth: [`../splits.json`](../splits.json) (combined with buildimage and management).

- Eligible: `has_diagnostic_signal == true` only
- Method: temporal by `issue.closed_at` (oldest → newest)
- **75% train / 25% test** — test is the newest quarter; **never train on it**
- Non-diagnostic rows: `split: null` (excluded)
- Record ids in the freeze are schema ids (`swss-<n>`, not raw issue numbers)

```bash
python3 scripts/freeze_splits.py --apply-only   # re-stamp after a clean rebuild
```

Do **not** re-run without `--apply-only` / `--force` — overwriting the freeze invalidates any prior eval numbers.

**RAG.** Do not index these records. Use [`data/rag/`](../rag/) only.

### Clean statistics (schema 1.0)

- **Cleaned date**: September 28, 2026
- **Raw issues examined**: 57
- **Clean records written**: 57
- **Skipped (no merged PR)**: 0
- **Skipped (empty PR description)**: 0
- **With diagnostic signal**: 41

Rebuild with `python3 scripts/swss/clean_swss.py`. Counts by severity/priority/type are in `clean/manifest.json`.

## Ground Rules

1. **`raw/` is immutable**: Never manually edit or prune files inside `raw/`.
2. **`clean/` is derived**: Only write it via `scripts/swss/clean_swss.py`. Keep records conformant to [`format.md`](format.md).
3. **Data hygiene**: IPs, internal hostnames, emails, and obvious secrets are scrubbed in `failure.body` and `resolution.description`.
