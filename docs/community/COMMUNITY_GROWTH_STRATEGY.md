# IDKMesh Community Growth Strategy

## Objective

Build a large, healthy, technically serious global community around IDKMesh **before** the system requires large-scale participation to function.

Community growth is not a marketing phase after engineering. It is a parallel product and systems problem.

## Starting assumptions

1. A complicated project with an unclear final target has unusually high onboarding risk.
2. AI-generated contribution volume can grow much faster than human review capacity.
3. People stay when they can see useful work, receive timely feedback, understand how decisions are made, and see a path toward greater responsibility.
4. The project needs many legitimate forms of contribution, not only core code.
5. GitHub should be the initial discovery and collaboration front door because of its open-source network effects, while project protocols remain portable.

## Design goals for the community system

Optimize for:

- first-time understanding;
- first successful contribution;
- second contribution / retention;
- reviewer growth;
- maintainer growth;
- diversity of contribution types;
- low concentration of critical knowledge;
- transparent decision-making;
- useful public artifacts;
- sustainable review and moderation workload.

Do **not** optimize primarily for star count, raw commit count, message volume, or AI-generated output volume.

## The contributor funnel

```text
Discover
  -> Understand
      -> Try
          -> First contribution
              -> Useful review/feedback
                  -> Second contribution
                      -> Recurring contributor
                          -> Reviewer / Steward
                              -> Maintainer / subproject leader
```

Each transition should eventually be measured. A large number of repository visitors is not a healthy community if almost nobody can make a successful first contribution.

## Phase 0 — Make the front door credible

Before broad promotion:

- README explains the project in under a few minutes;
- CONTRIBUTING exists and is short enough to use;
- COMMUNITY and GOVERNANCE explain roles and leadership paths;
- Code of Conduct, SUPPORT, SECURITY, and MAINTAINERS exist;
- issue and pull-request templates teach contribution norms;
- several genuinely small starter tasks exist;
- at least one reproducible public experiment exists or is clearly specified;
- newcomer questions receive useful answers.

This phase is more important than logo/branding work.

## Phase 1 — Create a shareable public experiment

The first growth engine should be an interesting, reproducible result rather than generic promotion.

Candidate headline experiment:

> **Can 10–20 ordinary laptops running diverse coding agents outperform a single-agent baseline per unit of human attention and compute?**

Publish:

- exact methodology;
- reproducible runner;
- raw/processed results;
- failures and negative results;
- cost and human-review measurements;
- a public table/dashboard;
- tasks that allow outsiders to reproduce or improve one component.

A project people can *test* is easier to join than a project people can only read about.

## Phase 2 — Grow contribution surfaces

Create independent contribution lanes:

- scheduler / distributed systems;
- coding-agent experiments;
- verification and benchmarks;
- security / sandboxing / provenance;
- goal/task graph;
- mathematical and statistical research;
- documentation and education;
- community/onboarding;
- UX/developer tooling;
- domain applications.

Each lane should have:

- an understandable scope;
- one-page getting-started documentation;
- starter issues;
- reviewer ownership;
- visible metrics or outputs;
- interfaces with other lanes.

## Phase 3 — Turn contributors into leaders

The project will not scale if every decision returns to the founder.

Mechanisms:

- invite reliable contributors to review within scoped areas;
- recognize excellent review, testing, docs, research, and community work;
- publish maintainer criteria;
- use rotating triage/review responsibilities;
- delegate bounded subprojects when activity justifies them;
- move inactive maintainers to emeritus status without erasing credit;
- document decisions and interfaces so leadership transfer is possible.

## Phase 4 — Federation of community and technical ownership

If the project becomes large, governance can mirror the technical architecture:

```text
contributor
 -> scoped working area / cell
 -> subproject
 -> cross-project coordination
 -> minimal shared constitution / protocols
```

Most decisions should stay close to the people doing the work. Global governance should focus on shared protocols, security invariants, community principles, cross-project conflicts, and project-level resources.

## Community-first issue design

Good issues are a major onboarding interface.

Every issue intended for outside contributors should make clear:

- why the work matters;
- what a successful result looks like;
- relevant files/docs;
- prerequisites;
- how to test/verify;
- approximate scope;
- whether parallel attempts are welcome;
- whom/where to ask for help.

Avoid vague issues such as “build the scheduler” or “improve architecture.” Break them into verifiable Work Units.

## Documentation architecture

Use progressive disclosure:

### Level 1 — visitor

README: what, why, status, how to join.

### Level 2 — contributor

CONTRIBUTING, COMMUNITY, starter issues, quick-start commands.

### Level 3 — subsystem contributor

Architecture, protocols, ADRs, tests, experiment docs.

### Level 4 — researcher / maintainer

Mathematical foundations, scientific foundations, deep research notes, governance evolution, threat models.

Do not make Level 4 reading a prerequisite for Level 2 participation.

## Recognition without turning the project into social-media competition

Borrow useful social mechanisms:

- visible contributor profiles/credits;
- acknowledgements in releases;
- badges or roles tied to real responsibility;
- public experiment leaderboards when metrics are meaningful;
- activity feeds / digest summaries;
- easy sharing of reproducible results;
- topic following and notifications.

Avoid:

- follower-count authority;
- rewarding raw message/commit volume;
- opaque engagement ranking;
- incentives that encourage spam or low-quality AI generation;
- popularity as a substitute for evidence or review.

## Community metrics

Track aggregate trends such as:

- median time to first response;
- median PR review time;
- first-time contributor acceptance rate;
- first -> second contribution conversion;
- active contributor / reviewer / maintainer counts;
- percentage of accepted contributions that are non-code;
- contributor concentration;
- stale issue/PR counts;
- contributor retention cohorts;
- review workload per maintainer;
- community-documentation improvements triggered by newcomer confusion.

Use these as diagnostics, not performance quotas.

## Distribution and visibility strategy

Priority order:

1. create a remarkable reproducible experiment;
2. make the repository immediately understandable;
3. provide tiny ways to participate in the experiment;
4. publish results and failures openly;
5. invite adjacent communities (AI agents, distributed systems, open-source governance, volunteer computing, security, benchmarking);
6. give contributors credit and ownership;
7. repeat experiments with community improvements.

Potential channels later include GitHub, technical blogs, research/preprint venues, Hacker News, Reddit communities, developer social networks, conferences/meetups, university labs, open-source foundations, and agent-framework communities. Channel activity should lead back to durable public artifacts in the repository.

## Current platform recommendation

Use GitHub as the initial public front door and source-of-record because discoverability, pull requests, issues, review, Actions, security features, and contributor familiarity reduce onboarding friction.

Keep the underlying Work Unit, identity/capability, artifact/provenance, and coordination protocols forge-neutral so the project can later integrate GitLab, Forgejo, Radicle, or other decentralized/federated systems.

## Practices this strategy draws from

Useful external guidance includes:

- GitHub community health files: https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file
- CNCF contributing-guide practices: https://contribute.cncf.io/projects/best-practices/templates/contributing/
- CNCF governance guidance: https://contribute.cncf.io/projects/best-practices/governance/
- CNCF contributor-growth guidance: https://contribute.cncf.io/projects/best-practices/community/contributor-growth/

These are references, not rigid templates. IDKMesh governance should describe the community that actually exists and evolve as that community grows.
