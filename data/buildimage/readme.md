# sonic-buildimage Dataset

Dataset mined from [sonic-net/sonic-buildimage](https://github.com/sonic-net/sonic-buildimage), focusing on closed issues that have linked pull requests resolving them.

## Overview

In SONiC, build issues, image configuration regressions, daemon startup failures, and test environment problems are tracked in `sonic-buildimage` issues. When an issue is resolved by a linked pull request, the pair provides:

1. **Failure Signature & Context** (from the Issue): Bug reports, environment details, traceback logs, reproduction steps, and triage comments.
2. **True Root Cause & Resolution** (from the linked PR): Developer analysis ("Why I did it", "How I did it"), changelog descriptions, discussion comments, and the exact code diff fixing the issue.

This pairing serves as ground-truth training and benchmark data for automated failure diagnosis.

## Directory Layout

```
data/buildimage/
├── raw/                      # Unprocessed mined data (immutable)
│   ├── issue-<number>.json   # Per-issue raw payload with linked PRs
│   └── manifest.json         # Index of all mined issues and linked PRs
├── clean/                    # Cleaned, standardized dataset records
├── format.md                 # Target schema for entries in clean/
└── readme.md                 # This documentation
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

Data was mined using the GitHub GraphQL API via `scripts/mine_buildimage.py`:

- **Filter**: All issues in `sonic-net/sonic-buildimage` with `state: CLOSED` where `closedByPullRequestsReferences.totalCount > 0`.
- **Query mechanism**: Cursor-based GraphQL pagination querying batches of 35 issues per page to maximize retrieval speed while staying well within API complexity limits.
- **Reproducibility**: Re-run `python3 scripts/mine_buildimage.py` to refresh or verify mined entries.

## Mining Statistics

- **Mined date**: September 28, 2026
- **Total closed issues scanned**: 2,964
- **Closed issues with linked PRs**: 997 records
- **Total raw JSON files saved**: 997 issue files + 1 manifest (`data/buildimage/raw/`)
- **Total raw data size**: ~15 MB

## Ground Rules

1. **`raw/` is immutable**: Never manually edit or prune files inside `raw/`.
2. **Filtering for `clean/`**: Not every closed issue contains a test failure (some are build toolchain updates, feature requests, or documentation). The cleaning pipeline filters for issues with diagnostic signals (error messages, test failure logs, crash dumps) and distills them into the standardized benchmark format.
3. **Data hygiene**: Ensure proprietary identifiers, private IP ranges, and any internal credentials are scrubbed before moving entries to `clean/`.
