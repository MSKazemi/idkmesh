# Conversation Record — Continue: Power-of-d Scheduling Under Churn

**Date:** 2026-08-28

## Project-owner instruction

The project owner asked IDKMesh work to continue in the canonical public repository.

## Repository state changed during the turn

The repository was re-read before making new changes. This mattered because several concurrent project changes had already landed on `main`:

- independent `VerificationResult` contracts and risk-weighted verification backpressure were already implemented;
- the randomness-lab stochastic simulator foundation had already merged through PR #39;
- emergence-simulation and repository-evolution work had also advanced.

This prevented duplicate implementation of verification backpressure and forced the work queue to be re-ranked from the new repository head.

## Duplicate PR cleanup

An earlier branch/PR created for a randomness-lab foundation (`#41`) became redundant after PR #39 merged a stronger package-based implementation.

Rather than leave duplicate work open and consume reviewer attention, PR #41 was closed with an explicit supersession note.

This follows the project objective:

> maximize verified useful work per scarce review/maintainer attention, not raw PR or activity count.

## Next selected task

Issue #31 was selected:

> Benchmark power-of-two scheduling under churn.

Reasons:

1. PR #39 deliberately exposed `power_of_d_least_loaded()` as a reusable primitive for #31.
2. There was no existing PR implementing #31 when checked.
3. The experiment directly tests whether IDKMesh can reduce global scheduler state while retaining useful load balance.
4. It is independent of the Docker acceptance gate blocking the canonical node PR.
5. It does not consume the reserved ACE newcomer Growth Seed issues.

## Branch

`feat/power-of-two-churn-benchmark`

The branch was created from the then-current `main` commit:

`bd03c6c79b4929a46549fd4e844bc84f0cdcf5d1`

## Implementation

Added `randomness_lab/scheduling.py` with a compact deterministic trace model and policies:

- one random choice;
- power-of-two;
- power-of-three;
- capability-aware power-of-two;
- global least-loaded oracle.

The oracle is intentionally treated as a high-information reference rather than a free baseline. It is charged an O(N) dynamic-state-read proxy per assignment while power-of-d policies pay O(d).

### Replayable trace

`TraceSpec` records:

- seed;
- worker count;
- arrival steps;
- base arrivals;
- burst probability/multiplier;
- churn probability.

Workers, tasks, and availability are derived deterministically from the specification. Availability is hash-derived per `(seed, step, worker)` rather than stored as an O(workers × steps) matrix, allowing large synthetic traces to remain compact and replayable.

A SHA-256 trace-spec digest is included in results.

### Synthetic heterogeneity

Workers vary in:

- service capacity;
- CPU/GPU capability set;
- availability/churn.

Tasks vary in:

- arrival time;
- work size;
- CPU/GPU requirement.

Failed assignment attempts remain pending and can be retried, which permits a recovery metric instead of treating every churn failure as permanently lost work.

### Stale load observations

The simulator supports configurable observation lag.

A correctness issue was identified during implementation: zero-lag power-of-d routing initially used a frozen start-of-step load snapshot. That could create an artificial herd during burst assignment because later assignments did not see load added earlier in the same burst.

The branch was corrected so `observation_lag_steps == 0` uses the live mutable current-load vector. Positive lag deliberately uses older snapshots.

### Metrics

The benchmark records:

- completion rate;
- unfinished tasks;
- failed assignments;
- unreachable assignments;
- capability mismatches;
- retry count/recovery rate;
- assignment attempts per task;
- max and p95 queue depth;
- mean and p95 task system time;
- utilization;
- Jain completion fairness;
- dynamic metadata-read proxy and reads per task.

`metadata_reads` is explicitly documented as a relative coordination-information proxy, not measured network traffic.

## Tests and CI

Added `tests/test_randomness_scheduling.py` covering:

- fixed-spec replayability;
- trace serialization/digest preservation;
- same-trace comparison across all policies;
- zero capability mismatches for capability-aware power-of-two;
- higher dynamic-state cost for the global oracle versus power-of-two;
- presence/range of churn recovery and queue-quality metrics.

The randomness-lab workflow path filter was generalized from only `tests/test_randomness_lab.py` to `tests/test_randomness*.py`, preventing future randomness-lab test files from silently missing CI.

The workflow also gains a scheduling CLI smoke test. It retains read-only repository permission and executes only repository-owned synthetic simulator code.

## Documentation

Added `randomness_lab/SCHEDULING_BENCHMARK.md` describing:

- policies and assumptions;
- trace replay;
- observation staleness;
- metrics;
- suggested `1 -> 10 -> 100 -> 1,000 -> 10,000 -> 100,000` synthetic scale sweep;
- churn/burst/staleness experiments;
- scientific and safety limitations.

## Scientific interpretation

The experiment should not be reduced to “power-of-two wins.”

The useful research question is whether local randomized routing occupies a better Pareto region of:

`queue/wait/failure quality vs coordination information cost`

than either one random choice or a globally informed oracle.

Negative regimes—especially extreme staleness, churn, or capability mismatch—should be retained as evidence.

## Repository rule

This record preserves project-relevant decisions and work under `PROJECT_RULES.md` without exposing private chain-of-thought, secrets, or restricted material.
