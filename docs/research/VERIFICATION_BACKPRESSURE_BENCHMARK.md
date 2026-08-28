# Verification Backpressure Temporal Benchmark

**Status:** synthetic reference experiment  
**Date:** 2026-08-28  
**Related:** issue #14, `VERIFICATION_DEBT_AND_BACKPRESSURE.md`, ADR-0007

## Question

When candidate generation becomes faster than independent verification, can verification-debt backpressure keep the verification queue in a bounded operating region without pretending that generated work is already trustworthy?

This experiment advances the existing one-window Risk-Weighted Verification Backpressure (RWVB) controller into a **multi-window queue benchmark**. It is a mechanism test, not evidence that RWVB is optimal on real software work.

## Compared policies

The benchmark implements five conditions:

1. **FIFO** — oldest candidates first;
2. **highest-risk-first** — prioritize synthetic risk × impact;
3. **cheapest-first** — maximize the number of candidates that fit the current verification-cost budget;
4. **RWVB fixed** — use the existing risk/uncertainty/impact/evidence-diversity/age scheduler while keeping generation fan-out fixed;
5. **RWVB adaptive** — use the same scheduler and additionally call the existing verification-debt fan-out controller after every verification window.

The implementation is in:

`experiments/verification_backpressure_benchmark.py`

Dedicated regression tests are in:

`tests/test_verification_backpressure_benchmark.py`

## Synthetic candidate stream

Each generated candidate receives deterministic seeded attributes:

- risk;
- uncertainty;
- impact;
- estimated verification cost;
- evidence diversity;
- hidden synthetic defect truth;
- predetermined synthetic verifier-detection outcome.

The stream is generated from `(seed, candidate_index)`. Therefore fixed policies at the same fan-out receive the exact same candidates in the exact same generation order. Each run records a SHA-256 digest of the generated stream.

Adaptive RWVB intentionally consumes only a deterministic prefix when it throttles generation. Comparing its raw candidate count to a fixed policy is therefore a comparison of **closed-loop system behavior**, not a claim that it solved the same number of generated candidates.

## Queue loop

For every time window:

```text
age pending candidates
 -> generate fanout candidates
 -> allocate bounded verifier-cost capacity
 -> record verifier evidence
 -> remove verified candidates
 -> measure queue + verification debt
 -> adapt next fanout only for rwvb-adaptive
 -> next window
```

No simulated verifier decision grants merge, acceptance, or integration authority.

## Metrics

The experiment preserves raw control/evidence metrics rather than collapsing them into one reward:

- generated candidates;
- independently examined candidates;
- verified throughput per window;
- final and peak pending queue;
- final and peak verification debt;
- mean and maximum wait;
- verifier cost consumed;
- detected seeded defects;
- synthetic verifier false negatives;
- pending seeded defects;
- pending defect exposure (`risk × (1 + impact)` for synthetic defects still waiting);
- minimum/maximum/final generation fan-out.

This makes negative trade-offs visible. A scheduler can clear many cheap candidates while retaining more risk-weighted debt, for example.

## Reference sweep

The checked-in reference result uses:

```text
20 seeds (0..19)
100 verification windows per run
verification-cost capacity = 8 per window
initial fanout = 2, 4, 8, 12
5 policies
```

Compact aggregate results are stored at:

`experiments/results/E014-verification-backpressure-20-seed-summary.json`

The full per-run JSON can be reproduced with:

```bash
python experiments/verification_backpressure_benchmark.py \
  --benchmark \
  --seeds 20 \
  --steps 100 \
  --fanouts 2,4,8,12 \
  --capacity 8 \
  --output /tmp/e014-full.json
```

### Overload examples

Mean values across the 20 seeds:

