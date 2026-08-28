# Random continuation: verification scaling benchmark

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`  
**Selected work:** issue #14 — Make verification scale with generation

## User direction

The project owner asked ChatGPT to continue useful work in IDKMesh, select one task at random, and work on it. The standing project rule also requires project conversation outcomes and implementation decisions to be preserved in the public repository.

## Random selection and repository check

An open-issue inventory was inspected and issue #14 was selected as the random continuation target.

Before creating new code, the repository was checked for overlapping work. The important discovery was that #14 already had a real foundation on `main`:

- `experiments/verification_backpressure.py` implements Risk-Weighted Verification Backpressure (RWVB);
- `docs/research/VERIFICATION_DEBT_AND_BACKPRESSURE.md` defines the model and its limits;
- ADR-0007 records verification-debt backpressure as an experimental architectural direction;
- Phase 0 CI already exercises the one-window controller self-test;
- issue #14 explicitly identified the next evidence step as comparing FIFO, highest-risk-first, cheapest-first, and RWVB under seeded defects and increasing generation fan-out.

The continuation therefore **did not create a second verification controller**. It extended the existing one into the missing temporal benchmark.

## Implemented slice

A fresh branch was created:

`experiment/verification-backpressure-benchmark`

The branch adds:

1. `experiments/verification_backpressure_benchmark.py`
   - deterministic multi-window queue simulation;
   - FIFO, highest-risk-first, cheapest-first, RWVB-fixed, and RWVB-adaptive policies;
   - seeded synthetic defects and predetermined verifier-detection outcomes;
   - identical workload streams for fixed-policy comparisons;
   - adaptive generation fan-out driven by the existing RWVB controller;
   - raw queue, debt, wait, verifier-cost, defect, exposure, throughput, and fan-out metrics;
   - explicit `integration_authority = none` safety boundary.

2. `tests/test_verification_backpressure_benchmark.py`
   - workload reproducibility;
   - verifier-capacity conservation;
   - same-stream fairness across fixed policies;
   - exact run replay;
   - overloaded adaptive contraction;
   - underloaded adaptive expansion;
   - no merge/acceptance authority;
   - complete benchmark matrix coverage.

3. `experiments/results/E014-verification-backpressure-20-seed-summary.json`
   - compact public 20-seed reference result;
   - enough provenance/configuration to reproduce full per-run output;
   - limitations recorded with the result rather than hidden in prose.

4. `docs/research/VERIFICATION_BACKPRESSURE_BENCHMARK.md`
   - methodology, fairness rule, metrics, reference results, interpretation, and next real-evidence step.

5. Phase 0 CI extension
   - runs the new benchmark self-test and dedicated unit-test module;
   - performs synthetic scheduling/control arithmetic only;
   - does not execute candidate code or grant new write/integration authority.

## Reference observation

In the synthetic 20-seed sweep, fixed fanout 8 or 12 generated work substantially faster than an 8-cost-unit verification window could absorb. Fixed policies therefore accumulated large pending queues.

Adaptive RWVB reacted differently: it reduced generation toward roughly 4–5 candidates/window and left a much smaller pending queue and verification debt. At initial fanout 2 it moved in the opposite direction and expanded generation to use spare verification capacity.

This is a controller-behavior result, **not evidence that RWVB is optimal**.

Other policies exposed useful trade-offs:

- cheapest-first verified more candidates under overload but could retain high risk-weighted debt;
- highest-risk-first strongly reduced synthetic pending defect exposure in several overloaded cases;
- fixed RWVB scheduling without fan-out control did not prevent queue growth when generation remained above verification capacity.

Those negative/comparative observations are preserved because the research goal is to discover where a mechanism helps or hurts, not to prove a preferred algorithm.

## Decision

The bounded result of this continuation is:

> Treat verification scaling as a closed-loop queue/control experiment. Compare scheduling and generation-control policies on identical evidence streams, preserve raw metrics, and allow simple baselines to outperform RWVB on individual objectives.

The next meaningful step for #14 is **real evidence**, not more synthetic complexity: feed measured WorkUnit/ResultManifest/VerificationResult timing, risk, correlation, failure, and human-attention signals from the local Verified Swarm Runner into the same benchmark shape.

## Safety and integration

This work does not:

- merge itself;
- approve itself;
- change branch protection;
- execute untrusted candidate code;
- treat verifier output as automatic integration authority;
- claim synthetic probabilities are real agent performance;
- claim classical backpressure throughput-optimality applies to IDKMesh.

Independent review and normal repository integration remain required.
