# IDKMesh Evolution Strategy

**Status:** Working direction — designed to evolve through IDKIPs, experiments, and community evidence.

IDKMesh is deliberately ambitious, but the next step is not to build every layer of a planetary distributed system. The next step is to make the thesis **useful, testable, installable, and easy for a community to extend**.

## The project in one sentence

> **IDKMesh is a verification-first coordination fabric for humans, AI agents, and heterogeneous compute working on uncertain goals.**

The project should connect existing agents and tools rather than trying to replace all of them.

## The first product

The first reference product should be a **Git-native Verified Swarm Runner**.

A user points IDKMesh at a bounded repository task. Several worker adapters attempt the work independently or in specialized roles. Each candidate runs in isolation. A separate verification pipeline tests and scores the outputs. IDKMesh produces an evidence-backed report and candidate patch/branch, but does not autonomously merge into the canonical branch.

Conceptually:

```text
Git issue / bounded task
        |
        v
   Work Contract
        |
        v
  task decomposition
        |
   +----+--------------------+
   |            |            |
   v            v            v
mini-SWE     OpenHands     human/other
 agent        adapter       adapter
   |            |            |
   +------------+------------+
                |
                v
       isolated candidates
                |
                v
      independent verifier
 tests | hidden tests | lint | security
                |
                v
      Evidence / Result Report
                |
                v
 human accepts / rejects / refines
```

A possible future CLI experience:

```text
idkmesh init
idkmesh run --task github:#42 --workers 5
idkmesh verify <run-id>
idkmesh report <run-id>
```

These command names are illustrative. The important part is the workflow.

## Why this is the right first wedge

It directly tests the central research question while producing something useful to ordinary open-source repositories.

It also gives contributors small, independent surfaces to improve:

- worker adapters;
- task decomposition;
- verification plugins;
- benchmarks;
- scheduling strategies;
- sandbox backends;
- provenance;
- GitHub integration;
- UX;
- experiment analysis.

A community can contribute to these parts without understanding the eventual million-node architecture.

---

# 1. What IDKMesh should build vs reuse

## Build: the distinctive IDKMesh layer

IDKMesh should own the pieces that directly express its research thesis:

1. **Goal/Evidence Graph** — goals, ambiguity, assumptions, competing hypotheses, work, artifacts, verification, decisions, and provenance.
2. **Work Contract** — bounded work plus constraints, dependencies, risk class, expected evidence, verification policy, resource/capability hints, and provenance requirements.
3. **Verification fabric** — independent tests, reviewers, redundant execution, adversarial checks, evidence aggregation, and escalation.
4. **Coordination policy** — decomposition, matching, scheduling, diversity, replication, exploration vs convergence, and integration policy.
5. **Evidence-backed reputation** — eventually reward durable verified contribution rather than raw output volume.
6. **Experiment and metrics layer** — reproducibly compare orchestration strategies.
7. **Community/governance bridge** — turn GitHub issues, IDKIPs, reviews, reproductions, and human decisions into first-class project evidence.

## Reuse or integrate: ecosystem infrastructure

Do not build replacements unless evidence shows a real gap:

- **A2A** for interoperable agent-to-agent communication and agent discovery;
- **MCP** for tool/context access and durable asynchronous tool tasks;
- **Git/GitHub** for the current human collaboration and code-history substrate;
- existing coding-agent harnesses such as **mini-SWE-agent** and **OpenHands** through adapters;
- **OCI containers** initially for reproducible execution, with stronger isolation backends where risk requires them;
- **gVisor / Firecracker / WASI** as candidate stronger sandbox tiers rather than inventing a hypervisor;
- **Sigstore/Rekor, in-toto, and SLSA-style attestations** for provenance patterns;
- existing P2P stacks such as **libp2p** when networking becomes necessary.

The rule is:

> **IDKMesh should innovate in coordination, verification, evidence, and collective intelligence — not in commodity transport or isolation unless the experiment requires it.**

---

# 2. Interoperability architecture

The 2026 agent ecosystem now has two important protocol directions:

