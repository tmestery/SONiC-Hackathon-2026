# SONiC Test Failure Root-Cause Analysis

**AI-assisted debugging and triage of SONiC test failures — SONiC Hackathon 2026**

<p align="center">
  <img src="assets/sonic-rca-logo.jpg" alt="SONiC RCA — Test Failure Root-Cause Analysis" width="900">
</p>

This project delivers the first dataset, benchmark, and tooling for automated
root-cause analysis of [SONiC](https://sonicfoundation.dev/) test failures. It
enables the community to evaluate how well language models — small and large —
can diagnose a failure directly from its test log or `show techsupport` dump.

## Problem Statement

`sonic-mgmt` runs continuously across nightly and PR pipelines, and every
failure must be triaged by hand: is it a real regression, a known flaky test,
or an environmental issue? Today that knowledge lives only in engineers'
heads. Nothing captures it, every contributor relearns the same failure
patterns, and the problem compounds as the test suite and platform list grow.
No dataset, benchmark, or tool currently addresses structured root-cause
analysis from SONiC test logs.

## Components

### 1. Dataset

A cleaned dataset pairing real SONiC test failures with their verified root
causes, mined from closed PRs and issues in
[sonic-mgmt](https://github.com/sonic-net/sonic-mgmt),
[sonic-buildimage](https://github.com/sonic-net/sonic-buildimage), and
[sonic-swss](https://github.com/sonic-net/sonic-swss), supplemented with
failures reproduced on the `sonic-vs` virtual switch.

### 2. Benchmark

A public HuggingFace benchmark that scores any model's ability to diagnose a
failure from its log or `show techsupport` dump alone, allowing the community
to rank small language models (SLMs) against large ones on this task.

### 3. Proof of Concept — CLI Extension

A working `sonic-utilities` CLI extension that applies retrieval-augmented
generation (RAG) over the dataset, combined with a lightweight triage
classifier and a confidence layer to distinguish known-flaky tests from real
regressions. Cost and latency are reported to assess feasibility on
constrained hardware.

## Repository Structure

```
.
├── data/                 # Dataset: mined failures, cleaned entries, SLM context
│   ├── buildimage/       #   From sonic-buildimage PRs and issues
│   ├── management/       #   From sonic-mgmt PRs and issues
│   ├── swss/             #   From sonic-swss PRs and issues
│   └── rag/              #   SONiC docs RAG corpus (retrieval only)
└── docs/                 # Project documentation
    ├── SONiC-Hackathon-2026-Proposal.md
    └── guides/           #   Dataset quality and benchmarking guides
```

See [`data/readme.md`](data/readme.md) for the dataset layout and contribution
ground rules.

## Documentation

- [Project Proposal](docs/SONiC-Hackathon-2026-Proposal.md)
- [High-Quality Dataset Guide](docs/guides/high-quality-dataset-guide.md)
- [LLM/SLM Benchmark Guide](docs/guides/llm-slm-benchmark-guide.md)

## Status

This project is under active development for the SONiC Hackathon 2026.

## Contributers

Tyler Mestery, Mason Hart, Andy Pham
