# Physarum N3 Readiness Gate

**Status:** blocked pending real compute-path topology evidence  
**Date:** 2026-09-22  
**Related:** PR #631, issue #630, Opportunistic Compute Fabric, Resource -> Compute Admission

## Decision

Do **not** create a production-shaped Physarum shadow adapter yet.

The synthetic Physarum experiments operate on a graph with edges, path
conductance, path burden, link reliability, and multi-path alternatives.

The current IDKMesh compute contracts do not expose that state.

Today the canonical path is:

```text
Resource Mesh evidence
 -> local binding
 -> concrete Compute Offer Pool
 -> subtractive resource_compute_admission.py
 -> smaller admitted Compute Offer Pool
 -> free_compute_router.py
 -> one selected compute offer
```

The admitted object is a **flat offer set**, not a routed network graph.

## What exists today

`compute-offer-pool-v0.1` gives each already-concrete offer:

- provider;
- cost class;
- zero/non-zero project cost;
- availability;
- trust;
- capabilities/resources;
- expected wait;
- observed success probability;
- independence group.

`resource_compute_admission.py` is deliberately subtractive.

It may remove offers that lack fresh evidence/authorization.

It does not create:

- network links;
- relay capabilities;
- route paths;
- edge latency;
- edge loss;
- edge bandwidth;
- route-specific donor burden;
- path failure attribution.

That is the correct current boundary.

## Why a graph should not be invented now

A research-only graph schema could be written immediately, but without a real
source for its edges it would create a dangerous illusion:

```text
synthetic edge exists in JSON
 !=
real admitted node can relay a WorkUnit over that edge
```

Volunteer nodes currently belong to a pull-based bounded WorkUnit architecture.
That does not automatically grant arbitrary relay or transit semantics.

A Physarum N3 adapter must therefore wait until IDKMesh has a real controlled
multi-node execution/federation path whose topology can be observed rather than
imagined.

## Non-overlap with current compute router

The current free compute router answers:

> Which one already-admitted zero-project-cost offer satisfies this WorkUnit?

Physarum PHY-0/PHY-1 answer a different research question:

> When work can traverse multiple real admissible paths in a changing
> federation, which paths should retain conductance so the system can recover
> from link/node changes?

If the real product remains single-hop offer selection, use simpler existing
routing/bandit mechanisms.

Do **not** repurpose Physarum merely to produce another score over flat offers.

## Required N3 prerequisites

### 1. Controlled real node cohort

Bring up 3-10 controlled nodes/containers using existing IDKMesh node/admission
boundaries.

Every execution-capable node must already survive:

- resource evidence;
- local authorization;
- concrete compute admission;
- WorkUnit capability/resource/trust checks;
- zero-project-spend policy.

### 2. Explicit path semantics

Before a graph exists, document what an edge means.

Acceptable examples might include a real:

- federation relay;
- artifact-transfer channel;
- scheduler-to-node control path;
- checkpoint migration path.

An edge MUST NOT mean merely:

- two offers happened to exist;
- two providers are both online;
- two nodes share a region label.

### 3. Observed edge telemetry

For each actual path/edge, retain measurements such as:

- source/destination node IDs;
- observation window;
- successful/failed transfers;
- latency or route burden;
- bandwidth where relevant;
- donor/resource burden where relevant;
- failure attribution confidence;
- whether the edge is currently available.

Telemetry must distinguish:

```text
transport/path failure
worker execution failure
verification rejection
provider outage
artifact corruption
timeout
```

Physarum must not penalize a route for failures that cannot reasonably be
attributed to that route.

### 4. Flat-router baseline remains canonical

During N3 shadow collection:

- actual execution stays on the existing admitted deterministic/current router;
- Physarum only recommends;
- shadow plan is frozen before outcome;
- no provider eligibility changes;
- no automatic reroute.

### 5. Common shadow evidence contract

Once real topology exists, use PR #637 / issue #636:

```text
captured topology snapshot
 -> hard admission gates
 -> named baseline route
 -> Physarum shadow route
 -> freeze plan before execution outcome
 -> actual baseline process
 -> timestamped outcome join
 -> descriptive cohort summary
```

## Proposed graph contract — deferred

Do **not** merge an `admitted-compute-graph` schema until there is at least one
real controlled topology source.

When that prerequisite exists, the graph contract should minimally bind:

- repository and exact source revision;
- WorkUnit;
- exact admitted Compute Offer Pool digest;
- admission report/evidence digest;
- capture timestamp;
- nodes referencing admitted offer IDs;
- edges referencing actual measured path semantics;
- edge telemetry source/evidence refs;
- no independent ability to add offers or relax admission.

The graph layer must be **subtractive/observational**, just like admission.

## N3 falsification questions

Before any live routing:

1. Does Physarum make materially different recommendations from the current
   baseline?
2. In stable periods, is its exploration premium acceptably small?
3. Around real outages, does it identify alternatives before the baseline would?
4. Does noisy attribution cause it to learn the wrong conductance?
5. Does discounted Thompson or explicit failover match the same behavior with
   less state?
6. Are multi-hop paths actually useful in IDKMesh, or is the product still
   fundamentally single-hop?

A negative answer to #6 is sufficient reason to keep Physarum as research only.

## Current conclusion

PHY-0 and PHY-1 justify continued **synthetic resilience research**.

They do not yet justify an N3 product adapter.

The next engineering work is real multi-node topology/telemetry, not more
Physarum policy code.
