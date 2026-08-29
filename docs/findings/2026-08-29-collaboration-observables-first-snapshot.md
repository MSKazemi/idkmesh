# First production collaboration-observables snapshot

**Date:** 2026-08-29
**Source run:** `collaboration-observables.yml` run `33229934255`, head `16f4ba59`, conclusion `success`, cutoff `2026-08-29T02:50:35.294099Z`
**Committed evidence:** [`results/collaboration/observables-2026-08-29T02-50-35Z.json`](../../results/collaboration/observables-2026-08-29T02-50-35Z.json), [`results/collaboration/snapshot-2026-08-29T02-50-35Z.json`](../../results/collaboration/snapshot-2026-08-29T02-50-35Z.json)

This is a snapshot of one run, not a current status. It is a review candidate for interpretation, not a proven claim about the project's trajectory.

## Why this is committed rather than left as a CI artifact

`.github/workflows/collaboration-observables.yml` runs weekly (`cron: "37 5 * * 1"`) and uploads its output with `retention-days: 30`. At the time of writing there was exactly one successful production run in the repository's history, and its output existed nowhere in the tree. Thirty days after 2026-08-29 the only production measurement the observables pipeline has ever produced would have ceased to exist.

Committing the two JSON files makes the measurement durable and citable. `results/` is listed in `.gitignore`, so these were added explicitly, matching the existing convention for `results/experiments/r1` and `results/benchmarks/`.

## What the run measured

Two of the eight observables carry data:

| Observable | Value | Model |
| --- | --- | --- |
| `ci_evidence` | 920 / 1005, posterior mean 0.914598, 95% approx interval [0.897344, 0.931851] | `beta-binomial-v1` |
| `cycle_latency` | median 0.051389 h over 50 samples, bootstrap 95% [0.041111, 0.0675], 0 right-censored | `deterministic-bootstrap-median-v1` |

Six report zero observations. **The reason differs between them, and the distinction is the point of this note.**

### Three zeros are real measurements

| Observable | Reading | What it means |
| --- | --- | --- |
| `first_independent_review_latency` | `samples: 0`, `closed_without_review: 50` | All 50 pull requests in the window closed without an independent review. There is no latency to estimate because the event never occurs. |
| `review_concentration` | `observations: 0`, `distinct_actors: 0`, `hhi: 0.0` | Follows directly from the above: with no independent reviewer/pull-request pairs, review concentration has no population. |
| `contributor_recurrence` | `trials: 0`, posterior falls back to the uniform prior 0.5 | `scripts/collaboration_snapshot.py:203-209` counts a contributor only for a **merged** pull request whose author is neither the repository owner nor a bot. Zero such authors exist in the window, which the raw snapshot records as `contributors: 0`. |

An HHI of `0.0` here must not be read as "perfectly distributed review". It is the value an empty population takes. The observables document already carries this caution; the run is the first concrete instance of it.

`review_queue.open_review_ready: 0` is a fourth real zero, but a point-in-time one — it describes the queue at the cutoff instant and carries no information about the window.

### Two zeros are collector limitations, not repository findings

| Observable | Reading | Cause |
| --- | --- | --- |
| `ownership_concentration` | `observations: 0` | `scripts/collaboration_snapshot.py` writes `"changed_file_owners": []` unconditionally and declares `ownership_attribution_not_collected` in its own `limitations` list. |
| `structural_debt` | `observed_findings: 0`, `inventory_complete: false` | Same: `"structural_debt_finding_ids": []` is hard-coded, with `structural_debt_inventory_not_collected` declared. |

Reading either of these as "no ownership concentration" or "no structural debt" would be a category error. Nothing was measured. The collector says so in machine-readable form, and `inventory_complete: false` is carried all the way into the output.

**Superseded for this snapshot only.** Collector `v0.2` closes both gaps. The follow-up run measured ownership concentration at HHI `1.0` over 66 attributions and loaded four deterministic structural-debt findings, none of which fell inside the observed window — see [Ownership Concentration: First Real Measurement](2026-08-30-ownership-concentration-first-measurement.md). The two zeros recorded above remain the correct reading of *this* snapshot, which was collected by `v0.1`.

## Consequences for the open research questions

- **`evidence_derived_strategy_priors: []`.** The run derived no priors from evidence. The evolution policy therefore still runs on the seven hand-authored uniform `0.142857` priors in `config/evolution-policy-v1.json`. The relevant checklist item in issue 86 remains genuinely open.
- **The falsifiable target "does review HHI predict cycle time or churn" cannot be tested at all right now**, and not for want of tooling — the tooling works and returned an honest empty population. It needs independent reviews to exist.
- **The window is bounded but the zero is probably not a sampling artifact.** The collector observes the 50 most recent pull requests by creation (`maximum_pull_requests: 50`, `window: most_recent_pull_requests_by_creation`). Widening the window would raise the pull-request count, but every additional pull request in this repository's history has the same single author, so `contributors` and `review_concentration` would very likely stay at zero. That is a prediction, not a measurement; it is falsifiable by re-running with a larger `--max-pull-requests`.

## Limitations of this note

- One run. No trend, no variance across runs, no seasonality.
- The 50-pull-request window is not the repository's full history.
- `ci_evidence` counts check runs, not distinct verified outcomes; a flaky check that reruns contributes more than once.
- Nothing here licenses a causal claim. The source artifact carries `"causal_claim": false`, `"github_write": false`, `"policy_activation": false`, and this note does not widen that authority.

## Related

- [Collaboration observables v0.1](../research/COLLABORATION_OBSERVABLES_V0_1.md)
- [Repository-driven community growth](2026-08-28-repository-driven-community-growth.md)
