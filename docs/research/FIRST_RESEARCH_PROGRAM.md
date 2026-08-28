# IDKMesh First Research Program

This document turns three field-defining questions into the first coordinated IDKMesh research program.

## Research tracks

1. [Issue #13 — Measure the scaling law of collective intelligence](https://github.com/MSKazemi/idkmesh/issues/13)
2. [Issue #14 — Make verification scale with generation](https://github.com/MSKazemi/idkmesh/issues/14)
3. [Issue #15 — Define a formal Work Unit for composable distributed work](https://github.com/MSKazemi/idkmesh/issues/15)

These tracks should not become three isolated projects. They share one experimental substrate.

---

## Unifying hypothesis

A large human+AI mesh becomes useful only when three things scale together:

```text
                 collective capability
                         /\
                        /  \
                       /    \
                      /      \
                     /        \
          Work Units ---------- verification
        composability           trust
```

More workers are useful only if work can be decomposed into composable units and verification can keep up with the resulting output.

A compact hypothesis is:

`VerifiedProgress = GeneratedValue * Composability * VerificationConfidence - CoordinationCost - FailureCost`

This expression is a research scaffold, not a settled model. Every term should eventually have an operational definition.

---

## Shared experimental object

Every experiment should produce a common event record so results from different orchestration strategies can be compared.

Candidate event fields:

```yaml
experiment_id: string
run_id: string
work_unit_id: string
parent_work_unit_ids: []
worker_id: string
worker_type: human | ai | compute
worker_family: string
strategy: string
started_at: timestamp
finished_at: timestamp
input_context_bytes: number
output_bytes: number
compute_cost: number
human_attention_seconds: number
messages_sent: number
validation_cost: number
validator_ids: []
validation_result: pass | fail | uncertain
hidden_test_score: number
escaped_defects: number
regressions: number
security_findings: number
confidence: number
provenance: object
```

The schema should evolve through versioned proposals rather than silently changing.

---

## Phase 0 — Make experiments reproducible

Before trying to prove that large collectives work, establish a minimal scientific harness.

### Deliverables

- experiment manifest format;
- deterministic/replayable task fixtures where possible;
- hidden-test interface;
- standardized cost accounting;
- event/result schema;
- seed and model/configuration recording;
- artifact provenance;
- a simple results summarizer;
- explicit negative-result reporting.

### Rule

**No architecture should be declared better from a single demonstration.**

Each comparison should specify in advance:

- hypothesis;
- baselines;
- workload;
- independent variables;
- dependent variables;
- budget;
- repetitions/seeds;
- stopping rule;
- acceptance/rejection criterion.

---

## Phase 1 — Establish the one-worker baseline

The mesh needs a reference point before adding complexity.

Run representative tasks with:

1. one strong worker/model;
2. one smaller worker/model;
3. one human-assisted baseline where practical.

Measure quality, time, compute, human attention, and verification cost.

This establishes the denominator for every later claim about collective advantage.

---

## Phase 2 — Scale generation without changing decomposition

Hold the task representation approximately fixed and vary worker count:

`N = 1, 2, 5, 10, 20, ...`

Compare homogeneous and heterogeneous groups.

Primary goal: estimate marginal verified value:

`MV(N+1) = VerifiedUtility(N+1) - VerifiedUtility(N)`

Also measure marginal cost and communication burden.

Important: majority agreement must not be treated as ground truth. Hidden tests or independent evidence remain the primary correctness signal.

---

## Phase 3 — Introduce verification scaling

For the same workloads and generation fan-out, compare verification policies:

- none;
- one independent verifier;
- fixed replication/quorum;
- test generation;
- adversarial review;
- heterogeneous verifier pools;
- risk-adaptive verification;
- risk-adaptive verification plus generation backpressure.

Track the verification queue as a first-class system variable.

A useful stability indicator is:

`rho = GenerationArrivalRate * MeanVerificationCost / EffectiveVerificationCapacity`

If `rho >= 1` for sustained periods, unverified work should be expected to accumulate. Real implementations will be more complicated than this queueing approximation, but the approximation provides a falsifiable starting point.

---

## Phase 4 — Vary Work Unit granularity

Now vary how the same larger objective is decomposed.

Candidate decomposition levels:

1. monolithic task;
2. coarse human-written subtasks;
3. file/module tasks;
4. dependency-DAG tasks;
5. formal Work Units carrying contracts, validators, evidence, permissions, assumptions, and provenance.

Search for the granularity that minimizes total cost:

`TotalCost = Execution + Coordination + Context + Verification + Integration + Rework`

The optimal Work Unit is not necessarily the smallest one.

---

## Phase 5 — Joint experiment

The flagship experiment should vary all three dimensions:

- number/diversity of workers;
- Work Unit granularity and graph structure;
- verification policy/capacity.

The key question becomes:

> For a fixed compute and human-attention budget, which combination produces the largest amount of independently verified useful work?

This is closer to the real IDKMesh problem than optimizing any component alone.

---

## Primary project metric

IDKMesh should avoid optimizing raw token generation, number of commits, number of agents, or number of completed tasks.

A candidate headline metric is:

**Verified Useful Work per Unit of Scarce Resource (VUWSR)**

Report it separately against at least:

- compute cost;
- wall-clock time;
- human attention;
- communication;
- energy when measurable.

No single scalar should permanently replace the underlying vector of metrics.

---

## Failure modes to actively search for

The research program should deliberately look for conditions under which IDKMesh fails:

- correlated hallucinations;
- verifier collusion;
- duplicated work;
- context fragmentation;
- dependency mistakes;
- integration explosions;
- generation outrunning verification;
- communication saturation;
- reward hacking;
- premature consensus;
- adversarial workers;
- central coordinator bottlenecks;
- local optimizations that damage global quality.

Negative results are project assets.

---

## What contributors can build immediately

Useful independent contributions include:

- benchmark task proposals;
- a versioned experiment-result schema;
- Work Unit JSON Schema drafts;
- task/evidence DAG tooling;
- orchestration baselines;
- verifier queue simulations;
- error-correlation metrics;
- hidden-test harnesses;
- cost/attention accounting;
- visualization of experiments and DAGs;
- statistical methodology reviews;
- literature reviews linking related distributed-systems, multi-agent, collective-intelligence, and software-engineering research.

Contributors do not need to solve the whole architecture. Small, independently verifiable pieces are preferred.

---

## First milestone

A useful first milestone is not "build a million-node mesh."

It is:

> **Run one reproducible benchmark that compares a strong single-agent baseline with several multi-agent configurations, records full cost and verification metrics, and publishes enough evidence for another contributor to reproduce or falsify the result.**

From there, scale only when measurement demonstrates what should be scaled.

## Related documents

- [`../foundations/FIELD_DEFINING_QUESTIONS.md`](../foundations/FIELD_DEFINING_QUESTIONS.md)
- [`RESEARCH_QUESTIONS.md`](../../RESEARCH_QUESTIONS.md)
- [`MATHEMATICAL_FOUNDATIONS.md`](../../MATHEMATICAL_FOUNDATIONS.md)
- [`ARCHITECTURE.md`](../../ARCHITECTURE.md)
- [`TOP_20_QUESTIONS.md`](TOP_20_QUESTIONS.md)
