# Training runs

Each LoRA SFT run lives in a model-specific folder:

```
training/runs/<base-model-slug>-lora/
├── run.json           # manifest (steps, hyperparams, checkpoint list)
├── data/              # prepared SFT JSONL (committed)
│   ├── train.jsonl
│   └── meta.json
├── adapter/           # final LoRA + tokenizer (committed)
└── checkpoints/       # TRL checkpoint-* (local only, gitignored)
```

Slug comes from `model.name_or_path` (e.g. `Qwen/Qwen3.5-2B` → `qwen3.5-2b-lora`).

Override with `training.run_name` in `config.yaml`.
