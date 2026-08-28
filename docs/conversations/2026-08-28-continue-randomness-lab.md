# Conversation Record — Continue: Executable Randomness Lab

**Date:** 2026-08-28

## Project-owner instruction

The project owner asked IDKMesh work to continue in the canonical public repository.

## Repository assessment

Before making a new change, the active repository state was inspected rather than adding more theory blindly.

Key findings:

- the roadmap already defines the Phase 0 experimental kernel and a concrete immediate backlog;
- the canonical Work Unit / ResultManifest contract work is substantially present;
- PR #34 contains the canonical local-node backend and is waiting on an independent Docker acceptance run (#37);
- PR #36 contains a proposal-first Repository Homeostasis Engine advancing #20;
- issues #24–#28 are intentionally reserved as ACE newcomer Growth Seeds and should not be consumed by the assistant merely to create activity;
- issue #29, the randomness-lab simulator, is an unblocked core research implementation directly connected to the mathematical work in this project.

## Decision

Advance issue #29 on a feature branch rather than writing directly to `main`.

Rationale:

1. The project has identified unprotected `main` as a P0 safety gap (#35).
2. The repository should practice the proposed safety rule: proposal/change -> independent review -> deterministic verification -> integration.
3. Completing reserved Growth Seeds would reduce contribution inventory for newcomers and work against the community-first strategy.

## Implementation

Branch:

`feat/randomness-lab-v0`

Added:

- `experiments/randomness_lab.py`
- `experiments/tests/test_randomness_lab.py`
- `experiments/RANDOMNESS_LAB.md`

The simulator is intentionally standard-library-only and small.

### Policies

The initial interchangeable worker-selection policies are:

- deterministic greedy;
- epsilon-greedy;
- softmax / Boltzmann exploration;
- UCB;
- Thompson sampling;
- power-of-two selection.

### Environment

Synthetic workers have heterogeneous:

- success probabilities;
- cost proxies;
- latency proxies;
- availability under churn.

Every policy receives the same seeded workload for a given trial (common random numbers), improving comparability between policies.

### Correlated-error control

The simulator uses `shared_outcome_probability` as a positive-dependence control. On a configurable fraction of tasks, worker outcomes are generated from a shared random draw; otherwise they use independent draws.

This parameter is explicitly **not** presented as an exact Pearson correlation coefficient. The simulator separately measures realized mean pairwise error correlation and records it in the results.

This avoids claiming mathematical precision that the generator does not enforce.

### Verification invariant

The implementation follows the project rule:

> Randomness controls exploration, not acceptance.

Stochastic policies choose which worker to try. Candidate acceptance remains mediated by an independent verifier model.

The output distinguishes:

- accepted candidates;
- verified successes;
- escaped failures;
- correct candidates rejected by the verifier;
- churn-related failed assignments;
- compute proxy;
- latency;
- human-attention proxy;
- selection diversity;
- realized error correlation.

### Reproducibility and uncertainty

Fixed seeds produce deterministic workloads and policy behavior. Repeated trials produce per-policy summary statistics with 95% normal-approximation intervals.

Machine-readable outputs are JSONL trial records plus a JSON summary envelope.

## Local verification performed before repository publication

The simulator was exercised locally with six policies over a seeded synthetic workload and successfully produced machine-readable output.

Python syntax compilation succeeded.

A four-test `unittest` suite passed, checking:

1. fixed-seed reproducibility;
2. all registered policies are exercised;
3. a perfect verifier never accepts bad work;
4. repeated generation of an identical seeded workload is identical.

No real AI models, external network calls, or production workloads were executed.

## Scientific limitations retained explicitly

The first version is illustrative research infrastructure, not evidence about real IDKMesh performance.

Important limitations include:

- synthetic worker-quality distributions;
- dependence control that does not force an exact correlation coefficient;
- proxy cost/human-attention metrics;
- no queueing network yet;
- no real coding benchmark;
- simple symmetric verifier model.

These limitations are documented so future results cannot silently drift from simulation evidence into real-world claims.

## Next evidence steps

The branch should be reviewed and integrated through a PR. Once accepted, it can support:

- #30 stochastic diversity vs replication;
- #31 power-of-two scheduling under churn;
- #32 evolutionary orchestration;
- #13 collective-intelligence scaling research;
- #14 verification-scaling research.

This conversation record follows `PROJECT_RULES.md`: project-relevant reasoning, decisions, verification performed, and limitations are preserved publicly without private chain-of-thought or secrets.
