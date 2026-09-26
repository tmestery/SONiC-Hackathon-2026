# Topic: AI + debugging & root causing test failures, analyzing test logs
- Tune Small Language Model (SLM)
    - Look for best base model for task
    - In-context learning
    - A lightweight supervised classifier for the triage bucket
    - A confidence/calibration layer
    - Evaluation Methodology
    - Cost/latency mention
- Find best context to feed it
- Look into if Retrieval Augmented Generation (RAG) is a valuable tool here
- Focus on Proof of Concept (PoC)
- Create + Clean datasets and look at:
    - Root cause test failures
    - Analyzation of test logs
    - Debugging
- Create a Benchmark, and put it on HuggingFace
    - Github/Forum Issues
    - Old tickets
    - Train on common outputs (test with virtual switch)
    - Documentation
    - Get University data
    - Benchmark models, and determine which ones perform best
        - SLMs + LLMs (optional)
- See if we can compress existing models to fit on the switch (optional)

## Proposal:
Our repository will contain (1) a cleaned dataset pairing real SONiC test failures with their true root causes, mined from closed sonic-mgmt/sonic-buildimage PRs and issues plus failures we reproduce on the sonic-vs virtual switch; (2) a public HuggingFace benchmark scoring any model's ability to diagnose a failure from its log or show techsupport dump alone, so the community can rank small vs. large models on this task; and (3) a working PoC - a sonic-utilities CLI extension - using retrieval-augmented generation over this dataset with a lightweight triage classifier and confidence layer to flag known-flaky tests vs. real regressions, reporting cost/latency for feasibility on constrained hardware. New for SONiC: no existing dataset, benchmark, or tool addresses structured root-cause analysis from test logs today.

## What Challenge/Problem does it address?
sonic-mgmt runs constantly across nightly and PR pipelines, and every failure has to get triaged by hand. Is it a real regression, a known flaky test, or just an environmental issue? Right now that knowledge only lives in engineers' heads. Nothing captures it, so every contributor ends up relearning the same failure patterns on their own, and it only gets worse as the test suite and platform list keep growing. There's also no dataset or benchmark for this in SONiC today, so we can't even say whether an automated approach would actually help until one exists.
