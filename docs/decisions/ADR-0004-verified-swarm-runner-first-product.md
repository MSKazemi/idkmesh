# ADR-0004 — Build the Verified Swarm Runner as the first reference product

- **Status:** Accepted for the next implementation cycle
- **Date:** 2026-08-28

## Context

IDKMesh has a broad long-term vision: coordinate humans, AI agents, knowledge, tasks, and heterogeneous compute from one laptop to very large networks.

The current roadmap correctly emphasizes experimentation and progressive scaling, but the project needs a smaller user-facing artifact that:

- demonstrates the thesis on one machine;
- is useful before distributed networking exists;
- gives newcomers understandable contribution surfaces;
- can benchmark one strong agent versus coordinated smaller/heterogeneous agents;
- does not require the final architecture to be known.

The ecosystem already contains agent harnesses and emerging interoperability standards, so building a new all-purpose agent implementation is not the highest-value first step.

## Decision

The first IDKMesh reference product will be a **Git-native Verified Swarm Runner**.

The runner will accept a bounded repository task, execute multiple candidate workers through adapters in isolated worktrees/branches, independently verify results, and produce an evidence-backed report for human review.

The first release will **not automatically merge** candidate work into the canonical branch.

## Minimum conceptual workflow

```text
bounded repository task
       |
       v
IDKMesh Work Contract
       |
       v
coordinator / decomposition
       |
       v
multiple isolated worker attempts
       |
       v
candidate patches/artifacts
       |
       v
independent verification
       |
       v
Evidence Report
       |
       v
human/project integration decision
```

## Initial worker targets

The architecture should support replaceable adapters.

Initial target categories:

1. simple local shell/test worker;
2. mini-SWE-agent adapter;
3. OpenHands adapter;
4. human/GitHub workflow adapter;
5. A2A-compatible remote agent later;
6. MCP-backed long-running tool/task where appropriate.

## Why Git-native

Git already provides:

- content history;
- branches;
- worktrees;
- diffs;
- merge/rebase workflows;
- rollback;
- reviewable artifacts;
- compatibility with existing open-source collaboration.

IDKMesh should initially strengthen these workflows rather than replace them.

## Why verification-first

The core thesis is not that more generated code is valuable.

It is that diverse contributors can create more **verified useful work** if the system separates generation from evidence and integration.

Therefore the product should make verification visible in its normal output rather than bolting it on later.

## Community Impact

Positive:

- gives newcomers a concrete thing to run;
- creates independent plugin/adapter/benchmark contribution paths;
- creates a compelling public experiment surface;
- avoids requiring contributors to understand the future distributed network;
- external repositories can eventually use IDKMesh without migrating platforms.

Risk:

- the project may over-focus on software coding and neglect the broader framework vision.

Mitigation:

Treat distributed software engineering as a **reference DomainPack/product**, while keeping Core interfaces domain-independent where justified by evidence.

## Alternatives considered

### Build the distributed network first

Rejected for now. Networking would multiply security, churn, and protocol complexity before the local coordination hypothesis is proven.

### Build a new coding agent first

Rejected as the primary product. The ecosystem has capable open agent harnesses; IDKMesh should test them behind adapters.

### Build a social/community platform first

Community tooling is important, but GitHub is already the effective front door. The project should first create an experiment/product worth gathering around while improving GitHub-native community workflows in parallel.

### Build a compute marketplace first

Rejected. Incentives and settlement should follow demonstrated useful work.

## Consequences

The next implementation priorities become:

1. IDKIP process and interoperability mapping;
2. WorkUnit/ResultManifest contracts;
3. local coordinator and adapter interface;
4. isolated Git worktree execution;
5. independent verification/evidence report;
6. two heterogeneous worker adapters;
7. flagship benchmark;
8. GitHub issue/PR bridge;
9. remote worker transport later.

## Evidence that could reverse this decision

Revisit if experiments show that:

- the Git-centric workflow prevents meaningful target use cases;
- external agent harnesses cannot expose the controls/evidence IDKMesh requires;
- users gain no practical value from local multi-worker verification;
- a different reference domain provides a much clearer falsifiable path to the core thesis.

## Implementation references

- `docs/planning/EXECUTION_TARGET_GRAPH.md`

## Related

- `EVOLUTION.md`
- `IDKIPS.md`
- `idkips/0001-interoperability-first-work-contract.md`
- Issues #2, #3, #4, #5, #6
