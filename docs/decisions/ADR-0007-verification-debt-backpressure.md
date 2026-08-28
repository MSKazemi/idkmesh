# ADR-0007: Treat independent verification and verification debt as control-plane primitives

- Status: Accepted for experimentation
- Date: 2026-08-28
- Related: issues #5, #14; PR #47

## Context

IDKMesh can already represent a bounded WorkUnit and a worker ResultManifest, but a scalable swarm needs a protocol boundary between worker claims and independent evidence.

It also needs a way to prevent candidate generation from outrunning verification. Raw queue length is insufficient because pending candidates have different risk, uncertainty, blast radius, verification cost, and evidence correlation.

## Decision

### 1. Independent VerificationResult is a separate protocol object

The execution/evidence chain is:

```text
WorkUnit
 -> worker attempt
 -> ResultManifest
 -> independent verifier
 -> VerificationResult
 -> integration/human policy decision
```

A worker cannot self-accept its candidate. A verifier can recommend acceptance, rejection, escalation, or insufficient evidence, but the VerificationResult does not itself authorize a canonical merge/integration action.

`schemas/verification-result-v0.1.schema.json` is the initial experimental contract.

### 2. Verification debt is a first-class flow-control signal

IDKMesh will experimentally model pending verification burden as risk-weighted debt rather than only candidate count.

The initial reference model increases debt with:

- candidate risk;
- uncertainty;
- blast radius/impact;
- estimated verification cost;
- insufficiently diverse/correlated evidence.

This is a controller signal, not a probability or permanent quality score.

### 3. Generation fan-out should respond to verification pressure

The first reference controller is Risk-Weighted Verification Backpressure (RWVB), implemented in `experiments/verification_backpressure.py`.

RWVB:

- prioritizes verifier capacity using risk-clearing pressure per estimated verification cost;
- includes an age/starvation guard;
- reduces generation fan-out when verification debt exceeds capacity watermarks;
- permits fan-out growth again after debt falls into a safe region.

## Rationale

The project objective is verified useful work, not maximum candidate production. If generator count grows while independent evidence capacity stays fixed, verification backlog and escaped-risk pressure can dominate any benefit from additional agents.

Making verification pressure part of the control loop creates negative feedback:

```text
high unverified risk
 -> higher verification pressure
 -> lower generation fan-out
 -> debt clears
 -> generation can expand again
```

This also aligns with IDKMesh's earlier decision that verification must scale with generation.

## Mathematical inspiration

RWVB is inspired by queueing/network MaxWeight/backpressure methods, especially work originating with Tassiulas and Ephremides and later stochastic-network optimization methods.

The classical throughput/stability theorems do **not** automatically transfer to IDKMesh's heuristic risk/verification model. The analogy is a research hypothesis and must be benchmarked against simpler baselines.

See `docs/research/VERIFICATION_DEBT_AND_BACKPRESSURE.md`.

## Consequences

Positive:

- worker self-report and independent evidence have an explicit trust boundary;
- verifier independence/correlation can be measured;
- the local Verified Swarm Runner has a concrete verification artifact to produce;
- verification capacity can actively constrain candidate-generation rate;
- issue #14 now has an executable algorithmic baseline.

Costs/risks:

- risk and cost estimates may be wrong or gameable;
- aggressive feedback parameters can oscillate;
- high-risk work can monopolize verifier capacity;
- evidence diversity is difficult to estimate robustly;
- more protocol objects increase implementation complexity.

## Required experiments before stronger adoption

Compare FIFO, highest-risk-first, cheapest-first, and RWVB under controlled workloads with seeded defects and increasing generation fan-out. Measure escaped defects, accepted throughput, total verification debt, queue latency, verifier cost, human attention, false rejection, and evidence correlation.

Parameters remain experimental until evidence supports defaults.

## Implementation references

- `docs/research/VERIFICATION_DEBT_AND_BACKPRESSURE.md`
- `docs/research/VERIFICATION_BACKPRESSURE_BENCHMARK.md`
