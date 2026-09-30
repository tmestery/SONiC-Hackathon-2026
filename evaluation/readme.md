# Evaluation

Score an agent on the **frozen test** split from [`data/splits.json`](../data/splits.json).
Never evaluates on `train`. Layout mirrors [`training/`](../training/).

Pipeline per example:

1. Load clean record (title + failure; gold held out from the model)
2. Optionally retrieve SONiC docs from [`data/rag/`](../data/rag/)
3. Query local **Ollama** for a diagnosis
4. Score the prediction with **Groq** judges (0–1) against gold `resolution.description`
5. Print a report and write JSON under `evaluation/results/`

## Layout

```
evaluation/
├── config.yaml         # Ollama + RAG + Groq judges
├── eval.py             # run test-split evaluation
├── requirements.txt
└── results/            # eval-*.json outputs (gitignored)
```

## Config

| Key | Purpose |
|---|---|
| `ollama.host` / `ollama.model` | Local inference server (default `http://127.0.0.1:11434`) |
| `ollama.system_prompt` | System message sent with each failure |
| `ollama.timeout_s` | Per-request timeout |
| `rag.*` | BM25 over `data/rag` (enabled by default); same retrieval as training |
| `judges[]` | Groq models + prompts; each returns a 0–1 score |
| `splits_file` | Frozen splits; eval always uses `test` |
| `limit` | Optional default cap on test examples (`null` = full split) |
| `results_dir` | Where JSON reports are written |

**Note:** Predictions come from **Ollama**. Judges use the **Groq** API (`GROQ_API_KEY` in repo-root `.env`). Judge model IDs must be ones your Groq account can access.

RAG uses the same BM25 index as training. Disable with `rag.enabled: false` or `--no-rag`.

## Setup (venv)

From the repo root (Python 3.12 recommended; same `.venv` as training is fine):

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r evaluation/requirements.txt
```

Copy [`.env.example`](../.env.example) to `.env` and set `GROQ_API_KEY`. Ensure Ollama is running and the model is pulled, e.g. `ollama pull qwen3.5:9b`.

## Usage

```bash
# Always work with the venv active
source .venv/bin/activate

# Smoke: first 5 test examples, override Ollama model
python evaluation/eval.py --limit 5 --ollama-model qwen3.5:9b

# Full frozen test split (checkpoint saved after every example)
python evaluation/eval.py --ollama-model qwen3.5:9b

# Optional: fixed checkpoint path (easier to resume)
python evaluation/eval.py --ollama-model qwen3.5:9b --output evaluation/results/eval-full.json

# Resume after Ctrl-C / crash (skips ids already in the JSON)
python evaluation/eval.py --ollama-model qwen3.5:9b --resume evaluation/results/eval-full.json

# Ablate RAG
python evaluation/eval.py --limit 5 --no-rag --ollama-model qwen3.5:9b

# Override Ollama host
python evaluation/eval.py --limit 5 --ollama-host http://127.0.0.1:11434
```

`--limit N` takes the first N ids from the test split (useful for cheap smoke runs).

Results are **checkpointed after every example** to `evaluation/results/eval-<stamp>.json` (or `--output`). If the run dies, use `--resume <that file>` to continue without redoing finished ids.
## What the model sees

Same user turn shape as training SFT:

- **system** — from `ollama.system_prompt`
- **user** — issue title + failure body + retrieved SONiC docs (`rag.enabled`)

Gold `resolution.description` is **not** sent to Ollama; judges only see it.

## Judges

Each judge in `config.yaml` scores prediction vs gold on one axis (e.g. root cause, fix approach, diagnostic fidelity). Eval reports:

- per-example mean over judges that returned a score
- overall mean and per-judge means
- RAG hit counts when retrieval is enabled

Results JSON lands in `evaluation/results/eval-<timestamp>.json`.

## Contract with training

| | Training | Evaluation |
|---|---|---|
| Split | `train` only | `test` only |
| Input | title + failure + RAG context | same text via Ollama user turn |
| Gold | PR description (SFT target) | PR description (judge reference) |
| RAG | `data/rag` BM25 | same index + `top_k` |
| Local LLM | HF `model.name_or_path` (LoRA SFT) | Ollama `ollama.model` (inference) |
| Scoring | train loss | Groq judges 0–1 |
