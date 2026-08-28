# Findings — Distributed agent coding and collective software engineering

Date: 2026-08-28

## Working thesis

IDKMesh should investigate whether many weaker or cheaper coding agents can collectively outperform a single stronger agent when the system provides diversity, decomposition, isolation, verification, selection, integration, and governance.

This should be treated as an empirical hypothesis, not a guarantee.

## Why simple scaling fails

Adding more coding agents can increase throughput and search breadth, but also creates new failure modes:

- correlated mistakes across similar models;
- inconsistent architecture and interfaces;
- duplicated work;
- merge conflicts;
- review bottlenecks;
- malicious or compromised workers;
- evaluator gaming;
- excessive compute spent on redundant low-value work;
- loss of global context;
- local optimizations that damage system-wide maintainability.

Therefore quality must be designed as a system property.

## Recommended quality pipeline

A candidate change should move through explicit stages:

1. **Task definition** — scope, allowed surfaces, contracts, acceptance criteria.
2. **Independent generation** — one or more workers produce candidate solutions.
3. **Isolation** — workers operate in branches/worktrees/sandboxes.
4. **Automated verification** — build, unit/integration tests, hidden tests, lint/static analysis, type checking, dependency policy.
5. **Adversarial verification** — fuzzing, security checks, regression search, reviewer agents or humans.
6. **Comparative selection** — choose or synthesize candidates based on evidence rather than worker prestige alone.
7. **Subsystem review** — maintainers check architectural fit and non-local consequences.
8. **Integration** — controlled merge into canonical state.
9. **Post-merge observation** — monitor regressions and longer-term durability.
10. **Reputation update** — reward verified useful outcomes, including review and bug discovery.

## Best practices for a large open-source community

- Keep the mission understandable even while the solution remains uncertain.
- Publish governance and decision mechanisms early.
- Divide the system into owned subsystems with explicit interfaces.
- Use lightweight RFCs for cross-cutting changes.
- Protect the canonical branch with mandatory checks and reviews.
- Design excellent newcomer tasks with bounded scope.
- Reward review, testing, documentation, reproduction, and negative results—not only features.
- Keep important discussion asynchronous and public where practical.
- Maintain decision logs so repeated debates do not erase context.
- Prefer empirical experiments when architectural disagreements can be tested.
- Make it easy to run one node or one experiment locally.
- Avoid centralizing all knowledge in a few founders.

## Working toward an unclear target

An unclear global goal does not have to prevent coordinated work if the project separates levels of certainty:

- **North Star:** stable statement of why the project exists.
- **Problem statements:** specific pains the community wants to solve.
- **Hypotheses:** possible mechanisms or architectures.
- **RFCs:** concrete proposals.
- **Experiments:** bounded tests of proposals.
- **Evidence:** reproducible results.
- **Decisions:** temporary commitments with recorded rationale.

This allows different understandings of the project to coexist without requiring every disagreement to be resolved socially before progress is possible.

## Enterprise quality at community scale

The key distinction is between **who may propose work** and **what may enter the canonical product**.

Thousands of contributors can explore freely while the canonical software remains governed by:

- stable interfaces;
- subsystem ownership;
- protected branches;
- test and security gates;
- compatibility guarantees;
- release engineering;
- auditability and provenance;
- rollback mechanisms;
- observability;
- explicit architectural review.

The crowd can maximize exploration. The integration system must maximize reliability.

## Platform recommendation

For the initial public project, GitHub remains the strongest default because it combines source hosting, pull requests, issues, Actions/CI, discoverability, and a very large developer network.

However, IDKMesh protocols should not depend permanently on GitHub-specific concepts. Git should remain the portable artifact layer, while worker scheduling, identity, reputation, validation, and coordination APIs should be designed so that GitLab, Forgejo, Radicle, self-hosted infrastructure, or peer-to-peer systems can be evaluated later.

## Community growth recommendation

A high-attention project should give people something concrete to reproduce and improve. A particularly strong public artifact would be a recurring benchmark such as:

> 100 Small Coding Agents vs 1 Strong Model

with reproducible tasks and transparent measurements of quality, cost, latency, regressions, security, and human review effort.

This turns community participation into a visible scientific/engineering competition rather than generic requests for contributors.

## Social-media ideas worth borrowing

Borrow low-friction onboarding, personalized discovery of suitable tasks, following topics/subprojects, notifications, contribution profiles, visible recognition, shareable experiments, and progressive paths from observer to contributor to reviewer to maintainer.

Avoid optimizing for engagement time, follower-count authority, opaque ranking, controversy incentives, and vanity metrics that reward quantity over durable usefulness.

## Distributed-systems analogies

### BOINC

Strong analogy for untrusted volunteer workers. Duplicate important work, validate results independently, tolerate churn, and assign work based on capabilities.

### Folding@home

Strong analogy for heterogeneous volunteer compute and low-friction participation.

### BitTorrent

Useful ideas include work partitioning, decentralized distribution, integrity verification, and incentives. Limitation: software subtasks have semantic dependencies and cannot be treated as interchangeable file chunks.

### Skype-style supernodes

Useful reminder that a heterogeneous network can assign heavier coordination, relay, validation, or integration responsibilities to more capable nodes.

### Large open-source ecosystems

The most important lesson is organizational: subsystem ownership, governance, review, and release processes must scale with contribution volume.

## Related software-agent directions

Existing multi-agent coding frameworks demonstrate parts of the idea: role-specialized software-agent teams, parallel coding agents, isolated Git workspaces, and agent orchestration. IDKMesh should avoid reinventing these components unnecessarily and instead focus research on the harder combination of global heterogeneous workers, volunteer commodity compute, human + agent participation, verification under untrusted execution, reputation and anti-Sybil mechanisms, uncertain evolving goals, long-lived enterprise-quality integration, and decentralized or federated coordination.

## Next empirical milestone

Create a reproducible experiment comparing strong single-agent baselines against small-agent ensembles under several coordination strategies. The first goal is not to prove the thesis; it is to measure where the thesis fails and succeeds.