| Initial fanout | Policy | Verified | Pending at end | Final debt | Pending defect exposure | Mean wait | Final fanout |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 8 | FIFO | 503.25 | 296.75 | 366.36 | 96.47 | 18.58 | 8.0 |
| 8 | highest-risk-first | 539.65 | 260.35 | 143.66 | 21.08 | 1.49 | 8.0 |
| 8 | cheapest-first | 605.80 | 194.20 | 416.63 | 61.38 | 2.28 | 8.0 |
| 8 | RWVB fixed | 508.00 | 292.00 | 361.77 | 92.45 | 15.13 | 8.0 |
| 8 | **RWVB adaptive** | **490.30** | **15.90** | **7.99** | **1.06** | **2.49** | **4.8** |
| 12 | FIFO | 503.75 | 696.25 | 869.84 | 228.61 | 29.03 | 12.0 |
| 12 | highest-risk-first | 537.10 | 662.90 | 475.02 | 90.69 | 1.53 | 12.0 |
| 12 | cheapest-first | 733.70 | 466.30 | 906.75 | 151.68 | 1.18 | 12.0 |
| 12 | RWVB fixed | 506.00 | 694.00 | 866.38 | 226.32 | 25.04 | 12.0 |
| 12 | **RWVB adaptive** | **490.55** | **15.80** | **8.15** | **1.11** | **2.49** | **4.6** |

The important result is not that adaptive RWVB has the largest verified count. It does not. The result is that under the synthetic overload regime it **refuses to keep generating work far above evidence capacity** and contracts toward roughly 4–5 candidates/window, leaving a much smaller risk-weighted queue.

Cheapest-first is a useful counterexample: at fanout 12 it verifies substantially more candidates than the other fixed policies, but still ends with very high verification debt. This is why throughput alone is not a sufficient objective.

Highest-risk-first also performs strongly on pending synthetic defect exposure in these runs. That is evidence that the RWVB scheduler itself should continue to be compared against simpler baselines rather than assumed superior.

## Underload behavior

At initial fanout 2, all fixed policies clear all 200 generated candidates in the reference sweep. Adaptive RWVB detects spare verification capacity and expands generation, reaching about 501 generated / 485 verified candidates on average and a final fanout around 5.1.

This demonstrates the other side of the negative-feedback controller: it can increase generation when verification debt is low instead of permanently suppressing parallelism.

## What this does and does not establish

### Demonstrated by the synthetic mechanism test

- the benchmark is deterministic for a fixed seed/configuration;
- fixed policies receive identical synthetic workloads at equal fan-out;
- all policies respect the verifier-cost capacity per window;
- overload can make fixed generation accumulate large verification queues;
- the existing RWVB fan-out controller can contract generation and stabilize this synthetic queue;
- underload can cause the adaptive controller to use spare capacity;
- no verification outcome is converted into merge authority.

### Not established

- that these risk estimates are calibrated;
- that these controller watermarks are appropriate for real coding work;
- that RWVB is optimal or throughput-optimal;
- that synthetic verifier detection resembles real models, tools, or humans;
- that lower synthetic debt guarantees fewer real regressions;
- that adaptive fan-out improves human reviewer experience;
- that the observed trade-offs generalize across repositories or task families.

## Next evidence step

The next #14 experiment should replace synthetic quantities with measured signals from the emerging local IDKMesh loop:

```text
real WorkUnit attempts
 -> ResultManifest
 -> independent VerificationResult
 -> measured verifier cost/time
 -> measured queue/backlog
 -> candidate risk class
 -> human attention where available
```

Then replay fixed vs adaptive generation policies over the same frozen candidate/verification corpus. The controller should be allowed to fail the experiment. A negative result is useful evidence for changing or removing the policy.

A particularly important follow-up is to compare:

- verification throughput;
- escaped defects / independent-check failures;
- reviewer minutes;
- queue stability;
- risk calibration error;
- verifier correlation;
- oscillation under bursty generation and changing verification capacity.

## Safety invariant

> Generation is supply; independent verification is trust capacity. Backpressure may decide how much work to generate or verify, but it never decides that a candidate is true, accepted, or mergeable merely because the queue is stable.
