# Conversation Record: Top 20 Questions, Scalability, and Agility

Date: 2026-08-28

## User question

> What are the most important 20 questions? How we can have a scalable, very scalable and very agile system for this idea?

## Resulting project direction

The response identified twenty priority research questions covering the unit of value, quality-at-scale, ambiguity and task decomposition, uncertainty, scheduling, correlated error, verification, threat models, consistency, networking, scheduler decentralization, locality, churn, security/privacy, incentives, governance, protocol evolution, observability, and falsifiability.

The most important architectural conclusion was:

> IDKMesh should not be one giant cluster or one giant multi-agent conversation. It should be a federation of autonomous cells, with local scheduling and verification and only compact summaries/overflow work crossing cell boundaries.

This architecture is recorded as **Fractal Autonomous Cells** in `docs/decisions/ADR-0002-fractal-autonomous-cells.md`.

## Key scalability rules

- No all-to-all communication in the hot path.
- No global queue, global lock, or global scheduler for routine work.
- No per-task global consensus.
- Partition state and work by cell/failure domain.
- Keep tasks retryable/idempotent and artifacts immutable/versioned.
- Use hierarchical scheduling and local-first data placement.
- Apply backpressure and admission control at every queue.
- Aggregate observability hierarchically.
- Make implementations pluggable behind versioned contracts.
- Use cells as canary and rollback units.

## Proposed north-star

**Validated Value Throughput (VVT):**

`VVT = verified useful artifacts / (wall-clock time * normalized cost)`

This must be bounded by quality/safety guardrails such as escaped defects, rollback rate, security incidents, reviewer burden, and coordination cost per verified artifact.

## Immediate experiment

Simulate 10, 100, 1,000, 10,000 and 100,000 workers and compare:

1. one global queue/scheduler;
2. sharded scheduling with global directory;
3. autonomous cells with overflow federation.

The primary success condition for the cell architecture is that **coordination cost per task remains approximately bounded as total node count grows**.

## Files produced

- `docs/research/TOP_20_QUESTIONS.md`
- `docs/architecture/SCALABILITY_AND_AGILITY.md`
- `docs/decisions/ADR-0002-fractal-autonomous-cells.md`

## External references consulted

Current primary documentation was checked for architectural lessons from Kubernetes large-cluster/multi-zone design, Ray scheduling/cluster control, libp2p modular peer-to-peer networking, Temporal durable workflows, and NATS messaging. The detailed links and extracted lessons are recorded in `docs/architecture/SCALABILITY_AND_AGILITY.md`.
