# PHY-1 — Physarum routing stress matrix

**Status:** executable synthetic falsification matrix  
**Date:** 2026-09-22  
**Tracker:** #630  
**Implementation:** `sim/physarum_compute_routing_stress.py`

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
