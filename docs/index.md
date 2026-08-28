# IDKMesh

> **I don't know. You don't know. Together, the mesh can discover, build, and know.**

IDKMesh is an open-source experiment in **verified swarm engineering**: humans, AI agents, and heterogeneous computers collaborate through bounded tasks, independent verification, and reproducible evidence.

The project is deliberately testing a hard question:

> Can a large open community of humans and AI agents collectively discover goals, decompose work, build, verify, and maintain useful systems better than isolated developers or agents can?

## Choose one path

### New here — 15 minutes

Audit the newcomer experience in [issue #24](../../issues/24). You do not need to understand the architecture. Confusion is useful evidence.

### Want to build or research

Pick a bounded open task from the repository's [`good first issue`](../../issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) or [`help wanted`](../../issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22) queues.

### Expert reviewer

Independent review is first-class work. Inspect one security, runtime, verification, or control-plane claim and try to falsify it. Start with [issue #151](../../issues/151) or the current canonical-node review path.

## What exists already

IDKMesh is not just a proposal. The repository already contains executable experiments and evidence for:

- bounded Work Units and canonical result manifests;
- isolated worker attempts;
- independent deterministic verification;
- non-selecting evidence reports and replay;
- scheduling experiments under churn;
- evolutionary orchestration experiments;
- repository graph/health observability;
- guarded mathematical self-evolution experiments;
- a zero-project-cost Free Resource Mesh;
- an experimental community reproduction controller (ACE).

The repository also preserves negative results and failed experiments. A mechanism that fails under a frozen test is evidence, not something to hide.

## The first product

The first reference product is a **Git-native Verified Swarm Runner**:

```text
bounded Git task
      -> isolated worker attempts
      -> independent verification
      -> Evidence Report
      -> human accept / reject / refine
```

Workers do not get merge authority just because they produced a plausible result.

## What success means

IDKMesh does **not** optimize raw commits, comments, pull requests, stars, or agent output.

A useful project-level target is:

```text
verified useful outcomes
-------------------------------
human attention + compute + risk
```

For community growth, the immediate target is even simpler:

```text
discover -> understand -> bounded action -> verified contribution -> return/help another
```

## Explore the project

- [Main repository](..)
- [Contribution guide](../CONTRIBUTING.md)
- [Community paths](../COMMUNITY.md)
- [What is IDKMesh?](WHAT_IS_IDKMESH.md)
- [Current research questions](../RESEARCH_QUESTIONS.md)
- [Community Growth Engine](../COMMUNITY_GROWTH_ENGINE.md)
- [Fast growth and free compute audit](findings/2026-08-28-fast-growth-and-free-compute-audit.md)

## One principle

**A proposal is not true because it came from a strong model, many models, an expert human, or a popular repository. Evidence must survive independent scrutiny.**
