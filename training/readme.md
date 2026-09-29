# Training (SFT)

Supervised fine-tuning on the **frozen train** split from [`data/splits.json`](../data/splits.json).
Never trains on `test`. Layout mirrors [`evaluation/`](../evaluation/).

## Layout

```
training/
├── config.yaml         # local model + agent endpoint + SFT/LoRA hyperparams
├── train.py            # prepare JSONL + run LoRA SFT
├── requirements.txt
├── data/               # written by --prepare-only / train (gitignored)
└── output/             # LoRA adapter / checkpoint (gitignored)
```

## Config (local LLM)

| Key | Purpose |
|---|---|
| `model.name_or_path` | HF id or local weights path to fine-tune (not an Ollama tag) |
| `agent.url` | Local predict server for smoke / post-train eval (`http://127.0.0.1:8000/predict`) |
| `rag.*` | BM25 over `data/rag` (enabled by default); injects docs into SFT user turns |
| `data.splits_file` | Frozen splits; `split: train` only |
| `training.*` / `lora.*` | SFT hyperparameters |

**Note:** Ollama (`qwen3.5:9b` on `:11434`) is for **inference / baseline**. LoRA SFT needs Hugging Face-style weights via `model.name_or_path`.

Default config uses `Qwen/Qwen3.5-0.8B` so a Mac can download + LoRA-smoke quickly. To train the same class as Ollama 9B, set `model.name_or_path: "Qwen/Qwen3.5-9B"` (large download + ~22GB memory).

RAG uses the same BM25 index as eval. Disable with `rag.enabled: false` or `--no-rag`.

## Setup (venv)

Use **Python 3.12** (PyTorch wheels; system 3.14 may not work yet). From the repo root:

```bash
# Create and activate a virtualenv
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Upgrade pip, then install training deps
python -m pip install --upgrade pip
pip install -r training/requirements.txt
```

On Apple Silicon, keep `training.load_in_4bit: false` in `config.yaml` (4-bit needs NVIDIA CUDA). MPS is used automatically when available.

## Usage

```bash
# Always work with the venv active
source .venv/bin/activate

# 1) Build chat SFT JSONL from frozen train ids
python training/train.py --prepare-only

# Quick smoke with a few examples
python training/train.py --prepare-only --limit 5

# 2) Optional: confirm local /predict server is up (eval-compatible)
python training/train.py --smoke-prompt

# 3) LoRA SFT (needs GPU/MPS + model.name_or_path set in config.yaml)
# Use unbuffered output so download/train progress shows under tee/pipes
PYTHONUNBUFFERED=1 python training/train.py --limit 2

# Full train split (after smoke works)
python training/train.py

# 4) Score baseline or fine-tuned server on the frozen test set
python evaluation/eval.py --agent-url http://127.0.0.1:8000/predict
python evaluation/eval.py --limit 5 --agent-url http://127.0.0.1:8000/predict
```

## Example format

Each train row is chat messages:

- **system** — from `data.system_prompt`
- **user** — issue title + failure body + retrieved SONiC docs (`rag.enabled`)
- **assistant** — gold `resolution.description`

Optional `rag` metadata on each JSONL row lists query + hit ids/paths (not fed to the model beyond the user text).

## Contract with evaluation

| | Training | Evaluation |
|---|---|---|
| Split | `train` only | `test` only |
| Input | title + failure + RAG context | same fields in `user_message` / payload |
| Gold | PR description (SFT target) | PR description (judge reference) |
| RAG | `data/rag` BM25 | same index + `top_k` |
| Local LLM | `model.name_or_path` + optional `agent.url` | `agent.url` |
