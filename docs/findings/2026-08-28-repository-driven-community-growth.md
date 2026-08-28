# Repository-Driven Community Growth and Agent Automation

Date: 2026-08-28

## Goal

Make the GitHub repository itself the primary discovery, onboarding, collaboration, and contribution surface so IDKMesh can grow without requiring its maintainer to spend large amounts of time on social media or advertising.

## Core thesis

Community growth should be treated as a product, systems, and research problem rather than a marketing chore.

The desired flywheel is:

`discover -> understand -> find bounded work -> contribute -> verify -> recognize -> return -> help another contributor -> discover`

A repository cannot guarantee thousands of contributors. Organic growth still requires something genuinely useful, credible, interesting, or unusually easy to contribute to. But the repository can be engineered so every useful contribution improves both the technical project and the probability of the next useful contribution.

## Community reproduction number

Define a working metric `R_c`:

> Expected number of new retained contributors eventually caused by one active contributor or one completed contribution cycle.

This is a branching-process-inspired abstraction, not a claim that communities literally behave like epidemics.

- `R_c > 1`: contributor population can grow organically.
- `R_c ~= 1`: community is roughly self-sustaining.
- `R_c < 1`: the maintainer must continually recruit people manually to prevent decay.

Track at least:

- time to first useful contribution;
- time to first response;
- starter-task claim and completion rates;
- first-contribution success rate;
- 30/90-day return rate;
- review latency;
- disciplines represented;
- cross-discipline graph connectivity;
- contributors who review/help another contributor;
- verified output per maintainer hour.

The last metric is critical: community growth should reduce owner workload per unit of useful progress.

## GitHub-native discovery

1. Use accurate repository topics such as `distributed-systems`, `multi-agent-systems`, `collective-intelligence`, `distributed-computing`, `ai-agents`, `complex-systems`, `mechanism-design`, `volunteer-computing`, and `developer-tools`.
2. Maintain a real supply of `good first issue` and `help wanted` work across disciplines. GitHub documents that `good first issue` can increase how approachable issues are surfaced.
3. Complete the community-health profile: README, CONTRIBUTING, CODE_OF_CONDUCT, LICENSE, SECURITY, governance, issue forms/templates.
4. Use GitHub Discussions as the primary community forum for ideas, research, architecture, experiments, mathematics, physics, agents, security, UX, governance, and onboarding rather than forcing participation into Discord/Slack/social platforms.
5. Use GitHub Pages as a generated visual front door, with repository content remaining canonical.
6. Publish reproducible releases and experiments so watchers receive meaningful update signals.

## Multidisciplinary contribution lanes

Contribution must not mean only “write code.”

- Computer science: protocols, scheduling, CRDTs, runtimes, APIs, simulations.
- AI/agents: planners, builders, reviewers, model routing, agent evaluation.
- Mathematics: optimization, graph models, game theory, proofs, counterexamples.
- Physics/complex systems: percolation, synchronization, transport, statistical models.
- Economics: incentives, public-goods mechanisms, market design, anti-Sybil economics.
- Security: threat models, adversarial tests, sandboxing, provenance.
- Web/UX: dashboards, onboarding flows, visual task graphs.
- Art/design: identity, diagrams, information visualization.
- Governance/social science: decision protocols, moderation, conflict resolution.
- Research/academia: literature maps, replication studies, experiment design.
- Compute contributors: reproducible worker nodes and hardware benchmarking.

Use bridge tasks that connect disciplines, for example:

`physicist formulates -> mathematician formalizes -> programmer implements -> designer visualizes -> verifier benchmarks`.

## Free / low-cost robot layer

Separate deterministic maintenance bots from AI agents.

### Deterministic automation first

- GitHub Actions for CI, tests, scheduled repository-health checks, and documentation validation. Standard GitHub-hosted runners are free for public repositories; larger runners are not.
- Dependabot for vulnerability alerts and dependency-update PRs.
- GitHub code scanning / CodeQL for public repositories.
- Secret scanning / push protection.
- OpenSSF Scorecard Action for supply-chain posture.
- Renovate as an open-source/self-hostable alternative for dependency automation. Avoid overlapping Renovate and Dependabot PR noise unless roles are explicitly separated.

### Open-source AI coding/research agents

Agents can avoid API fees when run against local open-weight models, although hardware/electricity still has a cost.

Promising current options:

- OpenHands with local models via Ollama, LM Studio, vLLM, or SGLang.
- SWE-agent / mini-swe-agent with local OpenAI-compatible endpoints, including Ollama-style configurations.

Initially use these as proposal engines, not unrestricted autonomous maintainers.

## Proposed IDKMesh self-evolution loop

Roles:

1. Observer — detects CI failures, documentation gaps, stale experiments, oversized issues, security signals.
2. Planner — translates accepted problems into bounded Work Units and acceptance tests.
3. Builder — creates a proposed branch/change.
4. Critic — independently searches for mistakes, hidden assumptions, security issues, and duplication.
5. Verifier — deterministic tests, linting, benchmarks, reproducibility checks, security scans.
6. Integrator — human or explicit multi-party policy decides whether to merge.
7. Historian — updates decisions, experiment results, acknowledgements, and durable docs.

Safety invariant:

`agent proposal -> independent review -> deterministic verification -> protected merge`

An agent should never be allowed to propose, approve, and merge the same change by itself. High-risk changes should require human approval.

