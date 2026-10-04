# Human–agent coordination: dependencies and effort preflight

**Date:** 2026-10-04

## Project owner's request and context

> can you work on those

This continues the [coordination questions/proposal](2026-10-04-human-agent-coordination-algorithms.md)
and [first ownership/recovery implementation](2026-10-04-coordination-implementation.md).
The request covers duplicate work, bounded competition, stalled workers,
dependency correctness and appropriate model size under resource limits.

## Assistant's implementation

The first implementation is PR 916, local shared claims, four deadlines and
occupancy-safe recovery. Bounded issue 915 records the next outcome: read-only
dependency/effort preflight under the existing Product Spine/C9/C10/connector
owners. The second branch is stacked on the first candidate so shared indexes
remain coherent and each review shows one outcome.

The projection freezes exact WorkUnit/source bindings and only executable
`requires` edges. It rejects cycles, missing targets, duplicates and arbitrary
free-text prerequisite conditions. Integrated prerequisite observations need
exact source/artifact/input/evidence references supplied by trusted adapters.
Candidate completion, issue closure and worker assertions cannot satisfy them.

Event identities and source sequences prevent duplicate/out-of-order delivery
from corrupting readiness. Changing upstream artifacts makes downstream old
input snapshots stale, transitively; unrelated branches remain current. These
are local replay/projection properties, not authenticated live observations.

An explicit effort vector separates scope, ambiguity, coupling, execution,
review and integration duration. Conservative shadow T0–T4 advice preserves
the existing trusted floor and frozen WorkUnit risk. Existing connector routing
retains authority, human, tool, processing, secret, capacity and zero-spend gates.
Unknown requirements queue; deterministic authority is not upgraded to an LLM.
No live issue router, learned bandit or candidate winner selection is changed.

## Mathematical and reproducible checks

Cycle/readiness traversal is iterative, with `O(V+E)` graph processing plus
deterministic normalization/hashing. A 1,500-node test covers recursion limits.
Critical-path ranks add execution seconds to 60 times review/integration
minutes. A three-stage chain of 10 execution seconds plus one review minute
per stage has a 210-second root rank; missing duration produces uncertainty,
not a made-up rank.

The standalone demo uses existing composability fixtures with explicitly
synthetic exact revisions/observations. It reports missing prerequisite -> no
lane, integrated fixture plus simple work -> T1 small lane, and coupled work
-> T3 strong lane. Reports are schema-checked; no model executes or wins a
quality comparison. Actual final test/gate/CI results are in the pull requests.

## Decisions, artifacts and remaining gates

- [Preflight module](../../idkmesh/coordination_preflight.py),
  [tests](../../tests/test_coordination_preflight.py),
  [demo](../../examples/coordination/preflight_demo.py) and
  [specification](../specifications/COORDINATION_PREFLIGHT_V0_1.md).
- Both local slices now make the recommended correctness/allocation mechanisms
  executable and reviewable. They do not yet form a live multi-user platform.
- A real executor must revalidate exact readiness/authority and acquire claims
  and resource reservations atomically before external work, then recheck inputs
  at canonical submission/integration. A report alone leaves a check/use race.
- GitHub durable ledger, authenticated event/identity producers, real provider
  termination/recovery, end-to-end wiring, genuine two-user pilot and held-out
  model-routing quality/energy/attention comparisons remain open evidence gates.

## Community impact and provenance

Inspectable blockers and recommendations help contributors choose useful work
without a reputation score or required compute donation. Synthetic/local evidence
and remaining authority gates are visible to the next reviewer.

Prepared by ChatGPT/Codex using local code/tests and connected GitHub state.
No independent human review, live energy observation, model-quality calibration
or real-user acceptance evidence is represented.
