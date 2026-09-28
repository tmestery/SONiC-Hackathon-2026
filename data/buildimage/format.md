# sonic-buildimage clean schema

`schema_version`: `1.0`

Clean records live in `clean/issue-<number>.json`. They are **labeled examples** for SLM training, validation, and testing (and a public benchmark later). They are **not** a RAG corpus. Retrieval context comes only from [`data/documentation/`](../documentation/).

Every `clean/` file must match this schema. Transform from `raw/` with `python3 scripts/buildimage/clean_buildimage.py`. Never hand-edit `raw/`.

## Contract

| Role | Fields |
|---|---|
| Model input | `issue.title` + `failure.body` |
| Label | `resolution.description` |
| Auxiliary label | `resolution.files` (paths changed; optional for text scoring) |
| Human audit | `issue.url`, `resolution.url` |
| Filter / split only | `metadata`, dates, `related_prs`, `quality` |

Do not put `resolution`, `metadata`, comments, or URLs into the model prompt.

## Inclusion

A raw issue becomes a clean record when:

1. At least one linked PR has `merged == true`.
2. That PR’s body is non-empty after HTML comments are stripped.

Primary resolution PR: among merged linked PRs, pick the latest `mergedAt`. Other linked PRs go in `related_prs` (no bodies).

Issues without a merged PR are skipped. Rows with `quality.has_diagnostic_signal == false` are still written; exclude them from train/val/test.

## Record

```json
{
  "id": "buildimage-<issue_number>",
  "schema_version": "1.0",
  "source": "sonic-buildimage",
  "issue": {
    "number": 26363,
    "url": "https://github.com/sonic-net/sonic-buildimage/issues/26363",
    "title": "sflow broken on XGS LTSW: bcmgenl module not packaged",
    "created_at": "2026-01-01T00:00:00Z",
    "closed_at": "2026-01-15T00:00:00Z"
  },
  "metadata": {
    "severity": "high",
    "priority": null,
    "issue_type": "bug",
    "platform": "broadcom",
    "target_releases": ["202511"],
    "topics": []
  },
  "failure": {
    "body": "Is it platform specific: broadcom\n\nImportance or Severity: High\n\nDescription of the bug: ..."
  },
  "resolution": {
    "pr_number": 26364,
    "repository": "sonic-net/sonic-buildimage",
    "url": "https://github.com/sonic-net/sonic-buildimage/pull/26364",
    "title": "Package and load bcmgenl for sflow on XGS",
    "merged_at": "2026-01-15T00:00:00Z",
    "description": "#### Why I did it\nFixes #26363. ...\n\n#### How I did it\n...",
    "files": [
      {"path": "platform/broadcom/...", "additions": 5, "deletions": 1}
    ]
  },
  "related_prs": [],
  "quality": {
    "has_diagnostic_signal": true,
    "notes": null
  }
}
```

### Top-level

| Field | Type | Notes |
|---|---|---|
| `id` | string | `buildimage-<issue_number>` |
| `schema_version` | string | `"1.0"` |
| `source` | string | `"sonic-buildimage"` |

### `issue`

| Field | Type | Notes |
|---|---|---|
| `number` | int | GitHub issue number |
| `url` | string | Issue URL (audit only) |
| `title` | string | Model-input title |
| `created_at` | string | ISO-8601; for time-based splits |
| `closed_at` | string \| null | ISO-8601 |

No `author`, `assignees`, `state`, or raw `labels`.

### `metadata`

Used to filter and balance splits. Null or `[]` when unknown. Do not guess.

| Field | Type | Allowed / source |
|---|---|---|
| `severity` | string \| null | `critical`, `high`, `medium`, `low` from issue body `Importance or Severity` |
| `priority` | string \| null | `P0`, `P1`, `P2`, `P3` from labels |
| `issue_type` | string \| null | `bug`, `enhancement`, `regression`, `build`, `question` from labels (prefer bug > regression > enhancement > build > question) |
| `platform` | string \| null | Body `Is it platform specific`; else vendor/platform labels (`BRCM` → `broadcom`) |
| `target_releases` | string[] | From `Issue for 202012`, `Issues for 202511`, `Master Branch Quality` → `master`, etc. |
| `topics` | string[] | Remaining labels after emoji strip, excluding labels already mapped above |

### `failure`

| Field | Type | Notes |
|---|---|---|
| `body` | string | Issue body with HTML comments stripped; secrets/IPs/hostnames scrubbed. Discussion comments are **not** included (they often leak the fix). |

### `resolution`

| Field | Type | Notes |
|---|---|---|
| `pr_number` | int | |
| `repository` | string | `owner/name` (may differ from sonic-buildimage) |
| `url` | string | PR URL |
| `title` | string | |
| `merged_at` | string | ISO-8601 |
| `description` | string | PR body with HTML-comment banners stripped; Why/How/verify kept; required and non-empty |
| `files` | object[] | `{ path, additions, deletions }` |

No `state`, `merged` boolean, `author`, PR comments, or `patch` in v1. Unified diffs are a later enrichment (`scripts/buildimage/enrich_patches.py`); do not store `"patch": null` on every record.

### `related_prs`

Other linked PRs: `{ pr_number, repository, url, title, merged }`. No bodies.

### `quality`

| Field | Type | Notes |
|---|---|---|
| `has_diagnostic_signal` | bool | Issue body contains error/traceback/fail/assert/log-like text |
| `notes` | string \| null | Cleaner remarks, if any |

## Omitted on purpose

Kept in `raw/` only:

- Authors and assignees
- Issue and PR discussion comments
- Issue `state` (this mine is all closed)
- `resolution.state` / `merged` (primary PR is always merged)
- Milestone (always null in this mine)
- Raw emoji labels (replaced by `metadata`)
- Unified diffs until explicitly enriched

## Later (not v1)

- Explicit `split`: `train` / `val` / `test`
- Parsed `failure.sections` from the SONiC bug template
- `resolution.patch` via `scripts/buildimage/enrich_patches.py`
