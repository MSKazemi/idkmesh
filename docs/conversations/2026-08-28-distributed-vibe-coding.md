# Conversation record — Distributed vibe coding, many small models, and open collaboration

Date: 2026-08-28

This document preserves the useful project content from the IDKMesh discussion about coordinating many human "vibe coders", small coding models, laptops, and distributed agents on one evolving software project.

## Project-owner questions and ideas

The project owner proposed a Git-like environment in which many people and laptops, each potentially using different free or local coding models, work on the same project. Small pieces of coding work would be completed independently and then integrated algorithmically into a larger application.

The discussion expanded into these questions:

1. If one strong vibe coder uses a large model, can 100 vibe coders using small models guarantee equal or better code quality?
2. What are best practices for building an open-source community around a very large project?
3. How can a community work toward a common target when the target is not yet completely clear and participants interpret it differently?
4. How can thousands of human and AI contributors still produce enterprise-grade software?
5. What are the major unsolved research questions in this area?
6. Does a system like this already exist?
7. What are best practices for open-source engineering and governance?
8. How should the project attract stars, attention, contributors, and sustained participation?
9. Which collaboration platform is best: GitHub, GitLab, or newer/decentralized systems?
10. What lessons can be borrowed from social media without importing harmful engagement incentives?
11. What can be learned from large distributed systems, volunteer computing, BitTorrent, Skype/P2P, and distributed file-sharing systems?

## Core finding

The central conclusion is that:

> 100 small coding models do not automatically equal one strong model, and they cannot guarantee quality merely by voting or generating more code.

The potentially useful system is instead:

```text
diversity
+ task decomposition
+ isolated execution
+ independent attempts
+ independent verification
+ selection
+ integration
+ architectural governance
+ durable memory
= potentially stronger collective engineering
```

The word "potentially" is essential. More agents can also create correlated errors, duplicated effort, inconsistent abstractions, security problems, review overload, integration conflicts, and architectural drift.

## Proposed distributed software-company model

A useful conceptual structure is:

```text
Product / research goal
        |
        v
Planner / decomposition layer
        |
        v
Task dependency graph
        |
  +-----+------+-----+
  |            |     |
  v            v     v
worker A    worker B worker C
model/human  model    model
  |            |     |
  v            v     v
isolated Git branches / worktrees
        |
        v
independent tests + reviewers + security checks
        |
        v
selection / conflict resolution / integration
        |
        v
canonical main branch
```

Workers should receive bounded tasks with explicit allowed files, interfaces, contracts, tests, and acceptance conditions where possible. This reduces the amount of global context required by each small model.

## Redundancy as a quality mechanism

Multiple workers can attempt the same task independently. Candidate solutions can then be evaluated for:

- functional correctness;
- hidden-test performance;
- security;
- speed;
- memory use;
- compatibility;
- maintainability;
- code quality;
- regression risk.

This is closer to competitive search and validation than to simple majority voting.

## Specialization

A large worker population should not necessarily perform identical roles. Candidate roles include:

- implementation agents;
- debugging agents;
- test-generation agents;
- security-review agents;
- performance agents;
- architecture reviewers;
- documentation agents;
- adversarial reviewers;
- integration agents;
- human maintainers.

Worker capability should be measured empirically by domain. A scheduler could learn that one worker is strong in Python debugging but weak in architecture, while another is strong in React or security.

## Hierarchy and decomposition

A flat network of thousands of agents is likely to become unmanageable. Hierarchical or modular coordination may be necessary:

```text
project-level coordinator
        |
  +-----+------+-----+
  |            |     |
backend      frontend QA/security leads
  |            |     |
local task teams and workers
```

The precise hierarchy should remain an experimental question rather than a fixed assumption.

## Project constitution

The discussion identified a need for stable architectural constraints that ordinary workers cannot casually modify. Examples include:

- canonical interface definitions;
- dependency policy;
- schema migration rules;
- API compatibility requirements;
- security requirements;
- required test coverage or verification evidence;
- module ownership;
- limits on architectural changes without an RFC.

The purpose is not bureaucracy for its own sake; it is protection against thousands of locally reasonable changes that are globally incoherent.

## Verification principle

The strongest principle from the discussion is:

> Never trust an AI agent's answer because it sounds intelligent. Trust externally verifiable evidence.

Software is unusually suitable for this because important properties can often be tested automatically: compilation, tests, API behavior, static analysis, fuzzing, performance, security scans, compatibility, and reproducibility.

Verification must itself be protected from manipulation. Workers should not be able to rewrite tests or evaluation logic merely to make their own patch pass unless that change is explicitly part of the task and independently reviewed.

## Volunteer-compute extension

A long-term IDKMesh network could resemble volunteer-computing systems:

