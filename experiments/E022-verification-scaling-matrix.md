# E022 — Seven-Mode Verification Scaling Matrix

**Status:** completed synthetic mechanism experiment

**Issue:** #14

## Question

Can candidate generation and independent verification scale together without
turning either unchecked acceptance or an unbounded review queue into the
apparent source of throughput?

Earlier issue #14 work implemented the RWVB controller and compared queue
schedulers. E012–E020 measured verifier correlation, effective evidence,
dependence shape, and quorum choice. This experiment closes the remaining
matrix gap by comparing all seven verification conditions named in #14 on one
matched hidden-defect stream.

## Conditions

1. **No independent verification** — an intentionally unsafe negative control;
   every candidate receives a simulated accept decision, but none is counted as
   verified useful work.
2. **One reviewer** — one fallible reviewer per candidate.
3. **Fixed three-reviewer quorum** — majority vote with a 25% shared-error
   component.
4. **Independent tests** — one test channel whose sensitivity differs for
   correctness, regression, and security defects.
5. **Tests plus adversarial reviewer** — conjunctive test and adversarial-review
   evidence.
6. **Risk-adaptive verification** — evidence cost and diversity rise with
   candidate risk while generation remains fixed.
7. **Risk-adaptive verification plus backpressure** — the same evidence bundles
   plus the existing verification-debt fanout controller.

All non-adaptive conditions at a fixed seed and fanout receive the exact same
candidate IDs, risk, impact, uncertainty, and hidden defect truth. Evidence
channel outcomes are hash-derived from candidate identity, so they do not
depend on policy execution order. The backpressure condition consumes a
deterministic prefix because reducing generation is the intervention under
test.

## Reproduce

```bash
python3 experiments/verification_scaling_matrix.py --self-test

python3 experiments/verification_scaling_matrix.py \
  --benchmark \
  --seeds 20 \
  --steps 100 \
  --fanouts 2,4,8,12 \
  --capacity 8 \
  --summary-only \
  --output experiments/results/E022-verification-scaling-matrix-20-seed-summary.json
```

Reference artifact SHA-256:

`074934de6f15eb60b28a6ad5a1ade3f8760a53b6343235290eaf333f01872ca4`

The compact artifact retains min/mean/max across all 20 seeds for every metric
and all 28 fanout/mode cells. Omitting `--summary-only` emits every raw run.

## Measured fanout-8 comparison

All values are means across 20 seeds and 100 verification windows.

| Mode | Generated | Verified useful / window | Escaped defects | Human-attention units | Final queue | Final fanout |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| no independent verification | 800.00 | 0.0000 | 294.90 | 0.00 | 0.00 | 8.0 |
| one reviewer | 800.00 | 3.1225 | 110.05 | 800.00 | 0.00 | 8.0 |
| fixed three-reviewer quorum | 800.00 | 0.8565 | 22.25 | 600.00 | 600.00 | 8.0 |
| independent tests | 800.00 | **4.9965** | 69.15 | 0.00 | 0.00 | 8.0 |
| tests + adversarial reviewer | 800.00 | 1.2240 | **1.25** | 400.00 | 600.00 | 8.0 |
| risk-adaptive | 800.00 | 2.1885 | 13.75 | 386.35 | 386.45 | 8.0 |
| risk-adaptive + backpressure | 423.30 | 2.1510 | 13.70 | 387.50 | **12.85** | **3.9** |

## Findings

### Backpressure finds a bounded operating region

At initial fanouts 8 and 12, fixed risk-adaptive generation leaves mean final
queues of 386.45 and 786.55 candidates. With the same evidence allocation plus
backpressure, both starting points converge near fanout 4, leave about 13
candidates queued, and deliver about 2.15 verified-useful candidates per window.

This satisfies the synthetic success criterion. Moving the fixed risk-adaptive
condition from fanout 2 to 4 raises verified-useful throughput from 1.0775 to
2.1010 per window while the final queue remains four candidates and escaped
defects and attention grow proportionally rather than without bound. Beyond
that region, generation should be contracted rather than reported as
productivity. It does not prove the controller is stable on real coding work.

### No policy dominates

- Independent tests maximize verified-useful throughput in this model, but
  allow roughly five times as many escaped defects as risk-adaptive verification.
- Tests plus adversarial review have the fewest escaped defects, but their fixed
  cost produces a 600-candidate queue at fanout 8.
- Risk-adaptive backpressure keeps the queue bounded and retains about 98% of
  overloaded fixed-generation throughput, but still permits about 13.7 escaped
  synthetic defects per run.
- A three-reviewer majority is weakened by shared error and becomes
  capacity-limited. Reviewer count is not independent evidence count.
- The no-verification baseline appears to accept the most work only because it
  spends no trust capacity; it produces zero verified-useful output and about
  295 escaped defects at fanout 8.

The correct result is a Pareto trade-off among throughput, escaped defects,
attention, and queue stability—not an RWVB victory claim.

## Issue #14 evidence map

| Requirement | Evidence |
| --- | --- |
| Verification protocol | `schemas/verification-result-v0.1.schema.json` and `docs/specifications/RUN_EVIDENCE_REPORT_V0_1.md` |
| Risk-scoring interface | `Candidate`, `verification_debt()`, and `priority_score()` in `verification_backpressure.py` |
| Verifier scheduler | FIFO, risk-first, cheapest-first, and RWVB in `verification_backpressure_benchmark.py` |
| Generation backpressure | `next_generation_fanout()` plus fixed/adaptive comparisons in E014 and E022 |
| Seeded-defect benchmark | E014 and this matched seven-mode matrix |
| Results schema/dashboard surface | versioned JSON outputs with per-cell metrics and raw-run mode |
| Correlation/diversity evidence | E012, E013, E015, and measured partial-oracle panel E017 |
| Security/regression detection | separate defect-class counters in E022 |
| Human-attention accounting | explicit synthetic attention units; real minutes remain a stated limitation |
| Authority boundary | every run reports `integration_authority = none` |

## Limits and next evidence

- Candidates, defects, reviewers, tests, costs, and attention are synthetic.
- Human-attention units are not measured minutes.
- Shared reviewer errors are controlled, not learned from history; E017 shows
  that real dependence shape is more complicated.
- The test channel is not a real hidden software test suite.
- Backpressure changes generated volume, so it is a closed-loop comparison, not
  a same-candidate-count policy contest.
- No simulated decision can approve, merge, or mutate canonical state.

The Phase-0 verification-scaling architecture and synthetic success criterion
are complete. Real WorkUnit/ResultManifest/VerificationResult timing and human
attention remain later validation work alongside the real-task programs in
#5, #16, #70, and #96; they are not silently inferred from this experiment.

Selection and closure rationale are preserved in
[`2026-08-29-issue-14-verification-scaling-closure.md`](../docs/conversations/2026-08-29-issue-14-verification-scaling-closure.md).
