# sonic-mgmt clean schema (`1.0`)

Labeled train/test records in `clean/issue-<n>.json`. Not a RAG corpus - that is `[data/documentation/](../documentation/)`.

Build with `python3 scripts/management/clean_management.py`. Never edit `raw/`.
Frozen splits live in [`splits.json`](splits.json) — **never train on `split: "test"`**.

See [`issue.md`](issue.md) for mining vs quality criteria.


| Role        | Fields                                      |
| ----------- | ------------------------------------------- |
| Input       | `issue.title` + `failure.body`              |
| Label       | `resolution.description`                    |
| Optional    | `resolution.files`                          |
| Audit       | `issue.url`, `resolution.url`               |
| Filter only | `metadata`, dates, `related_prs`, `quality` |
| Split       | `split`: `train` \| `test` \| `null`        |


Include a record when a linked PR is merged and its body is non-empty after HTML comments are stripped. Primary PR is the latest `mergedAt`. Other linked PRs go in `related_prs` (no bodies).

**Splits (frozen):** only `has_diagnostic_signal == true` rows are assigned. Random shuffle (seed `42`): **75% train / 25% test**. Non-diagnostic rows get `split: null` (excluded). Rebuild stamps with `python3 scripts/management/freeze_splits.py --apply-only`.

```json
{
  "id": "management-28115",
  "schema_version": "1.0",
  "source": "sonic-mgmt",
  "split": "test",
  "issue": {
    "number": 28115,
    "url": "https://github.com/sonic-net/sonic-mgmt/issues/28115",
    "title": "Bug: MACSec test cleanup excessively slow with --per_interface_macsec",
    "created_at": "2026-09-22T20:39:32Z",
    "closed_at": "2026-09-23T17:59:03Z"
  },
  "metadata": {
    "severity": "medium",
    "priority": null,
    "issue_type": "bug",
    "platform": "generic",
    "target_releases": [],
    "topics": []
  },
  "failure": {
    "body": "..."
  },
  "resolution": {
    "pr_number": 28116,
    "repository": "sonic-net/sonic-mgmt",
    "url": "https://github.com/sonic-net/sonic-mgmt/pull/28116",
    "title": "...",
    "merged_at": "2026-09-23T17:59:03Z",
    "description": "#### Why I did it\n...",
    "files": [
      { "path": "tests/macsec/...", "additions": 5, "deletions": 1 }
    ]
  },
  "related_prs": [],
  "quality": {
    "has_diagnostic_signal": true,
    "notes": null
  }
}
```


| `metadata`   | Values                                                      |
| ------------ | ----------------------------------------------------------- |
| `severity`   | `critical` | `high` | `medium` | `low` (from issue body)    |
| `priority`   | `P0` | `P1` | `P2` | `P3`                                   |
| `issue_type` | `bug` | `enhancement` | `regression` | `build` | `question` |


Unknown values are `null` or `[]`. Bodies are HTML-comment-stripped and scrubbed; discussion comments stay in `raw/`. No authors or `patch` in v1.