```text
volunteer laptop joins network
        |
announces capabilities
        |
receives bounded work unit
        |
runs local model / tests / analysis
        |
submits patch + evidence
        |
independent validators reproduce or challenge result
        |
accepted result contributes to canonical project
```

The network could eventually include heterogeneous participants: local small models, stronger remote models, humans, GPU machines, test runners, and specialized security nodes.

## Incentives and reputation

The discussion proposed contribution accounting based on verified usefulness rather than raw activity. Valuable contributions can include:

- accepted durable patches;
- bugs discovered;
- regressions prevented;
- high-quality reviews;
- security vulnerabilities found;
- benchmark reproduction;
- documentation improvements;
- architectural clarification;
- useful negative experimental results.

Reputation should be multidimensional and domain-specific. It should not become a simple popularity score.

## Open-source governance lessons

The project should separate exploration from authority over the canonical branch. A large population can generate proposals and experiments, but integration should remain gated by tests, maintainers, subsystem ownership, and explicit governance.

Useful patterns include:

- subsystem ownership similar to large projects such as Kubernetes;
- public asynchronous decision records;
- lightweight RFCs for cross-cutting changes;
- protected main branches and required checks;
- contribution authority earned through demonstrated work;
- clear newcomer paths;
- visible ownership rather than vague governance.

## Working with an unclear goal

IDKMesh should not require universal agreement on a fully specified target. Instead it can maintain several layers:

1. a relatively stable North Star;
2. explicit hypotheses;
3. competing RFCs;
4. bounded experiments;
5. empirical evidence;
6. decisions that can later be revised.

Different interpretations can sometimes be implemented in parallel and compared rather than resolved entirely through discussion.

## Platform strategy

The recommendation from this discussion is:

- **GitHub** as the initial public front door because of ecosystem, discoverability, contributors, issues, pull requests, and CI;
- **Git** as the portable canonical artifact/provenance model;
- worker and orchestration protocols designed to remain forge-independent;
- GitLab, Forgejo, Radicle, or P2P replication explored later where decentralization or self-hosting becomes valuable.

## Lessons from social media

Potentially useful ideas:

- low-friction onboarding;
- personalized feeds of suitable work;
- following topics/subprojects;
- notifications;
- profiles and contribution history;
- visible recognition;
- shareable experiments and results;
- progressive paths from observer to contributor to reviewer to maintainer.

Ideas to avoid:

- engagement maximization as a primary goal;
- follower count as technical authority;
- opaque ranking;
- rewarding quantity of commits over usefulness;
- outrage or conflict as growth mechanisms.

## Lessons from distributed systems

### BOINC / volunteer computing

Assume workers can fail, disconnect, disagree, or be malicious. Important work can be replicated and independently validated before a canonical result is accepted.

### Folding@home

Match work units to heterogeneous hardware and make joining the network easy. Visible contribution statistics can motivate participation, but technical correctness still requires verification.

### BitTorrent

Break a large object into independently handled pieces, verify integrity, distribute load, and avoid relying on a single source. IDKMesh can borrow the work-unit and swarm intuition, but software tasks are not interchangeable chunks and need dependency/semantic awareness.

### Skype / supernode-style P2P

Not every participant must have the same role. Better-connected or more capable nodes can coordinate, relay, validate, or integrate work for lighter nodes.

### Large open-source projects

Scaling code generation without scaling maintainership, ownership, review, testing, and governance will fail. Technical and social architecture must evolve together.

## Related directions already existing

Pieces of the idea exist in modern multi-agent coding systems and agent orchestration projects. Examples discussed include OpenHands-style isolated coding agents, MetaGPT-style software-company roles, and ChatDev-style multi-agent development. The distinct IDKMesh research direction is the combination of:

- many heterogeneous/free/local models;
- human contributors;
- volunteer/commodity compute;
- Git-native provenance;
- independent verification;
- uncertain goals;
- open governance;
- large-scale reputation and scheduling;
- possible decentralization of coordination itself.

## Proposed first experiment

Do not begin by attempting a thousand-agent enterprise application. First test whether the core premise works.

Compare on the same controlled task set:

- one strong coding model;
- one small model;
- five independent small-model attempts;
- ten independent small-model attempts;
- specialized planner/implementer/tester/reviewer teams;
- parallel DAG-based teams where tasks are truly independent.

Measure:

- accepted-task rate;
- hidden-test success;
- regressions;
- security findings;
- human correction/review time;
- merge conflicts;
- wall-clock time;
- compute consumed;
- cost per accepted change;
- maintainability after integration.

## Important project interpretation

The final intelligence may not reside in one model. It may emerge from the overall process:

```text
decomposition
-> parallel attempts
-> criticism
-> testing
-> selection
-> integration
-> memory
-> iteration
```

Under this interpretation, the orchestrator, verification network, governance, and accumulated project memory together form the higher-level collective intelligence.
