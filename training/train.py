#!/usr/bin/env python3
"""
Supervised fine-tuning on the frozen train split.

Mirrors evaluation/: local model + endpoints live in config.yaml.

Pipeline:
  1. Load train ids from data/splits.json (never test)
  2. Build chat SFT examples from clean records
  3. Write JSONL under training/data/
  4. Run LoRA SFT with TRL (optional --prepare-only to skip training)

Usage:
  python training/train.py --prepare-only
  python training/train.py
  python training/train.py --config training/config.yaml --limit 8
  python training/train.py --smoke-prompt
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.yaml"
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from rag.retriever import (  # noqa: E402
    build_user_content,
    load_index_from_cfg,
    retrieve_for_record,
)

SOURCE_DIRS = {
    "buildimage": ROOT / "data" / "buildimage" / "clean",
    "management": ROOT / "data" / "management" / "clean",
    "swss": ROOT / "data" / "swss" / "clean",
}


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    if not isinstance(cfg, dict):
        raise SystemExit(f"Config must be a mapping: {path}")
    return cfg


def record_path_for_id(record_id: str) -> Path:
    try:
        source, number = record_id.split("-", 1)
    except ValueError as exc:
        raise ValueError(f"Bad record id: {record_id!r}") from exc
    clean_dir = SOURCE_DIRS.get(source)
    if clean_dir is None:
        raise ValueError(f"Unknown source prefix in id: {record_id!r}")
    return clean_dir / f"issue-{number}.json"


def load_record(record_id: str) -> dict[str, Any]:
    path = record_path_for_id(record_id)
    if not path.exists():
        raise FileNotFoundError(f"Missing clean record for {record_id}: {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_split_ids(splits_file: Path, split: str, limit: int | None) -> list[str]:
    with splits_file.open(encoding="utf-8") as fh:
        splits = json.load(fh)
    if split == "test":
        raise SystemExit(
            "Refusing to train on the frozen test split. "
            "Use data.split: train in config."
        )
    ids = list(splits.get(split) or [])
    if not ids:
        raise SystemExit(f"No ids for split={split!r} in {splits_file}")
    if limit is not None:
        ids = ids[: max(0, limit)]
    return ids


def gold_content(record: dict[str, Any]) -> str:
    return ((record.get("resolution") or {}).get("description") or "").strip()


def build_example(
    record: dict[str, Any],
    *,
    system_prompt: str,
    rag_context: str = "",
    rag_meta: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    user = build_user_content(record, rag_context=rag_context)
    gold = gold_content(record)
    if not user or not gold:
        return None
    example: dict[str, Any] = {
        "id": record.get("id"),
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user},
            {"role": "assistant", "content": gold},
        ],
    }
    if rag_meta:
        example["rag"] = rag_meta
    return example


def prepare_dataset(
    cfg: dict[str, Any],
    *,
    limit: int | None = None,
) -> Path:
    data_cfg = cfg.get("data") or {}
    splits_rel = data_cfg.get("splits_file") or "data/splits.json"
    splits_file = ROOT / splits_rel
    if not splits_file.exists():
        raise SystemExit(f"Missing splits file: {splits_file}")

    split = data_cfg.get("split") or "train"
    cfg_limit = data_cfg.get("limit")
    effective_limit = limit if limit is not None else cfg_limit
    if effective_limit is not None:
        effective_limit = int(effective_limit)

    ids = load_split_ids(splits_file, split, effective_limit)
    system_prompt = data_cfg.get("system_prompt") or (
        "You diagnose SONiC failures and explain the root cause and fix."
    )

    rag_cfg = cfg.get("rag") or {}
    rag_enabled = bool(rag_cfg.get("enabled", False))
    index = load_index_from_cfg(ROOT, cfg) if rag_enabled else None
    top_k = int(rag_cfg.get("top_k") or 4)
    max_query_chars = int(rag_cfg.get("max_query_chars") or 1500)
    max_chars_per_chunk = int(rag_cfg.get("max_chars_per_chunk") or 800)

    prepared_rel = data_cfg.get("prepared_dir") or "training/data"
    prepared_dir = ROOT / prepared_rel
    prepared_dir.mkdir(parents=True, exist_ok=True)
    out_path = prepared_dir / "train.jsonl"

    written = 0
    skipped = 0
    rag_hit_total = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for record_id in ids:
            try:
                record = load_record(record_id)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                print(f"skip {record_id}: {exc}", file=sys.stderr)
                skipped += 1
                continue
            rag_context = ""
            rag_meta: dict[str, Any] | None = None
            if index is not None:
                query, hits, rag_context = retrieve_for_record(
                    index,
                    record,
                    top_k=top_k,
                    max_query_chars=max_query_chars,
                    max_chars_per_chunk=max_chars_per_chunk,
                )
                rag_hit_total += len(hits)
                rag_meta = {
                    "query": query,
                    "hits": [h.to_meta() for h in hits],
                }
            example = build_example(
                record,
                system_prompt=system_prompt,
                rag_context=rag_context,
                rag_meta=rag_meta,
            )
            if example is None:
                skipped += 1
                continue
            fh.write(json.dumps(example, ensure_ascii=False) + "\n")
            written += 1

    meta = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "splits_file": str(splits_file.relative_to(ROOT)),
        "split": split,
        "requested_ids": len(ids),
        "written": written,
        "skipped": skipped,
        "train_jsonl": str(out_path.relative_to(ROOT)),
        "rag": {
            "enabled": rag_enabled and index is not None,
            "top_k": top_k if index is not None else 0,
            "hit_total": rag_hit_total,
            "mean_hits": (rag_hit_total / written) if written else 0.0,
        },
    }
    meta_path = prepared_dir / "meta.json"
    with meta_path.open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
        fh.write("\n")

    print(f"Prepared {written} SFT examples (skipped {skipped})")
    print(f"  → {out_path.relative_to(ROOT)}")
    print(f"  → {meta_path.relative_to(ROOT)}")
    return out_path


def smoke_prompt(cfg: dict[str, Any]) -> None:
    """Query the local Ollama model with a tiny synthetic payload (eval-compatible)."""
    try:
        import requests
    except ImportError as exc:
        raise SystemExit(
            "requests is required for --smoke-prompt. "
            "pip install -r training/requirements.txt"
        ) from exc

    ollama_cfg = cfg.get("ollama") or {}
    host = ollama_cfg.get("host") or "http://127.0.0.1:11434"
    model = ollama_cfg.get("model")
    if not model:
        raise SystemExit("Config must define ollama.model")
    timeout_s = float(ollama_cfg.get("timeout_s") or 120)

    data_cfg = cfg.get("data") or {}
    system_prompt = data_cfg.get("system_prompt") or (
        "You diagnose SONiC failures and explain the root cause and fix."
    )
    record = {
        "id": "smoke-local",
        "issue": {"title": "orchagent crash during warm reboot"},
        "failure": {
            "body": "ERR swss#orchagent: segfault after kexec warm reboot on multi-ASIC."
        },
    }
    rag_cfg = cfg.get("rag") or {}
    rag_context = ""
    index = load_index_from_cfg(ROOT, cfg)
    if index is not None:
        _query, _hits, rag_context = retrieve_for_record(
            index,
            record,
            top_k=int(rag_cfg.get("top_k") or 4),
            max_query_chars=int(rag_cfg.get("max_query_chars") or 1500),
            max_chars_per_chunk=int(rag_cfg.get("max_chars_per_chunk") or 800),
        )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {
                "role": "user",
                "content": build_user_content(record, rag_context=rag_context),
            },
        ],
        "stream": False,
    }
    url = host.rstrip("/") + "/api/chat"
    print(f"POST {url}")
    resp = requests.post(url, json=body, timeout=timeout_s)
    resp.raise_for_status()
    print(json.dumps(resp.json(), indent=2)[:2000])

def run_sft(
    cfg: dict[str, Any],
    train_jsonl: Path,
    *,
    resume_from_checkpoint: bool | str | Path = False,
) -> Path:
    try:
        import torch
        from datasets import load_dataset
        from peft import LoraConfig
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from trl import SFTConfig, SFTTrainer
    except ImportError as exc:
        raise SystemExit(
            "Missing training deps. Install with:\n"
            "  source .venv/bin/activate\n"
            "  pip install -r training/requirements.txt\n"
            f"Import error: {exc}"
        ) from exc

    model_cfg = cfg.get("model") or {}
    train_cfg = cfg.get("training") or {}
    lora_cfg = cfg.get("lora") or {}

    name_or_path = model_cfg.get("name_or_path")
    if not name_or_path:
        raise SystemExit("config model.name_or_path is required")

    if train_cfg.get("load_in_4bit"):
        try:
            from transformers import BitsAndBytesConfig
        except ImportError as exc:
            raise SystemExit(
                "load_in_4bit requires bitsandbytes (NVIDIA CUDA only)."
            ) from exc
        quant = BitsAndBytesConfig(load_in_4bit=True)
    else:
        quant = None

    output_rel = train_cfg.get("output_dir") or "training/output"
    output_dir = ROOT / output_rel
    output_dir.mkdir(parents=True, exist_ok=True)

    def log(msg: str) -> None:
        print(msg, flush=True)

    log(f"Loading tokenizer: {name_or_path}")
    tokenizer = AutoTokenizer.from_pretrained(
        name_or_path,
        trust_remote_code=bool(model_cfg.get("trust_remote_code", True)),
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    dtype_name = (model_cfg.get("torch_dtype") or "float16").lower()
    dtype_map = {
        "bfloat16": torch.bfloat16,
        "bf16": torch.bfloat16,
        "float16": torch.float16,
        "fp16": torch.float16,
        "float32": torch.float32,
        "fp32": torch.float32,
    }
    torch_dtype = dtype_map.get(dtype_name, torch.float16)

    if torch.cuda.is_available():
        device_map = "auto"
    elif torch.backends.mps.is_available():
        # Avoid accelerate auto-sharding quirks on Apple Silicon.
        device_map = None
    else:
        device_map = "cpu"
        # float16 matmul is unreliable on CPU; force float32 for SFT.
        if torch_dtype in (torch.float16, torch.bfloat16):
            torch_dtype = torch.float32
            dtype_name = "float32"

    log(f"Loading model: {name_or_path} (device_map={device_map}, dtype={dtype_name})")
    model_kwargs: dict[str, Any] = {
        "trust_remote_code": bool(model_cfg.get("trust_remote_code", True)),
        # Prefer `dtype=` (transformers>=4.56); keep torch_dtype fallback below.
        "dtype": torch_dtype if quant is None else None,
    }
    if quant is not None:
        model_kwargs["quantization_config"] = quant
        model_kwargs["device_map"] = "auto"
    elif device_map is not None:
        model_kwargs["device_map"] = device_map

    try:
        model = AutoModelForCausalLM.from_pretrained(name_or_path, **model_kwargs)
    except TypeError:
        model_kwargs.pop("dtype", None)
        model_kwargs["torch_dtype"] = torch_dtype if quant is None else None
        model = AutoModelForCausalLM.from_pretrained(name_or_path, **model_kwargs)
    if device_map is None and torch.backends.mps.is_available():
        log("Moving model to MPS…")
        model.to("mps")
    log("Model loaded.")

    # LoRA needs grad-enabled inputs on frozen base weights.
    model.config.use_cache = False
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()

    peft_config = LoraConfig(
        r=int(lora_cfg.get("r") or 16),
        lora_alpha=int(lora_cfg.get("alpha") or 32),
        lora_dropout=float(lora_cfg.get("dropout") or 0.05),
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=list(
            lora_cfg.get("target_modules")
            or ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
        ),
    )

    dataset = load_dataset("json", data_files=str(train_jsonl), split="train")

    def to_text(example: dict[str, Any]) -> dict[str, str]:
        kwargs: dict[str, Any] = {
            "tokenize": False,
            "add_generation_prompt": False,
        }
        # Qwen3.5 defaults to "thinking" mode; disable for SFT targets.
        try:
            text = tokenizer.apply_chat_template(
                example["messages"],
                chat_template_kwargs={"enable_thinking": False},
                **kwargs,
            )
        except TypeError:
            text = tokenizer.apply_chat_template(example["messages"], **kwargs)
        return {"text": text}

    dataset = dataset.map(to_text, remove_columns=dataset.column_names)

    use_cuda = torch.cuda.is_available()
    use_mps = (not use_cuda) and torch.backends.mps.is_available()
    sft_kwargs: dict[str, Any] = {
        "output_dir": str(output_dir),
        "num_train_epochs": float(train_cfg.get("num_train_epochs") or 1),
        "per_device_train_batch_size": int(
            train_cfg.get("per_device_train_batch_size") or 1
        ),
        "gradient_accumulation_steps": int(
            train_cfg.get("gradient_accumulation_steps") or 8
        ),
        "learning_rate": float(train_cfg.get("learning_rate") or 2e-4),
        "logging_steps": int(train_cfg.get("logging_steps") or 10),
        "save_steps": int(train_cfg.get("save_steps") or 100),
        "seed": int(train_cfg.get("seed") or 42),
        "report_to": [],
        "dataset_text_field": "text",
        "gradient_checkpointing": True,
        # Transformers rejects bf16/fp16 GPU defaults when only CPU is available.
        "use_cpu": not use_cuda and not use_mps,
        "fp16": use_cuda,
        "bf16": False,
    }
    max_len = int(train_cfg.get("max_seq_length") or 1024)
    # TRL versions differ on the length kwarg name.
    try:
        sft_args = SFTConfig(**sft_kwargs, max_length=max_len)
    except TypeError:
        sft_args = SFTConfig(**sft_kwargs, max_seq_length=max_len)

    trainer = SFTTrainer(
        model=model,
        args=sft_args,
        train_dataset=dataset,
        processing_class=tokenizer,
        peft_config=peft_config,
    )
    if resume_from_checkpoint:
        if resume_from_checkpoint is True:
            ckpt: bool | str = True
            log("Resuming SFT from latest checkpoint in output_dir…")
        else:
            ckpt_path = Path(resume_from_checkpoint)
            if not ckpt_path.is_absolute():
                ckpt_path = ROOT / ckpt_path
            if not ckpt_path.exists():
                raise SystemExit(f"Checkpoint not found: {ckpt_path}")
            ckpt = str(ckpt_path)
            log(f"Resuming SFT from {ckpt_path.relative_to(ROOT)}…")
        trainer.train(resume_from_checkpoint=ckpt)
    else:
        log("Starting SFT…")
        trainer.train()
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    log(f"Saved adapter/model → {output_dir.relative_to(ROOT)}")
    return output_dir


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare data and run SFT on the frozen train split."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Path to training config (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on number of train examples",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Only write training/data/train.jsonl; do not run SFT",
    )
    parser.add_argument(
        "--smoke-prompt",
        action="store_true",
        help="POST a sample failure to agent.url (local LLM server check)",
    )
    parser.add_argument(
        "--no-rag",
        action="store_true",
        help="Disable BM25 RAG context even if config rag.enabled is true",
    )
    parser.add_argument(
        "--resume",
        nargs="?",
        const=True,
        default=False,
        metavar="CHECKPOINT",
        help=(
            "Resume SFT from the latest checkpoint under training/output "
            "(or from CHECKPOINT if a path is given)."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    cfg = load_config(args.config)
    if args.no_rag:
        cfg.setdefault("rag", {})["enabled"] = False

    if args.smoke_prompt:
        smoke_prompt(cfg)
        return

    train_jsonl = prepare_dataset(cfg, limit=args.limit)
    if args.prepare_only:
        return

    run_sft(cfg, train_jsonl, resume_from_checkpoint=args.resume)


if __name__ == "__main__":
    main()
