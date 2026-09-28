# sonic-mgmt issue inclusion criteria

Rules for which [sonic-net/sonic-mgmt](https://github.com/sonic-net/sonic-mgmt) issues belong in this dataset. Mining and future cleaning use different layers.

## Mining gate (enforced now)

Applied by `scripts/management/mine_management.py` when writing `raw/issue-<number>.json`:

1. Issue `state` is `CLOSED`
2. At least one linked pull request (`closedByPullRequestsReferences` is non-empty)

No other filters run at mine time. `raw/` may contain issues that fail the quality criteria below.

## Clean gate (enforced by `clean_management.py`)

Applied when writing `clean/issue-<number>.json` (see [`format.md`](format.md)):

1. **Resolving PR** — At least one linked PR with `merged == true` whose body is non-empty after HTML comments are stripped.
2. Primary PR is the latest `mergedAt`; other linked PRs go in `related_prs`.

Records are still written when diagnostic signal is missing; set `quality.has_diagnostic_signal` and keep `false` rows out of train/val/test.

## Additional quality criteria (documented only; not enforced yet)

Aligned with root-cause diagnosis from test failures/logs ([proposal](../../docs/SONiC-Hackathon-2026-Proposal.md), [high-quality dataset guide](../../docs/guides/high-quality-dataset-guide.md)):

1. **Diagnostic / failure signal** — The issue body matches failure-oriented language, for example:
   - General: `error`, `traceback`, `exception`, `assert`, `failed`, `failure`, `fatal`, `panic`, `segfault`, `core dump`, `crash`, `timeout`, `not found`, `unable to`, `show techsupport`, `show version`
   - sonic-mgmt oriented: `pytest`, `AssertionError`, `FAILED`, `test_*.py` / named test modules, `LogAnalyzer`
2. **Non-placeholder body** — Body is not empty and is not only an unfilled bug-template shell (`_No response_`, empty fenced log / `show version` blocks with no other substance).
3. **Failure report, not coverage-only** — Prefer bug/failure reports. Exclude issues that are only a “Test gap” or feature request with no failure signature.
4. **Structured content when present** — If the bug template fields exist (Description, Steps to Reproduce, Actual/Expected Behavior), they should contain real content rather than placeholders.

These additional rules are **not** applied by the miner or cleaner yet.