- **A2A** provides agent discovery, skills, stateful tasks, messages, and artifacts across heterogeneous agent implementations.
- **MCP** provides a broad tool/context protocol and now includes a durable Tasks extension for long-running tool work.

IDKMesh should therefore avoid defining another generic remote-agent transport.

Instead:

```text
                 IDKMesh Work Contract
       (risk + resources + deps + verification + evidence)
                         |
          +--------------+---------------+
          |                              |
          v                              v
     A2A mapping                    MCP mapping
 Task + AgentCard + Artifact       Tool + Task handle
          |                              |
          +--------------+---------------+
                         |
                         v
                 concrete worker
```

The IDKMesh Work Contract is **not identical** to an A2A or MCP Task. It carries project-specific scheduling and verification obligations that those general protocols do not attempt to define.

This mapping should be tested before the WorkUnit schema is frozen.

See IDKIP-0001.

---

# 3. Architecture layers

The project should evolve as separable layers so contributors can work independently.

## Layer A — Community and project surface

GitHub issues, pull requests, IDKIPs, Discussions, docs, starter tasks, releases, and public experiments.

This remains the front door until evidence supports federation.

## Layer B — Goal and Evidence Graph

Represents:

- goals and subgoals;
- uncertainty and assumptions;
- questions and hypotheses;
- competing proposals;
- dependencies;
- evidence;
- artifacts;
- verification events;
- decisions;
- risks;
- provenance.

This is how IDKMesh can coordinate a community that does not begin with one perfectly shared mental model.

## Layer C — Work Contract

A bounded task specification that can be assigned to a human, coding agent, test worker, research worker, or remote compute node.

The contract should answer:

- What is being attempted?
- What may the worker access/change?
- What capabilities/resources are needed?
- What artifacts are expected?
- How will the result be verified?
- What provenance/evidence must be returned?
- What risk class applies?
- What dependencies block or constrain it?

## Layer D — Worker adapters

Adapters connect IDKMesh to existing execution systems.

Initial targets:

1. simple local shell/test worker;
2. mini-SWE-agent;
3. OpenHands;
4. human/GitHub workflow;
5. generic A2A-compatible worker;
6. generic MCP task/tool worker where appropriate.

Workers should be replaceable.

## Layer E — Execution and isolation

Risk-tiered execution:

```text
trusted local task
   -> process/container
untrusted generated code
   -> hardened container / gVisor
higher-risk multi-tenant task
   -> microVM or equivalent strong isolation
portable capability-limited task
   -> WASI candidate where compatible
```

The first implementation should keep the backend interface simple and use the easiest safe local option. Stronger isolation becomes mandatory before accepting arbitrary remote work on volunteer machines.

## Layer F — Verification and integration

Verification is the heart of IDKMesh.

Candidate methods include:

- existing tests;
- hidden tests;
- independently generated tests;
- static analysis;
- lint/type checks;
- security scanning;
- fuzz/property tests;
- performance/resource checks;
- unauthorized-change detection;
- redundant execution;
- independent agent/human review;
- provenance/reproducibility checks.

A candidate result is an **untrusted proposal** until the applicable verification policy passes.

## Layer G — Provenance and evidence

The first provenance path should be:

```text
content hashes
 -> signed manifests
 -> attestations
 -> append-only transparency/audit log
 -> independent monitors
```

Do not introduce blockchain unless a later multi-operator trust/settlement experiment demonstrates that simpler mechanisms are insufficient.

## Layer H — Remote mesh and federation

Only after the local scientific kernel demonstrates value:

- remote workers;
- capability advertisement;
- task offers/claims;
- artifact transfer;
- churn/retry;
- locality-aware scheduling;
- cell/federation architecture;
- distributed state only where needed.

---

# 4. The next milestones

## Milestone 0 — Make project evolution explicit

**Goal:** contributors know what is stable, experimental, or disputed.

Deliverables:

- IDKIP process;
- IDKIP-0001 interoperability proposal;
- this evolution document;
- architecture decisions linked to experiments;
- community-facing backlog.

