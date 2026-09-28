# SONiC RAG corpus

Retrieval-only context for the SLM. **Not** train/val/test data — that lives in
`buildimage/`, `management/`, and `swss/`.

Source: [`sonic-net/SONiC`](https://github.com/sonic-net/SONiC) `doc/` tree, plus a
few wiki pages (Architecture, Home).

## Layout

```
data/rag/
├── readme.md
├── sources/          # mirrored markdown/text from SONiC/doc (+ wiki/)
├── chunks.jsonl      # chunked documents
└── index/
    ├── bm25.pkl      # BM25 retrieval index
    └── meta.json     # chunk counts, source commit, build time
```

## Rebuild

```bash
pip install -r requirements-rag.txt
python3 scripts/rag/fetch_docs.py
python3 scripts/rag/build_index.py
python3 scripts/rag/query.py "orchagent warm reboot"
```

Temp clone lives in `.cache/sonic-docs/` (gitignored).

## Usage contract

- Index **only** this corpus for RAG.
- Do **not** index `clean/` issue/PR records (label leakage).
- Query returns top-k chunks with path, title, and score for prompt context.
