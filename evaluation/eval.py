#!/usr/bin/env python3
"""
Evaluate an agent on the frozen test split.

Pipeline:
  1. Load test ids from data/splits.json
  2. POST each failure (no gold) to the agent endpoint
  3. Score each prediction with configured Groq judges (0–1)
  4. Print a brief report and write JSON results

Usage:
  python evaluation/eval.py
  python evaluation/eval.py --limit 5 --agent-url http://localhost:8000/predict
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


def agent_payload(
    record: dict[str, Any],
    *,
    rag_context: str = "",
    rag_hits: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    issue = record.get("issue") or {}
    failure = record.get("failure") or {}
    return {
        "id": record.get("id"),
        "issue": {"title": issue.get("title") or ""},
        "failure": {"body": failure.get("body") or ""},
        "rag_context": rag_context or None,
        "rag_hits": rag_hits or [],
        # Same text the SFT user turn uses — agents should prefer this.
        "user_message": build_user_content(record, rag_context=rag_context),
    }


def call_agent(
    url: str,
    payload: dict[str, Any],
    *,
    timeout_s: float,
    headers: dict[str, str] | None,
) -> str:
    resp = requests.post(
        url,
        json=payload,
        headers=headers or {},
        timeout=timeout_s,
    )
    resp.raise_for_status()
    ctype = (resp.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        data = resp.json()
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            if "prediction" in data:
                return str(data["prediction"])
            if "output" in data:
                return str(data["output"])
            raise ValueError(f"Agent JSON missing 'prediction': {data!r}")
        raise ValueError(f"Unexpected agent JSON type: {type(data)}")
    text = resp.text.strip()
    if not text:
        raise ValueError("Agent returned empty body")
    return text


def parse_score(text: str) -> float | None:
    match = FLOAT_RE.search(text or "")
    if not match:
        return None
    try:
        value = float(match.group(0))
    except ValueError:
        return None
    return max(0.0, min(1.0, value))


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
            if resp.status_code == 429 and attempt == 0:
                time.sleep(2.0)
                continue
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
                f"  judge {judge.get('name')}: {last_error}",
                file=sys.stderr,
            )
            return None
    return None


def mean_or_none(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def evaluate(
    cfg: dict[str, Any],
    *,
    agent_url: str | None = None,
    limit: int | None = None,
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
    agent_cfg = cfg.get("agent") or {}
    url = agent_url or agent_cfg.get("url") or "http://127.0.0.1:8000/predict"
    timeout_s = float(agent_cfg.get("timeout_s") or 120)
    headers = dict(agent_cfg.get("headers") or {})

    rag_cfg = cfg.get("rag") or {}
    rag_enabled = bool(rag_cfg.get("enabled", False))
    index = load_index_from_cfg(ROOT, cfg) if rag_enabled else None
    top_k = int(rag_cfg.get("top_k") or 4)
    max_query_chars = int(rag_cfg.get("max_query_chars") or 1500)
    max_chars_per_chunk = int(rag_cfg.get("max_chars_per_chunk") or 800)

    results: list[dict[str, Any]] = []
    agent_errors = 0
    judge_failures = 0
    rag_hit_total = 0

    for record_id in test_ids:
        print(f"[{len(results) + 1}/{len(test_ids)}] {record_id}", flush=True)
        try:
            record = load_record(record_id)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            agent_errors += 1
            results.append(
                {
                    "id": record_id,
                    "error": f"load_failed: {exc}",
                    "prediction": None,
                    "scores": {},
                    "mean": None,
                }
            )
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
            rag_hit_total += len(hits)
        payload = agent_payload(
            record, rag_context=rag_context, rag_hits=rag_hits_meta
        )

        try:
            prediction = call_agent(
                url, payload, timeout_s=timeout_s, headers=headers
            )
        except Exception as exc:  # noqa: BLE001
            agent_errors += 1
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
            if score is None:
                judge_failures += 1

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

    datapoint_means = [r["mean"] for r in results if r["mean"] is not None]
    overall_mean = mean_or_none(datapoint_means)

    by_judge: dict[str, float | None] = {}
    for judge in judges:
        name = judge.get("name") or judge.get("model") or "unnamed"
        vals = [
            r["scores"][name]
            for r in results
            if name in r.get("scores", {}) and r["scores"][name] is not None
        ]
        by_judge[name] = mean_or_none(vals)

    scored_n = len(datapoint_means)
    summary = {
        "test_n": len(test_ids),
        "scored": scored_n,
        "agent_errors": agent_errors,
        "judge_failures": judge_failures,
        "overall_mean": overall_mean,
        "by_judge": by_judge,
        "rag": {
            "enabled": rag_enabled and index is not None,
            "top_k": top_k if index is not None else 0,
            "hit_total": rag_hit_total,
            "mean_hits": (rag_hit_total / scored_n) if scored_n else 0.0,
        },
    }

    output = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "agent_url": url,
        "judges": [
            {"name": j.get("name"), "model": j.get("model")} for j in judges
        ],
        "summary": summary,
        "results": results,
    }
    return output


def print_report(output: dict[str, Any]) -> None:
    s = output["summary"]
    overall = s["overall_mean"]
    overall_s = f"{overall:.4f}" if overall is not None else "n/a"
    print()
    print("Evaluation report")
    print(
        f"  test_n={s['test_n']} scored={s['scored']} "
        f"agent_errors={s['agent_errors']}"
    )
    print(f"  overall_mean={overall_s}")
    print("  by_judge:")
    for name, mean in (s.get("by_judge") or {}).items():
        mean_s = f"{mean:.4f}" if mean is not None else "n/a"
        print(f"    {name}: {mean_s}")


def write_results(output: dict[str, Any], results_dir: Path) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    path = results_dir / f"eval-{stamp}.json"
    with path.open("w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return path


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
        "--agent-url",
        default=None,
        help="Override agent.url from config",
    )
    parser.add_argument(
        "--no-rag",
        action="store_true",
        help="Disable BM25 RAG context even if config rag.enabled is true",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    cfg = load_config(args.config)
    if args.no_rag:
        cfg.setdefault("rag", {})["enabled"] = False
    output = evaluate(cfg, agent_url=args.agent_url, limit=args.limit)
    print_report(output)

    results_rel = cfg.get("results_dir") or "evaluation/results"
    results_dir = ROOT / results_rel
    out_path = write_results(output, results_dir)
    print(f"  wrote {out_path.relative_to(ROOT)}")
    return output


if __name__ == "__main__":
    main()