## Milestone 1 — Freeze the smallest useful contracts

**Goal:** define interfaces only after checking current ecosystem standards.

Deliverables:

- WorkUnit/Work Contract v0;
- ResultManifest/EvidenceReport v0;
- ProjectManifest/DomainPack v0;
- mapping to A2A Task/Artifact;
- mapping to MCP Tasks where appropriate;
- example payloads;
- JSON Schema validation tests.

Exit condition: at least two different worker implementations can execute the same logical Work Contract through different adapters.

## Milestone 2 — Build the local Verified Swarm Runner

**Goal:** one laptop, multiple isolated workers, one independent verifier.

Deliverables:

- CLI;
- coordinator;
- worker adapter interface;
- isolated Git worktrees/branches;
- execution backend interface;
- deterministic experiment/run manifest;
- result/evidence report;
- cleanup/replay.

Exit condition: a bounded Git repository task is dispatched to 3–5 workers and the run can be reproduced from saved manifests.

## Milestone 3 — Ship two real agent adapters

Initial candidates:

- mini-SWE-agent, because its small architecture makes experiments and community contributions easy;
- OpenHands, because it provides a broader software-agent platform and multi-agent research precedent.

Exit condition: the same Work Contract can be attempted by at least two heterogeneous agent stacks without coordinator changes.

## Milestone 4 — Independent verification and benchmark

Build a benchmark that is difficult to game and records hidden evaluation separately from worker execution.

Exit condition: approximately 20–50 bounded repository tasks can be replayed against different worker/orchestration strategies with comparable metrics.

## Milestone 5 — Run the flagship experiment

Compare:

- one strong agent;
- one small agent;
- repeated copies of one small agent;
- heterogeneous independent small agents;
- specialized planner/builder/tester/reviewer team;
- parallel DAG execution where the task really contains parallel work.

Publish raw results, negative results, reviewer effort, resource use, and error-correlation analysis.

The purpose is evidence, not proving the preferred hypothesis.

## Milestone 6 — GitHub community bridge

Make IDKMesh useful to external repositories without forcing them to adopt a new collaboration platform.

Candidate flow:

```text
GitHub issue
 -> Work Contract
 -> swarm run
 -> candidate branches/patches
 -> Evidence Report
 -> human review
 -> normal pull request
```

IDKMesh should initially strengthen normal open-source workflows, not bypass them.

## Milestone 7 — Provenance and stronger sandboxing

Add:

- content-addressed artifacts;
- signed results/verification;
- attestation format;
- reproducibility metadata;
- risk-tiered sandbox backends;
- OpenSSF security-baseline tracking for the project itself.

## Milestone 8 — 3–10 real machines

Only now add remote worker transport.

Test:

- churn;
- retries;
- slow workers;
- partitions;
- artifact transfer;
- heterogeneous environments;
- coordinator restart;
- malicious or corrupted results.

## Milestone 9 — 10–20 laptop community experiment

Run the existing self-improvement experiment with external contributors and ordinary machines.

The social experiment matters too: measure how much human coordination/review is required as worker count grows.

## Milestone 10 — Federation and scale research

Then test the Fractal Autonomous Cells hypothesis, distributed state, cross-organization trust, and eventual open compute economics.

Scale must be earned through evidence.

---

# 5. v0.1 definition

A useful `v0.1` should be small.

A newcomer should be able to:

1. install IDKMesh locally;
2. point it at a repository and bounded task;
3. configure at least two worker adapters;
4. launch multiple isolated candidates;
5. run an independent verification policy;
6. inspect an evidence report;
7. reproduce the run;
8. contribute a new worker or verifier adapter from documented interfaces.

`v0.1` does **not** require decentralized networking.

If IDKMesh cannot make this local workflow compelling, scaling it to thousands of machines will not fix the product.

---

# 6. Community evolution

The community should evolve in parallel with the code.

## Community milestone A

First 10 recurring contributors, including non-code contributors and at least a few reviewers/triagers.

## Community milestone B

Independent contributors own worker adapters, benchmark areas, docs, or verification plugins.

