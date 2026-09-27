# LLM/SLM Benchmarking — Condensed Guide

## 1. Define Task & Dataset
- Pick task type (classification, QA, summarization, code gen, extraction, chat).
- Build input→expected-output dataset; split into train/dev/test (keep test set untouched).

## 2. Standardize Setup
- Choose models to compare; log name, params, quantization, context length, hardware, framework, prompt template.
- Use identical dataset, prompts, and generation settings across all models.

## 3. Measure Quality
- Pick metrics per task (Accuracy/F1, EM/F1, ROUGE/BERTScore, Pass@k, etc.).
- Use human or LLM-based eval for generative tasks.
- Track failure modes: hallucinations, bad reasoning, missing info, long-context/OOD failures.

## 4. Measure Performance & Cost
- **Performance:** latency, TTFT, tokens/sec, throughput, RAM/VRAM, CPU/GPU use — report mean/median/P95 over multiple runs.
- **Cost:** $/request, $/1K–1M tokens, total cost (hosted); hardware + runtime cost (local).
- **Derived:** quality/$, quality/sec, quality/GB VRAM.

## 5. Build a Reproducible Harness
- Pipeline: Dataset → Prompt Builder → Model → Output → Evaluator → Metrics → Results.
- Save raw per-example results (JSONL) for failure inspection, plus a summary CSV.
- Standard structure: `data/`, `prompts/`, `models/`, `benchmark.py`, `evaluate.py`, `results/`.

## 6. Analyze Trade-offs
- Compare models on quality vs. latency vs. cost vs. resource footprint — not a single score.
- Decision flow: Does it meet quality bar? → Is it faster/cheaper? → Fits hardware? → Handles edge cases?

## 7. Core Principle
- Benchmark on your actual workload, not just public leaderboards.
- Goal: smallest/cheapest/fastest model that meets **your** quality bar — not the biggest model.
