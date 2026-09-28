# sonic-swss clean schema (`1.0`)

Labeled train/val/test records in `clean/issue-<n>.json`. Not a RAG corpus — that is [`data/rag/`](../rag/).

Build with `python3 scripts/swss/clean_swss.py`. Never edit `raw/`.


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
    "merged_at": "2019-11-09T01:36:23Z",
    "description": "...",
    "files": [
      { "path": "tests/Makefile.am", "additions": 5, "deletions": 1 }
    ]
  },
  "related_prs": [],
  "quality": {
    "has_diagnostic_signal": true,
    "notes": null
  },
  "split": "train"
}
```


| `metadata`   | Values                                                      |
| ------------ | ----------------------------------------------------------- |
| `severity`   | `critical` | `high` | `medium` | `low` (from issue body)    |
| `priority`   | `P0` | `P1` | `P2` | `P3`                                   |
| `issue_type` | `bug` | `enhancement` | `regression` | `build` | `question` |


Unknown values are `null` or `[]`. Bodies are HTML-comment-stripped and scrubbed; discussion comments stay in `raw/`. No authors or `patch` in v1.

## `split`

`split` is `"train"`, `"test"`, or `null`. Only records with `quality.has_diagnostic_signal == true` are assigned a split (75% train / 25% test, seeded deterministically — `SPLIT_SEED = 42` in `clean_swss.py`); records without diagnostic signal keep `split: null` and stay out of train/test entirely.

The same assignment is mirrored in [`clean/split.json`](clean/split.json) as an `id -> split` map, alongside the seed, ratio, and counts, so splits can be looked up without opening every record.
