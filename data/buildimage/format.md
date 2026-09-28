# sonic-buildimage clean schema (`1.0`)

Labeled train/val/test records in `clean/issue-<n>.json`. Not a RAG corpus - that is `[data/documentation/](../documentation/)`.

Build with `python3 scripts/buildimage/clean_buildimage.py`. Never edit `raw/`.


| Role        | Fields                                      |
| ----------- | ------------------------------------------- |
| Input       | `issue.title` + `failure.body`              |
| Label       | `resolution.description`                    |
| Optional    | `resolution.files`                          |
| Audit       | `issue.url`, `resolution.url`               |
| Filter only | `metadata`, dates, `related_prs`, `quality` |


Include a record when a linked PR is merged and its body is non-empty after HTML comments are stripped. Primary PR is the latest `mergedAt`. Other linked PRs go in `related_prs` (no bodies). Keep `has_diagnostic_signal == false` rows out of train/val/test.

```json
{
  "id": "buildimage-26363",
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
    "body": "..."
  },
  "resolution": {
    "pr_number": 26364,
    "repository": "sonic-net/sonic-buildimage",
    "url": "https://github.com/sonic-net/sonic-buildimage/pull/26364",
    "title": "Package and load bcmgenl for sflow on XGS",
    "merged_at": "2026-01-15T00:00:00Z",
    "description": "#### Why I did it\n...",
    "files": [
      { "path": "platform/broadcom/...", "additions": 5, "deletions": 1 }
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


Unknown values are `null` or `[]`. Bodies are HTML-comment-stripped and scrubbed; discussion comments stay in `raw/`. No authors, `patch`, or `split` in v1.