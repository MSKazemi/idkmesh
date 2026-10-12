# PHY-1 — Physarum routing stress matrix

**Status:** executable synthetic falsification matrix  
**Date:** 2026-09-22  
**Tracker:** #630  
**Implementation:** `sim/physarum_compute_routing_stress.py`  
**Retained completion sweep:** `experiments/results/PHY-1-completion-sweep.json`  
**Retained failover frontier:** `experiments/results/PHY-1-failover-frontier.json`

## Purpose

PHY-0 intentionally used an abrupt route-quality shift and produced a favorable
result for conductance-based routing. That is not enough evidence.

PHY-1 asks a harder question:

> Does the mechanism remain useful when the environment is stationary, failures
> are temporary or correlated, route burden is asymmetric, or failure
> attribution is noisy?

## Strategies

- `shortest-static`
- `discounted-thompson`
- `multipath-failover`
- `physarum`

The new baselines matter:

- discounted Thompson sampling forgets stale observations and can adapt without
  maintaining conductance;
- multipath failover explicitly pays retry burden to obtain resilience.

A biological mechanism is not retained merely because it beats a static path.

## Environments

### Stationary

Nothing changes.

This is a falsification case for unnecessary exploration. Physarum should not
receive credit for resilience if it wastes materially more donor/network burden
when the shortest reliable route remains good.

### Abrupt shift

The original PHY-0 change point.

### Gradual shift

Reliability changes continuously rather than at one obvious boundary.

### Transient A outage

The initially attractive corridor becomes almost unavailable for a bounded
window and then recovers.

This tests whether adaptation can also **unlearn the outage**.

### Permanent A node loss

The `a` corridor is effectively removed after the event.

### Correlated A/B regional shocks

A and B are jointly degraded during random regional events.

This tests common-mode failures rather than independent edge noise.

### Donor-burden asymmetry

The C corridor remains technically usable but costs twice as much in synthetic
donor/network burden.

A resilience policy should not treat every alternate path as equally cheap.

### Noisy failure attribution

Thirty percent of failed-edge penalties are assigned to another edge on the
same used path.

This directly tests a deployment hazard: adaptive routing can learn the wrong
lesson when failure provenance is poor.

## Metrics

Report at minimum:

- overall task success;
- pre-event and post-event success;
- route attempts per task;
- retry rate;
- mean route burden per task;
- mean burden of successful tasks;
- normalized path entropy;
- maximum primary-path share.

Do not report success without its resource burden.

## Command

```bash
python sim/physarum_compute_routing_stress.py \
  --seeds 20 \
  --epochs 80 \
  --tasks-per-epoch 20
```

Target individual scenarios with repeated `--environment` flags.

## Decision rule

Physarum earns a dry-run planner experiment only if all of the following hold:

1. it provides a reproducible resilience advantage in at least two distinct
   non-stationary failure regimes;
2. that advantage remains meaningful against discounted Thompson and explicit
   failover;
3. its stationary-network burden premium is bounded and disclosed;
4. it remains stable under correlated failure and noisy attribution;
5. donor-burden asymmetry does not cause pathological overuse of expensive
   alternate routes.

If a simpler adaptive baseline provides the same frontier, prefer the simpler
baseline.

## Authority boundary

PHY-1 remains downstream of:

```text
resource evidence
 -> local authorization
 -> concrete compute offer
 -> repository $0 policy
 -> WorkUnit feasibility/trust gate
 -> admitted graph
```

The experiment cannot grant eligibility, permissions, money, trust, or merge
authority.


## Completion sweep — 2026-10-08

Issue #630's remaining synthetic gates were completed with two explicit graph
views:

- `sparse`: the three independent coordinator-to-worker corridors only;
- `dense`: the same admitted nodes plus all three cross-corridor edges already
  present in PHY-0/PHY-1.

No synthetic edge is treated as production topology. These are deterministic
falsification fixtures only.

The retained bounded sweep uses seeds 1–6, 50 epochs, and 10 tasks per epoch.
It is intentionally smaller than the exploratory default so review and CI can
reproduce it cheaply. The machine-readable summary is
`experiments/results/PHY-1-completion-sweep.json`.

Reproduce the topology matrix with:

```bash
python sim/physarum_compute_routing_stress.py \
  --topology all --seeds 6 --epochs 50 --tasks-per-epoch 10
```

The explicit sensitivity sweep varies the conductance floor (`d_min`),
evaporation, and exploration independently around the frozen baseline:

```bash
python sim/physarum_compute_routing_stress.py \
  --parameter-sweep --topology dense --environment abrupt-shift \
  --seeds 6 --epochs 50 --tasks-per-epoch 10
```

### Outcome

**Recommendation: reject promotion to a dry-run product planner at this stage.**

The result is negative, not a fabricated success. Across both topology views,
explicit multipath failover has higher synthetic success than Physarum in all
16 topology/environment cells of the retained sweep. It pays more route burden
in 12 of them; in the remaining 4 (`stationary` on both views, and `dense`
`correlated-ab-region-shocks`) failover is better on both success and burden.
Discounted Thompson is better than Physarum on both success and burden in three
dense scenarios (`abrupt-shift`, `gradual-shift`, `donor-burden-asymmetry`).
The parameter sweep (dense, `abrupt-shift` only) moves Physarum's success
between 0.805 (`evaporation-low`) and 0.926 (`exploration-high`) around a
frozen baseline of 0.850, so its trade-off is materially parameter-sensitive.
The best tested settings still trail failover's 0.998: `evaporation-high`
reaches 0.924 at burden 2.287, and `exploration-high` reaches 0.926 at burden
2.455, against failover's burden of 2.451. The negative result therefore does
not come from an unluckily tuned baseline alone.

