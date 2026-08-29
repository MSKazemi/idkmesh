# Issue #84 Factor-Isolation Closure

**Date:** 2026-08-29

## Project-owner requirement

Select another open issue with no overlapping active work, solve it through a
focused pull request, and merge only after current exact-head evidence passes.

## Selection and scope

Issue #84 was unassigned after its Phase A PR merged. A fresh audit found no
open PR, local branch, remote branch, or worktree targeting its remaining Phase
B/C scope. A capability-rarity claim had in fact been posted nine seconds before
this work's claim and then merged as PR #262. The branch was rebased onto #262
and its duplicate capability implementation was discarded. This contribution
covers only the independent lag, failure-shape, saturation, and coordination-
cost work that #262 explicitly left open.

The remaining acceptance surface was bounded to factor isolation and stronger
coordination-cost evidence. The work deliberately does not expand into real
fleet validation or claim that one scheduling policy is universally optimal.

## Implementation

`randomness_lab.r2_factor_sweep` adds five-seed sweeps for:

- availability lag with load lag fixed at zero;
- load lag over the same trace with availability lag fixed at zero;
- dispersed independent outages versus one simultaneous regional outage;
- offered load from 0.25 through 1.25 capacity-work per tick.

Each raw policy run retains performance, failures, churn recovery, locality,
metadata probes, modeled messages/bytes, capability-directory operations, and
scheduler state. An opt-in profile separately measures process CPU time and
Python traced peak allocation on a recorded host.

## Findings and decision

PR #262 establishes the capability-rarity result. This continuation finds that
availability lag creates unreachable routing attempts, while load lag instead
increases queue response time. The regional-outage effect is measurable but
modest in this model. Near saturation, local two-choice latency diverges from
the full-information oracle.

These results complete issue #84's synthetic Phase B/C acceptance criteria and
preserve negative regimes. Real packet measurements, distributed directory
behavior, and hardware/fleet validation remain explicitly out of scope.

## Community impact

Contributors can now inspect one raw, reproducible causal matrix instead of
inferring causes from combined `fresh`/`moderate`/`stale` presets. Transparent
cost assumptions make it easier to challenge or replace the model.

## AI/tool provenance

Codex implemented the harness, tests, reference artifacts, and synthesis. Local
verification passed the self-test, 22 focused R2 tests, 439 repository tests,
and 25 interop tests (two optional-dependency skips). The deterministic matrix
has SHA-256
`988b002bdbbd28a92c34825381ccbe45f09384780494a3300f91457987f680fa`;
the host profile has SHA-256
`0265c4cc971b7e4f8cbf0f8113a2850676378540715a4cbacc44f36b81cdc0ee`.
GitHub exact-head verification remains required before integration.