## Repository-only community autopilot

A future scheduled agent can propose issues/PRs for:

- broken/missing docs;
- unlabeled or oversized issues;
- vague ideas that can become bounded Work Units;
- stale starter tasks;
- benchmark regressions;
- dependency/security maintenance;
- newly relevant papers/repositories;
- duplicate research questions;
- contributor recognition summaries;
- cross-discipline collaboration opportunities;
- project-health metrics.

It should never mass-message strangers, scrape private contact data, spam unrelated repositories, or create unsolicited advertising issues elsewhere.

## Physics- and mathematics-inspired mechanisms

- Activation energy: first-contribution effort is an activation barrier; minimize it.
- Percolation: measure whether contributor/discipline graphs form a healthy connected giant component rather than isolated clusters.
- Queueing theory: review requests are queues; long review latency signals capacity instability.
- Control theory: dynamically adjust starter-task supply and task size based on contribution/review rates.
- Information theory: reward uncertainty reduction, including negative results and counterexamples, not only code volume.
- Evolutionary selection: experiment with contribution processes and retain mechanisms that improve verified output, retention, and maintainer leverage.

## Innovative questions

1. Can `R_c > 1` be achieved with no maintainer-operated social-media channel?
2. Which GitHub-native signals best predict visitor-to-contributor conversion?
3. Do reproducible experiments attract more durable contributors than visionary documentation alone?
4. Can machine-readable research questions improve discovery by AI agents as well as humans?
5. Can releases automatically generate scientifically meaningful starter tasks?
6. What is the maximum acceptable time to first useful contribution?
7. How does issue size affect claim rate, completion rate, and return rate?
8. Can an AI onboarding agent improve first-contribution success while reducing maintainer time?
9. Does immediate machine verification compensate for slower human review?
10. Which recognition mechanisms increase repeated contribution without creating a low-quality points game?
11. What representation lets physicists, mathematicians, programmers, security researchers, and artists collaborate without sharing vocabulary?
12. Can contribution tasks become typed interfaces between disciplines?
13. How can useful cross-disciplinary coupling be measured?
14. Is there a contributor-graph percolation threshold beyond which knowledge spreads productively?
15. Can bridge contributors/agents reduce fragmentation between specialist communities?
16. Should AI agents be first-class public contributors with explicit identities and provenance?
17. How should human-authored, agent-authored, and mixed contributions be distinguished?
18. Can agents generate starter tasks continuously without flooding the issue tracker with low-value work?
19. What is the correct builder-to-critic/verifier ratio?
20. Can multiple cheap local agents produce trustworthy triage/review through diversity and independent verification?
21. Which automated actions can safely merge without a human, and which must never do so?
22. How should agent reputation account for correlated failures among clones of the same model?
23. At what contributor count does a single-maintainer review model become unstable?
24. Can trusted contributors earn scoped permissions from verified history rather than informal status?
25. Can the project dynamically create cells/teams when the contributor graph becomes too dense for one coordination layer?
26. How can IDKMesh detect isolated or viewpoint-captured subcommunities?
27. Can governance mechanisms be experimentally compared using project-health metrics?
28. What anti-spam/anti-Sybil mechanisms preserve a very low barrier for legitimate newcomers?
29. Can reputation reward criticism and negative results as strongly as code production?
30. What is the smallest owner workload compatible with a growing, safe, technically serious community?

## Immediate priorities

### P0 — remove newcomer friction

- add CONTRIBUTING.md;
- add CODE_OF_CONDUCT.md;
- add LICENSE consistent with README;
- add SECURITY.md;
- expose multidisciplinary contribution paths;
- add issue forms/templates;
- maintain real `good first issue` and `help wanted` backlogs.

### P1 — GitHub-native discovery

- add accurate repository topics;
- enable Discussions;
- create a generated GitHub Pages front door;
- publish the first runnable experiment/release;
- add a social-preview image so links shared by other people render well.

### P2 — deterministic automation

- CI/documentation checks;
- dependency automation;
- CodeQL/code scanning;
- secret scanning/push protection;
- OpenSSF Scorecard;
- automated benchmark publication.

### P3 — bounded agent automation

- local/self-hosted Observer;
- Planner/Builder;
- independent Critic;
- agents open issues/PRs, but do not self-merge;
- measure whether the loop actually reduces maintainer workload.

## References checked

- GitHub community profiles: https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/about-community-profiles-for-public-repositories
- Helpful contribution labels: https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/encouraging-helpful-contributions-to-your-project-with-labels
- Repository topics: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics
- GitHub Discussions: https://docs.github.com/en/discussions/collaborating-with-your-community-using-discussions/about-discussions
- GitHub Actions billing/usage: https://docs.github.com/en/actions/concepts/billing-and-usage
- GitHub Pages: https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site
- Repository security/analysis settings: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-security-and-analysis-settings-for-your-repository
- OpenSSF Scorecard Action: https://github.com/ossf/scorecard-action
- OpenHands local LLM docs: https://github.com/OpenHands/docs/blob/main/openhands/usage/llms/local-llms.mdx
- SWE-agent: https://github.com/SWE-agent/SWE-agent
- Renovate GitHub platform docs: https://docs.renovatebot.com/modules/platform/github/

## Working decision

Repository-driven organic growth should be treated as a first-class IDKMesh technical experiment. External social media can amplify the project later but should not be a dependency for its survival or growth.
