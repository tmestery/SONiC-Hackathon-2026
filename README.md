# SONiC Hackathon 2026

## Proposal
Our repository will contain:

(1) a cleaned dataset pairing real SONiC test failures with their true root causes, mined from closed sonic-mgmt/sonic-buildimage PRs and issues plus failures we reproduce on the sonic-vs virtual switch; 

(2) a public HuggingFace benchmark scoring any model's ability to diagnose a failure from its log or show techsupport dump alone, so the community can rank small vs. large models on this task; and 

(3) a working PoC - a sonic-utilities CLI extension - using retrieval-augmented generation over this dataset with a lightweight triage classifier and confidence layer to flag known-flaky tests vs. real regressions, reporting cost/latency for feasibility on constrained hardware. New for SONiC: no existing dataset, benchmark, or tool addresses structured root-cause analysis from test logs today.