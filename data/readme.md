# Data

Mined SONiC test failures paired with their root causes, organized by source repository:

| Folder | Source |
|---|---|
| `buildimage/` | [sonic-buildimage](https://github.com/sonic-net/sonic-buildimage) PRs and issues |
| `management/` | [sonic-mgmt](https://github.com/sonic-net/sonic-mgmt) PRs and issues |
| `swss/` | [sonic-swss](https://github.com/sonic-net/sonic-swss) PRs and issues |
| `rag/` | SONiC documentation RAG corpus (retrieval only) |

## Layout

Each source folder (`buildimage/`, `management/`, `swss/`) follows the same structure:

- **`raw/`** — Unprocessed mined data: closed PRs, linked issues, test logs, and
  `show techsupport` dumps, exactly as collected. Never edit files here by hand.
- **`clean/`** — Cleaned, labeled entries derived from `raw/`. Each entry pairs a
  failure with its verified resolution (PR URL + PR description). Use these for
  SLM train/val/test and a future benchmark. Do not index them for RAG.
- **`format.md`** — Schema for the cleaned entries in that folder (fields, types, example record).
- **`readme.md`** — Source-specific notes: how the data was mined, filters applied, known gaps.

## Ground rules

- Raw data goes in `raw/`; anything derived or hand-corrected goes in `clean/`.
- Keep `clean/` entries conformant to the folder's `format.md`.
- Strip anything sensitive (IPs, hostnames, credentials) before committing.

## RAG corpus

`rag/` holds SONiC documentation used as retrieval context for the SLM (architecture
guides, HLDs, CLI notes). It is **not** train/val/test data. See [`rag/readme.md`](rag/readme.md).