What the data does **not** show: on the `sparse` view, Physarum is not
Pareto-dominated by any single tested baseline in any of the seven
non-stationary environments. It sits between discounted Thompson (lower
success, lower burden) and failover (higher success, higher burden). The
rejection is therefore a decision-rule judgement and not a dominance result.
Rule 2 requires a resilience advantage against explicit failover, and Physarum
has none in success. A failover variant matched on burden was not tested here; it is tested in the
frontier section below. The
sensitivity sweep covers one environment and one topology, and it reuses the
evaluation seeds.

Every retained number is recomputed from the committed code and seeds by
`tests/test_physarum_compute_routing_stress.py`. The full replay is the
`sim`-marked (nightly) test, and one cheap cell replays in the unit tier. Both
compare values within `1e-6`, never bytes.

This does not prove failover is universally superior, and it is not real
network evidence. It does satisfy the issue's decision purpose: the current
synthetic evidence is insufficient to justify adding a Physarum production
integration surface. Keep the simulator as research evidence; prefer simpler
routing until a materially different experiment falsifies this conclusion.


## Burden-matched failover frontier — 2026-10-12

The completion sweep left one question open: its rejection compared Physarum
with explicit failover that retries on **every** failure, so failover usually
spent more burden and the comparison was not burden-matched. This section
closes that gap on the same synthetic fixture. Tracker: #630.

### Method

`multipath-failover` gained a `retry_probability` knob (default `1.0`). A
failed primary is retried only with that probability, so sweeping it over
`0, 0.25, 0.5, 0.75, 1` traces a failover burden/success frontier. At `1.0` no
extra random number is drawn, so the arm is the published failover arm
unchanged: its retained numbers equal the completion sweep's failover cells
(checked by a test), which keeps the new arm comparable with the baseline.

Physarum and discounted Thompson are scored per seed as
`success - frontier_success_at_that_seed's_own_burden`, where the frontier is
the Pareto envelope of the five failover points (more burden for no more
success is dropped), interpolated linearly. Failover, Physarum and Thompson
share seeds 1-6, 50 epochs, 10 tasks per epoch, on both the `sparse` and
`dense` views. Verdicts:

- `above-frontier` / `below-frontier`: mean gap beyond 2 standard errors of the
  per-seed gaps (an uncalibrated screen with n=6, not a significance test);
- `on-frontier`: within 2 standard errors;
- `dominated-by-frontier-endpoint`: Physarum burden is above failover's `p=1`
  burden and its success is below it, in the means;
- `uncompared`: burden below the cheapest failover point, so there is nothing
  to interpolate against.

Reproduce, and replay the retained artifact:

```bash
python sim/physarum_compute_routing_stress.py \
  --failover-frontier --topology all --seeds 6 --epochs 50 --tasks-per-epoch 10
```

The retained result is `experiments/results/PHY-1-failover-frontier.json`; it
is replayed from committed code by `tests/test_physarum_failover_frontier.py`
(one cell in the unit tier, all 16 topology/environment cells in the `sim`-marked nightly test,
compared by value within `1e-6`).

### Result (synthetic)

Verdicts over the 16 topology/environment cells:

| Strategy | above frontier | on frontier | below frontier | dominated by endpoint | uncompared |
|---|---|---|---|---|---|
| physarum | 3 | 7 | 3 | 3 | 0 |
| discounted-thompson | 10 | 2 | 2 | 0 | 2 |

- Physarum is above the burden-matched failover frontier only in
  `permanent-a-node-loss` on both views (gap +0.095 +/- 0.007 dense,
  +0.111 +/- 0.023 sparse) and in `abrupt-shift` on the sparse view
  (+0.032 +/- 0.015).
- In each of those three cells discounted Thompson has a comparable gap at
  lower burden (+0.096 +/- 0.010 dense node loss; +0.086 +/- 0.005 sparse node
  loss, below Physarum's +0.111 by about one Physarum standard error;
  +0.034 +/- 0.007 sparse abrupt). The
  Physarum advantage over burden-matched failover is therefore not specific to
  Physarum; a simpler adaptive baseline gets it too. Under decision rule 2 and
  the "prefer the simpler baseline" clause this reaffirms the rejection.
- Thompson is above the frontier in all non-correlated, non-transient,
  non-stationary cells on both views; Physarum is not.
- In `stationary` (both views) Physarum is dominated by the `p=1` failover
  endpoint (success 0.967 / 0.959 against 0.998, at higher burden), and in
  dense `correlated-ab-region-shocks` it is dominated too (success 0.914 at
  burden 2.66 against 0.993 at 2.55).
- Dense `donor-burden-asymmetry` is Physarum's worst cell: -0.060 +/- 0.007
  below the frontier.

### What this does and does not show

Tested: one burden-matched failover frontier (five retry probabilities), two
graph views, eight environments, six seeds, paired by seed.

Not tested, and still open for #630:

- the failover arm orders paths by **undiscounted** posteriors, so it adapts
  slowly after a persistent change. The `above-frontier` cells are exactly the
  persistent-change cells, so part of the Physarum and Thompson advantage there
  may be a weak-frontier artifact. A failover arm with discounted posteriors
  is the natural next arm and is not built;
- a change-point-aware or contextual-bandit baseline;
- sensitivity-sweep settings chosen on seeds disjoint from the evaluation seeds;
- any real topology, network trace, or donor burden. Nothing here is empirical
  evidence, and the held-out splits tracked by #973 were not opened.

The recommendation stays **reject promotion to a dry-run planner**.
