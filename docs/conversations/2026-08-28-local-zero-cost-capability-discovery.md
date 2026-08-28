# Conversation Record — Local Zero-Cost Capability Discovery

**Date:** 2026-08-28

## Context

The project owner required IDKMesh to continue using available compute while keeping project-funded compute spend at exactly `$0`.

The zero-cost router and repository policy had already been added. The next engineering question was whether the router could consume a **real offer discovered from the current machine**, rather than only hand-written fixtures.

## Repository inspection

Before implementing another node abstraction, the open canonical node integration PR (#34) was inspected.

That PR already uses the canonical Work Unit v0.2 schema and explicitly enforces:

- `budget.project_spend_usd_max = 0`;
- `budget.paid_fallback_allowed = false`;
- local-only bounded execution;
- no task network;
- no secrets;
- independent verification.

Therefore local capability discovery was implemented as a small provider-neutral utility on `main`, not as a second node/runtime protocol.

## Implementation

Added:

`experiments/local_compute_offer.py`

The utility performs **discovery only**. It does not:

- execute a Work Unit;
- open a network connection;
- register with a broker;
- expose remote-control functionality;
- require cloud/model/billing credentials.

It discovers, using Python standard-library facilities where practical:

- logical CPU count;
- physical memory where the platform exposes it through `os.sysconf`;
- free repository-filesystem disk space;
- OS and architecture capability tags;
- Python capability;
- JSON Schema capability when the `jsonschema` package is installed.

## Conservative resource caps

Raw host capacity is **not** automatically advertised as permission to consume the whole machine.

Default advertised limits are deliberately conservative:

```text
CPU:    1 core
Memory: 1024 MB
Disk:   4096 MB
GPU:    disabled
```

A contributor can explicitly lower or raise those caps, but the emitted value is always:

```text
min(detected capacity, configured cap)
```

Unknown detected memory/disk is represented as zero rather than being inflated to the configured cap.

This separates:

```text
what hardware exists
```

from:

```text
what capacity the participant is willing to expose
```

## GPU policy

GPU capacity is not automatically enabled by hardware probing in this first utility.

A user must explicitly provide `--gpu`, with optional accelerator labels such as `--accelerator cuda`, before GPU capacity is advertised.

This avoids treating hardware detection as consent to use a scarce/high-power resource.

## Privacy

The utility does not collect or publish a hostname by default.

It uses a logical `independence_group` label, defaulting to `local-machine`, which can later be replaced by a privacy-preserving node identifier or attestation design.

## Zero-spend invariant

Every generated local offer reports:

```text
project_cost_usd = 0
```

and uses:

- `local_owned` by default;
- `donated` only when the operator explicitly passes `--donated`.

The distinction matters because donated capacity has real donor-side resource costs even though the IDKMesh project receives no invoice.

## Deterministic self-test

The utility includes a self-test that verifies:

- generated offers validate against `compute-offer-pool-v0.1`;
- CPU caps are enforced;
- memory caps are enforced;
- disk caps are enforced;
- detected small machines are never inflated to configured caps;
- project monetary cost remains zero;
- donated mode requires an explicit choice.

## End-to-end CI integration

The Phase 0 workflow was extended to run:

```text
python experiments/local_compute_offer.py self-test
python experiments/local_compute_offer.py discover --output results/local-offer.json
python experiments/free_compute_router.py select --offers results/local-offer.json
```

This makes CI exercise the real path:

```text
current machine
 -> conservative capability discovery
 -> schema-valid zero-cost offer
 -> repository `$0` policy
 -> Work Unit/resource matching
 -> selection report
```

It remains selection/discovery only; CI does not execute provider-supplied task commands.

## Relation to issue #52

This implements the core scope of issue #52, `Connect the zero-cost router to real local capability discovery`.

Once the new CI run succeeds, the issue can be closed. The same offer-generation logic can then be reused by the canonical local node work rather than defining a new Work Unit protocol.

## Community impact

A contributor can now inspect exactly what IDKMesh would advertise from a machine before any distributed or sandbox execution is connected.

This makes zero-cost compute contribution more transparent and lowers the trust barrier for future volunteer-node participation.
