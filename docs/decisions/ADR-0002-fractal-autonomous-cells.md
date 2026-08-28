# ADR-0002: Fractal Autonomous Cells for Scalability

- Status: Proposed / default hypothesis
- Date: 2026-08-28
- Decision owners: IDKMesh community

## Context

IDKMesh aspires to scale from one laptop to potentially millions of heterogeneous human/AI/compute participants while remaining agile, fault tolerant, and open.

A conventional single-cluster architecture creates several likely ceilings:

- central scheduler contention;
- global-state growth;
- large failure domains;
- all-to-all or broadcast pressure;
- control-plane availability requirements;
- inability to operate across disconnected or mutually untrusted organizations;
- slow global upgrades.

Existing distributed platforms usually have bounded cluster/control-plane domains. For example, current Kubernetes large-cluster documentation specifies a supported envelope of up to 5,000 nodes in a cluster, while Ray uses cluster-level head/control services. These are useful building blocks but do not imply that one cluster should become the global IDKMesh.

## Decision

Adopt **Fractal Autonomous Cells** as the default architecture hypothesis.

Topology:

`node -> cell -> fabric/region -> global federation`

A cell performs most scheduling, execution, storage, verification, policy, and observability locally. Higher levels exchange summaries, overflow work, artifact discovery information, attestations, and protocol metadata rather than complete local state.

The same protocol concepts should recur at multiple levels, hence "fractal."

## Core constraints

- no all-to-all hot path;
- no global task queue;
- no global lock for routine work;
- no per-task global consensus;
- bounded membership view per node;
- local-first scheduling;
- immutable/versioned artifacts;
- explicit failure domains;
- versioned replaceable components;
- cell-level canary deployment and rollback.

## Why this supports agility

Cells create independent blast-radius and rollout units. New schedulers, validators, runtimes, models, storage systems, and protocol versions can be tested in shadow mode or deployed to selected cells without requiring a global synchronized upgrade.

## Alternatives considered

### One global control plane
Simple initially, but likely creates scaling and availability ceilings and a global failure domain.

### Pure unstructured peer-to-peer mesh
Avoids a central server but can create discovery, trust, routing, governance, debugging, and coordination complexity. Local cells provide useful structure while retaining federation.

### Blockchain/global consensus as the primary coordination layer
Potentially useful for narrow global settlement/attestation functions, but too expensive and restrictive for routine high-rate task coordination. Not selected as the general control plane.

### One Kubernetes/Ray cluster
Useful inside a cell; rejected as the assumed global topology.

## Consequences

Positive:

- horizontal organizational and compute scaling;
- fault containment;
- heterogeneous trust domains;
- local autonomy;
- lower WAN coordination;
- independent upgrades/canaries;
- easier offline/partition-tolerant operation.

Costs:

- federation protocols are harder than one central database;
- duplicate state and caches;
- eventual-consistency semantics;
- more complex cross-cell debugging;
- policy/version skew;
- need for discovery and routing mechanisms.

## Falsification criteria

This ADR should be rejected or substantially changed if experiments show that autonomous cells:

- require cross-cell coordination for a large fraction of ordinary tasks;
- create unacceptable duplicate work or data transfer;
- make global quality/trust significantly worse than centralized scheduling;
- fail to keep coordination cost per task approximately bounded with scale;
- produce protocol complexity whose cost exceeds their scalability benefit.

## Required experiment

Simulate 10, 100, 1,000, 10,000 and 100,000 workers and compare:

1. global queue/scheduler;
2. sharded scheduler with global directory;
3. autonomous cells with overflow federation.

Measure throughput, latency, messages/task, bytes/task, cross-cell operations, failure recovery, and validation quality.

Do not promote this ADR from Proposed to Accepted until those experiments provide supporting evidence.
