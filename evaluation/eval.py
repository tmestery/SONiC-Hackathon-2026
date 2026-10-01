#!/usr/bin/env python3
"""
Evaluate an agent on the frozen test split.

Pipeline:
  1. Load test ids from data/splits.json
  2. Query the local Ollama model for each failure (no gold)
  3. Score each prediction with configured Groq judges (0–1)
  4. Print a brief report and write JSON results

Usage:
  python evaluation/eval.py
    python evaluation/eval.py --limit 5 --ollama-model qwen3:1.7b
  python evaluation/eval.py --resume evaluation/results/eval-20260929-214804.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import requests
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.yaml"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_SYSTEM_PROMPT = (
    "You diagnose SONiC failures and explain the root cause and fix."
)
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

FLOAT_RE = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    if not isinstance(cfg, dict):
        raise SystemExit(f"Config must be a mapping: {path}")
    if not cfg.get("judges"):
        raise SystemExit("Config must define at least one judge under 'judges'")
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


def load_test_ids(splits_file: Path, limit: int | None) -> list[str]:
    with splits_file.open(encoding="utf-8") as fh:
        splits = json.load(fh)
    ids = list(splits.get("test") or [])
    if limit is not None:
        ids = ids[: max(0, limit)]
    return ids


def agent_user_content(
    record: dict[str, Any],
    *,
    rag_context: str = "",
) -> str:
    """Build the Ollama user turn (title + failure + optional RAG docs)."""
    return build_user_content(record, rag_context=rag_context)

def call_ollama(
    host: str,
    model: str,
    *,
    system_prompt: str,
    user_content: str,
    timeout_s: float,
) -> str:
    url = host.rstrip("/") + "/api/chat"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        # Keep evaluation output aligned with the non-thinking SFT targets.
        "think": False,
        "stream": False,
    }
    resp = requests.post(url, json=body, timeout=timeout_s)
    resp.raise_for_status()
    data = resp.json()
    content = (data.get("message") or {}).get("content")
    if not content:
        raise ValueError(f"Ollama response missing message content: {data!r}")
    return content.strip()


def parse_score(text: str) -> float | None:
    match = FLOAT_RE.search(text or "")
    if not match:
        return None
    try:
        value = float(match.group(0))
    except ValueError:
        return None
    return max(0.0, min(1.0, value))


def describe_groq_error(resp: requests.Response, model: str, judge_name: str) -> str:
    """Build a descriptive error message for a failed Groq response, calling
    out token/rate limit exhaustion specifically since it needs a different
    response (wait/backoff) than a generic API failure."""
    try:
        detail = resp.json().get("error") or {}
    except ValueError:
        detail = {}
    message = detail.get("message") or resp.text
    err_type = (detail.get("type") or detail.get("code") or "").lower()

    if resp.status_code == 429:
        if "token" in err_type or "token" in message.lower():
            return (
                f"judge '{judge_name}' (model {model}) hit its Groq TOKEN limit: "
                f"{message}. This model's free-tier token quota is exhausted for "
                f"now; wait for the quota to reset or swap in a different judge "
                f"model in evaluation/config.yaml."
            )
        return (
            f"judge '{judge_name}' (model {model}) hit a Groq RATE limit: "
            f"{message}. Retry after a short delay or reduce request concurrency."
        )
    return f"judge '{judge_name}' (model {model}) Groq API error [{resp.status_code}]: {message}"


def call_judge(
    judge: dict[str, Any],
    *,
    title: str,
    prediction: str,
    gold: str,
    api_key: str,
) -> float | None:
    prompt = (judge.get("prompt") or "").format(
        title=title,
        prediction=prediction,
        gold=gold,
    )
    model = judge.get("model")
    judge_name = judge.get("name") or model or "unnamed"
    if not model:
        raise ValueError(f"Judge {judge.get('name')!r} missing model")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            resp = requests.post(GROQ_URL, headers=headers, json=body, timeout=60)
            if resp.status_code == 429:
                print(f"  {describe_groq_error(resp, model, judge_name)}", file=sys.stderr)
                if attempt == 0:
                    time.sleep(2.0)
                    continue
                return None
            resp.raise_for_status()
            data = resp.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            return parse_score(content)
        except Exception as exc:  # noqa: BLE001 — surface per-judge failure as null
            last_error = exc
            if attempt == 0:
                time.sleep(1.0)
                continue
            print(
                f"  judge '{judge_name}' (model {model}) failed: {last_error}",
                file=sys.stderr,
            )
            return None
    return None


def mean_or_none(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def build_summary(
    *,
    test_ids: list[str],
    results: list[dict[str, Any]],
    judges: list[dict[str, Any]],
    rag_enabled: bool,
    top_k: int,
) -> dict[str, Any]:
    datapoint_means = [r["mean"] for r in results if r.get("mean") is not None]
    overall_mean = mean_or_none(datapoint_means)
    by_judge: dict[str, float | None] = {}
    for judge in judges:
        name = judge.get("name") or judge.get("model") or "unnamed"
        vals = [
            r["scores"][name]
            for r in results
            if isinstance(r.get("scores"), dict)
            and name in r["scores"]
            and r["scores"][name] is not None
        ]
        by_judge[name] = mean_or_none(vals)

    agent_errors = sum(1 for r in results if r.get("error"))
    judge_failures = 0
    for r in results:
        scores = r.get("scores") or {}
        if not isinstance(scores, dict):
            continue
        judge_failures += sum(1 for v in scores.values() if v is None)

    rag_hit_total = sum(int(r.get("rag_hits") or 0) for r in results)
    scored_n = len(datapoint_means)
    return {
        "test_n": len(test_ids),
        "done": len(results),
        "remaining": max(0, len(test_ids) - len(results)),
        "scored": scored_n,
        "agent_errors": agent_errors,
        "judge_failures": judge_failures,
        "overall_mean": overall_mean,
        "by_judge": by_judge,
        "rag": {
            "enabled": rag_enabled,
            "top_k": top_k if rag_enabled else 0,
            "hit_total": rag_hit_total,
            "mean_hits": (rag_hit_total / len(results)) if results else 0.0,
        },
        "complete": len(results) >= len(test_ids),
    }


def build_output(
    *,
    host: str,
    model: str,
    judges: list[dict[str, Any]],
    test_ids: list[str],
    results: list[dict[str, Any]],
    rag_enabled: bool,
    top_k: int,
    checkpoint_path: str | None = None,
) -> dict[str, Any]:
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "ollama_host": host,
        "ollama_model": model,
        "checkpoint": checkpoint_path,
        "judges": [
            {"name": j.get("name"), "model": j.get("model")} for j in judges
        ],
        "summary": build_summary(
            test_ids=test_ids,
            results=results,
            judges=judges,
            rag_enabled=rag_enabled,
            top_k=top_k,
        ),
        "results": results,
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    tmp.replace(path)


def load_checkpoint(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise SystemExit(f"Invalid checkpoint (missing results list): {path}")
    return data


def resolve_checkpoint_path(
    results_dir: Path,
    *,
    resume: Path | None,
    output: Path | None,
) -> Path:
    if resume is not None:
        path = resume if resume.is_absolute() else ROOT / resume
        if not path.exists():
            raise SystemExit(f"Checkpoint not found: {path}")
        return path
    if output is not None:
        return output if output.is_absolute() else ROOT / output
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    return results_dir / f"eval-{stamp}.json"


def evaluate(
    cfg: dict[str, Any],
    *,
    ollama_host: str | None = None,
    ollama_model: str | None = None,
    limit: int | None = None,
    checkpoint_path: Path,
    resume: bool = False,
) -> dict[str, Any]:
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise SystemExit("GROQ_API_KEY not set (expected in .env)")

    splits_rel = cfg.get("splits_file") or "data/splits.json"
    splits_file = ROOT / splits_rel
    if not splits_file.exists():
        raise SystemExit(f"Missing splits file: {splits_file}")

    cfg_limit = cfg.get("limit")
    effective_limit = limit if limit is not None else cfg_limit
    if effective_limit is not None:
        effective_limit = int(effective_limit)

    test_ids = load_test_ids(splits_file, effective_limit)
    judges = cfg.get("judges") or []
    ollama_cfg = cfg.get("ollama") or {}
    host = ollama_host or ollama_cfg.get("host") or "http://127.0.0.1:11434"
    model = ollama_model or ollama_cfg.get("model")
    if not model:
        raise SystemExit("Config must define ollama.model (or pass --ollama-model)")
    timeout_s = float(ollama_cfg.get("timeout_s") or 120)
    system_prompt = ollama_cfg.get("system_prompt") or DEFAULT_SYSTEM_PROMPT

    rag_cfg = cfg.get("rag") or {}
    rag_enabled = bool(rag_cfg.get("enabled", False))
    index = load_index_from_cfg(ROOT, cfg) if rag_enabled else None
    top_k = int(rag_cfg.get("top_k") or 4)
    max_query_chars = int(rag_cfg.get("max_query_chars") or 1500)
    max_chars_per_chunk = int(rag_cfg.get("max_chars_per_chunk") or 800)
    rag_on = bool(rag_enabled and index is not None)

    try:
        ckpt_rel = str(checkpoint_path.relative_to(ROOT))
    except ValueError:
        ckpt_rel = str(checkpoint_path)

    results: list[dict[str, Any]] = []
    if resume and checkpoint_path.exists():
        prior = load_checkpoint(checkpoint_path)
        results = list(prior.get("results") or [])
        print(
            f"Resuming {ckpt_rel}: {len(results)} done, "
            f"{max(0, len(test_ids) - len(results))} remaining",
            flush=True,
        )
    done_ids = {r.get("id") for r in results if r.get("id")}
    pending_ids = [rid for rid in test_ids if rid not in done_ids]
    if not pending_ids and results:
        print("Checkpoint already complete; refreshing summary.", flush=True)

    def persist() -> dict[str, Any]:
        output = build_output(
            host=host,
            model=model,
            judges=judges,
            test_ids=test_ids,
            results=results,
            rag_enabled=rag_on,
            top_k=top_k,
            checkpoint_path=ckpt_rel,
        )
        atomic_write_json(checkpoint_path, output)
        return output

    # Create/refresh file immediately so a crash mid-first-example still leaves a path.
    output = persist()
    print(f"Checkpoint → {ckpt_rel}", flush=True)

    total = len(test_ids)
    for record_id in pending_ids:
        idx = len(results) + 1
        print(f"[{idx}/{total}] {record_id}", flush=True)
        try:
            record = load_record(record_id)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            results.append(
                {
                    "id": record_id,
                    "error": f"load_failed: {exc}",
                    "prediction": None,
                    "scores": {},
                    "mean": None,
                }
            )
            persist()
            continue

        title = (record.get("issue") or {}).get("title") or ""
        gold = (record.get("resolution") or {}).get("description") or ""
        rag_context = ""
        rag_hits_meta: list[dict[str, Any]] = []
        if index is not None:
            _query, hits, rag_context = retrieve_for_record(
                index,
                record,
                top_k=top_k,
                max_query_chars=max_query_chars,
                max_chars_per_chunk=max_chars_per_chunk,
            )
            rag_hits_meta = [h.to_meta() for h in hits]
        user_content = agent_user_content(record, rag_context=rag_context)

        try:
            prediction = call_ollama(
                host,
                model,
                system_prompt=system_prompt,
                user_content=user_content,
                timeout_s=timeout_s,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  agent error: {exc}", file=sys.stderr)
            results.append(
                {
                    "id": record_id,
                    "error": f"agent_failed: {exc}",
                    "prediction": None,
                    "scores": {},
                    "mean": None,
                    "rag_hits": len(rag_hits_meta),
                }
            )
            persist()
            continue

        scores: dict[str, float | None] = {}
        for judge in judges:
            name = judge.get("name") or judge.get("model") or "unnamed"
            score = call_judge(
                judge,
                title=title,
                prediction=prediction,
                gold=gold,
                api_key=api_key,
            )
            scores[name] = score

        valid = [s for s in scores.values() if s is not None]
        results.append(
            {
                "id": record_id,
                "error": None,
                "prediction": prediction,
                "scores": scores,
                "mean": mean_or_none(valid),
                "rag_hits": len(rag_hits_meta),
            }
        )
        persist()

    return persist()


def print_report(output: dict[str, Any]) -> None:
    s = output["summary"]
    overall = s["overall_mean"]
    overall_s = f"{overall:.4f}" if overall is not None else "n/a"
    print()
    print("Evaluation report")
    print(
        f"  test_n={s['test_n']} done={s.get('done', s['scored'])} "
        f"scored={s['scored']} agent_errors={s['agent_errors']}"
    )
    if not s.get("complete", True):
        print(f"  remaining={s.get('remaining')} (incomplete checkpoint)")
    print(f"  overall_mean={overall_s}")
    print("  by_judge:")
    for name, mean in (s.get("by_judge") or {}).items():
        mean_s = f"{mean:.4f}" if mean is not None else "n/a"
        print(f"    {name}: {mean_s}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate agent predictions on the frozen test split."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Path to eval config (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on number of test examples",
    )
    parser.add_argument(
        "--ollama-host",
        default=None,
        help="Override ollama.host from config",
    )
    parser.add_argument(
        "--ollama-model",
        default=None,
        help="Override ollama.model from config",
    )
    parser.add_argument(
        "--no-rag",
        action="store_true",
        help="Disable BM25 RAG context even if config rag.enabled is true",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Checkpoint/results JSON path (default: evaluation/results/eval-<stamp>.json)",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        default=None,
        help="Resume from an existing checkpoint JSON (skips completed ids)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    cfg = load_config(args.config)
    if args.no_rag:
        cfg.setdefault("rag", {})["enabled"] = False

    results_rel = cfg.get("results_dir") or "evaluation/results"
    results_dir = ROOT / results_rel
    checkpoint_path = resolve_checkpoint_path(
        results_dir, resume=args.resume, output=args.output
    )

    output = evaluate(
        cfg,
        ollama_host=args.ollama_host,
        ollama_model=args.ollama_model,
        limit=args.limit,
        checkpoint_path=checkpoint_path,
        resume=args.resume is not None,
    )
    print_report(output)
    try:
        rel = checkpoint_path.relative_to(ROOT)
    except ValueError:
        rel = checkpoint_path
    print(f"  wrote {rel}")
    return output


if __name__ == "__main__":
    main()
