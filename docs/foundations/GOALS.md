# IDKMesh Goals

This document turns the broad IDKMesh vision into a concrete hierarchy of goals. The project is intentionally uncertain about its final product, but it should not be uncertain about what it is trying to learn and enable.

## North Star

Build an open collective software-engineering system in which large numbers of humans, AI agents, and heterogeneous computers can collaborate on useful projects and produce **verified useful work** that improves as participation grows.

The project should eventually scale conceptually from one laptop to very large distributed communities without requiring every participant to share the exact same model, hardware, skill level, or interpretation of the goal.

## Core mission

IDKMesh exists to discover and implement the coordination rules that can transform many imperfect contributors into a reliable collective engineering system.

A working relationship is:

`collective value = f(competence, diversity, independence, verification, specialization, coordination)`

The project must experimentally determine how each term matters and where scaling breaks down.

## Primary goals

### Goal 1 — Collective coding that can outperform individual coding

Design and test mechanisms under which many smaller or heterogeneous coding agents can collectively match or exceed a stronger single-agent baseline on real software-engineering tasks.

This includes:

- parallel candidate generation;
- task decomposition;
- specialized roles such as planner, implementer, tester, reviewer, security analyst, and integrator;
- diversity-aware aggregation rather than simple majority voting;
- isolated Git branches/worktrees for candidate changes;
- independent verification before integration.

**Key question:** When does adding more workers produce more verified value rather than more noise?

### Goal 2 — Collaboration under uncertain or disputed goals

Allow a project to progress even when the final target is not fully specified and different contributors understand the objective differently.

IDKMesh should represent:

- goals;
- subgoals;
- assumptions;
- competing hypotheses;
- alternative architectures;
- experiments;
- evidence;
- decisions;
- confidence;
- unresolved disagreements.

The system should turn disagreement into structured exploration rather than forcing premature consensus.

### Goal 3 — Distributed Work Units across heterogeneous machines

Create a portable worker protocol in which laptops, workstations, servers, GPUs, humans, and AI agents can accept bounded Work Units and return verifiable artifacts.

Suitable early Work Units include:

- coding tasks;
- tests;
- bug reproduction;
- code review;
- fuzzing;
- security analysis;
- benchmarking;
- documentation;
- simulation;
- research and evidence collection;
- independent replication of previous work.

The initial architecture should favor asynchronous, weakly coupled work rather than attempting to emulate one tightly coupled supercomputer.

### Goal 4 — Verification strong enough for enterprise-quality software

The network must not trust output simply because it came from a capable model, experienced developer, or highly rated participant.

Verification should combine, where appropriate:

- unit and integration tests;
- hidden tests;
- static analysis;
- property-based testing and fuzzing;
- reproducible builds/environments;
- security scanning;
- performance benchmarks;
- API/contract checks;
- independent review;
- redundant execution;
- provenance and supply-chain controls;
- formal methods for critical components when justified.

Enterprise quality should emerge from the validation and integration process, not from assuming every contributor is enterprise-grade.

### Goal 5 — A scalable open-source community

Build a community in which newcomers, researchers, professional engineers, domain experts, AI-agent operators, and compute donors can all contribute meaningfully.

The project should support a progression such as:

`observer -> reproducer -> contributor -> reviewer -> maintainer -> subsystem steward`

Recognition should reward durable value such as bugs found, regressions prevented, experiments reproduced, reviews performed, security issues discovered, and long-lived improvements—not only commit count.

### Goal 6 — A model- and platform-independent coordination layer

IDKMesh should not depend permanently on one coding model, vendor, forge, or hardware architecture.

GitHub is currently the public front door and canonical project record, but the underlying Work Unit, provenance, verification, scheduling, and reputation protocols should eventually be portable across GitHub, GitLab, self-hosted forges, and decentralized transports.

### Goal 7 — Scientific understanding of collective software intelligence

IDKMesh should produce reusable scientific knowledge, not only software.

Important research outputs include:

- scaling curves for number of agents versus verified quality;
- measurements of correlated model errors;
- optimal redundancy levels;
- scheduling and matching algorithms;
- task-decomposition methods;
- reputation and anti-Sybil mechanisms;
- exploration-versus-convergence strategies;
- verification economics;
- contributor/community-health measurements;
- negative results showing mechanisms that do not work.

## Primary system KPI

The current leading system-level metric is:

> **Verified useful work per unit of human attention and compute.**

No single scalar is sufficient for the whole project, so this KPI must be accompanied by a multi-objective scorecard including:

- correctness;
- post-merge defects;
- security;
- maintainability;
- reviewer time;
- wall-clock time;
- compute/energy cost;
- bandwidth;
- reproducibility;
- diversity/independence;
- contributor satisfaction and retention.

## Near-term success criteria

IDKMesh should not claim success at planetary scale before succeeding at small scale.

### Stage A — 1 machine

A coordinator can assign the same bounded repository task to multiple local workers, isolate their changes, evaluate them, and select or reject results reproducibly.

### Stage B — 5–20 machines/agents

A small heterogeneous network completes real Work Units and demonstrates measurable gains—or clearly measured failure modes—relative to a single-agent baseline.

### Stage C — 100 participants

The project can accept work from a larger community while preserving provenance, security boundaries, review quality, and understandable governance.

### Stage D — 1,000+ participants

Scheduling, state management, verification, and community governance remain functional without requiring one central human to understand or approve every contribution.

### Stage E — Very large mesh

The architecture can federate or decentralize major functions while maintaining useful quality, security, incentives, and interoperability.

## Explicit non-goals for the first implementation

The first implementation is **not** trying to:

- train a frontier model across home laptops;
- make thousands of laptops behave like one tightly synchronized GPU cluster;
- introduce a cryptocurrency or token economy;
- fully decentralize every control-plane component;
- solve general artificial intelligence;
- guarantee that 100 small models always outperform one large model;
- build a giant enterprise application before the coordination system itself is tested.

## First falsifiable project claim

The first claim we should attempt to test is:

> For at least some repository-level software tasks, a coordinated set of heterogeneous smaller coding agents using independent generation, testing, criticism, and selection can achieve a higher rate of accepted regression-free changes per unit of human attention than a single-agent baseline.

If experiments reject this claim, that result is valuable and should change the architecture.
