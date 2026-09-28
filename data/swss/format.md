# sonic-swss clean schema (`1.0`)

Labeled train/test records in `clean/issue-<n>.json`. Not a RAG corpus — that is [`data/rag/`](../rag/).

Build with `python3 scripts/swss/clean_swss.py`. Never edit `raw/`.
Frozen splits live in [`splits.json`](splits.json) — **never train on `split: "test"`**.


| Role        | Fields                                      |
| ----------- | ------------------------------------------- |
| Input       | `issue.title` + `failure.body`              |
| Label       | `resolution.description`                    |
| Optional    | `resolution.files`                          |
| Audit       | `issue.url`, `resolution.url`               |
| Filter only | `metadata`, dates, `related_prs`, `quality` |
| Split       | `split`: `train` \| `test` \| `null`        |


Include a record when a linked PR is merged and its body is non-empty after HTML comments are stripped. Primary PR is the latest `mergedAt`. Other linked PRs go in `related_prs` (no bodies).

**Splits (frozen):** only `has_diagnostic_signal == true` rows are assigned. Random shuffle (seed `42`): **75% train / 25% test**. Non-diagnostic rows get `split: null` (excluded). Rebuild stamps with `python3 scripts/swss/freeze_splits.py --apply-only`.

```json
{
  "id": "swss-1122",
  "schema_version": "1.0",
  "source": "sonic-swss",
  "issue": {
    "number": 1122,
    "url": "https://github.com/sonic-net/sonic-swss/issues/1122",
    "title": "swss build fails if SAI library installed",
    "created_at": "2019-11-08T01:06:12Z",
    "closed_at": "2019-11-09T01:36:24Z"
  },
  "metadata": {
    "severity": null,
    "priority": null,
    "issue_type": "bug",
    "platform": null,
    "target_releases": [],
    "topics": []
  },
  "failure": {
    "body": "..."
  },
  "resolution": {
    "pr_number": 1123,
    "repository": "sonic-net/sonic-swss",
    "url": "https://github.com/sonic-net/sonic-swss/pull/1123",
    "title": "[tests] fix build against real SAI",
    "merged_at": "2019-11-09T01:36:24Z",
    "description": "...",
    "files": [
      { "path": "tests/Makefile.am", "additions": 2, "deletions": 0 }
    ]
  },
  "related_prs": [],
  "quality": {
    "has_diagnostic_signal": true,
    "notes": null
  },
  "split": "test"
}
```


| `metadata`   | Values                                                      |
| ------------ | ----------------------------------------------------------- |
| `severity`   | `critical` | `high` | `medium` | `low` (from issue body)    |
| `priority`   | `P0` | `P1` | `P2` | `P3`                                   |
| `issue_type` | `bug` | `enhancement` | `regression` | `build` | `question` |


Unknown values are `null` or `[]`. Bodies are HTML-comment-stripped and scrubbed; discussion comments stay in `raw/`. No authors or `patch` in v1.