## Community milestone C

First external Reviewer and Community Steward roles become active.

## Community milestone D

Subsystem maintainership becomes distributed before contribution volume overwhelms the bootstrap maintainer.

The best attraction mechanism is a reproducible public result, not generic promotion.

The flagship experiment should be designed so outsiders can:

- reproduce one task;
- add one model/agent adapter;
- add one verifier;
- challenge one metric;
- submit a competing orchestration strategy;
- publish a negative result.

---

# 7. Research ideas worth testing next

## R1 — Diversity budget

Given a fixed compute budget, is it better to buy:

- more attempts from the same model;
- fewer attempts from heterogeneous models;
- specialized roles;
- more verification?

Measure marginal verified value.

## R2 — Adaptive fan-out

Do not always spawn N workers. Predict uncertainty/risk first, then allocate more candidate attempts only when expected value exceeds verification cost.

## R3 — Verification market

Treat verification capacity as scarce. Route higher-risk or higher-impact changes through stronger independent verification and cheaper low-risk changes through lightweight checks.

## R4 — Error-correlation routing

Measure which worker/model families fail together. Prefer additional workers that add independent evidence rather than correlated duplicates.

## R5 — Goal ambiguity as branching search

Represent competing interpretations explicitly. Use experiments/evidence to prune or promote branches rather than forcing consensus too early.

## R6 — Human attention scheduler

Human review is often the true scarce resource. Schedule escalation to humans by expected information gain, risk, disagreement, and potential impact.

## R7 — Community as part of the distributed system

Study contributor onboarding, review, mentoring, governance, and retention with the same seriousness as worker scheduling. A technical mesh that requires one human bottleneck is not scalable.

## R8 — Reputation by verified durability

Explore reputation based on independently verified contribution and long-term stability, with separate dimensions for implementation, review, security, reproduction, research, and community work.

## R9 — Competitive verifier ensembles

Use multiple verifier types with intentionally different failure modes. Study when disagreement is useful evidence rather than noise.

## R10 — Self-improvement with constitutional boundaries

Eventually let IDKMesh propose improvements to its own scheduler/verifier policies, but require fixed external benchmarks, rollback, human approval for constitutional changes, and evidence against Goodhart effects.

---

# 8. What would make IDKMesh genuinely different?

IDKMesh becomes distinctive if it can demonstrate all of the following together:

1. **heterogeneous workers** instead of one vendor/model;
2. **humans and agents in one work/evidence model**;
3. **uncertain goals represented explicitly** instead of hidden in chat context;
4. **verification as the primary trust mechanism**;
5. **measured diversity and correlated error** instead of raw majority voting;
6. **Git-native integration** with existing open-source practice;
7. **portable protocols/adapters** instead of a closed orchestration stack;
8. **progressive decentralization** based on measured need;
9. **scientific reproducibility and negative results** as first-class outputs;
10. **community scalability** measured alongside compute scalability.

That is a stronger identity than “many AI agents coding together.”

---

# 9. Decision rule for future ideas

Before adding a major mechanism, ask:

1. What problem does it solve?
2. Is that problem already solved by an open standard/project we can integrate?
3. What falsifiable hypothesis says the new mechanism will improve IDKMesh?
4. How will we measure it?
5. What is the verification/security model?
6. What does it cost in contributor complexity?
7. Can a newcomer understand or extend it?
8. Can we remove it if the experiment fails?

If those questions do not have credible answers, the idea belongs in research/IDKIP discussion rather than the core implementation.

---

# 10. Current recommendation

The immediate sequence is:

```text
community + IDKIP process
        -> interoperability mapping
        -> Work/Result contracts
        -> local verified swarm runner
        -> two heterogeneous agent adapters
        -> independent benchmark/verifier
        -> public flagship experiment
        -> GitHub bridge
        -> provenance + stronger sandboxing
        -> 3–10 machine mesh
        -> 10–20 laptop self-improvement study
        -> federation / economics / very-large-scale research
```

This keeps the project ambitious while giving every stage a concrete user, experiment, and community contribution path.
