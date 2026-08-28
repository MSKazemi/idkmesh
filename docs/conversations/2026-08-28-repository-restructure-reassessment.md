# Repository Restructure Reassessment

Date: 2026-08-28

## User question

What should IDKMesh do next in the repository? Does the repository need to be restructured, and if so, how?

## Short answer

**Yes — restructure incrementally, not as a bulk cleanup.**

The repository now has two competing information architectures:

1. many substantial Markdown documents at repository root; and
2. a typed `docs/` hierarchy (`architecture`, `research`, `community`, `decisions`, `specifications`, `planning`, `audits`, `findings`, `conversations`, and related modules).

That duplication increases navigation cost for newcomers, contributors, and future agents. The root should increasingly function as the project front door rather than the complete knowledge base.

At the same time, the executable product kernel is still much smaller than the conceptual/research surface. Therefore the restructuring effort should primarily simplify information architecture without creating a large new code/package migration before the Verified Swarm Runner path stabilizes.

## Important current-state finding

The repository already has the right restructuring direction:

- Issue #35: protect `main` before stronger autonomous writes;
- Issue #20: deterministic IDKGraph/repository observatory;
- PR #36: proposal-first Repository Homeostasis Engine (RHE);
- Issue #38: first bounded structural migration into `docs/foundations/`.

However, PR #36 is currently a draft whose branch has diverged substantially from current `main`. Its last observed RHE workflow passed on the branch head, but the branch must be refreshed/recreated against current `main` and re-reviewed before it is used as the structural controller.

This means the repository should **not** perform a broad manual move now.

## Recommended sequence

### P0 — Establish the integration safety boundary

Complete #35 first or in parallel with the observatory work:

- require PR-based integration for structural/code changes;
- block force pushes/deletion of `main`;
- require stable checks;
- require independent review for medium/high-risk structural, protocol, governance, security, and autonomous-evolution changes;
- keep the invariant that one autonomous actor cannot propose, approve, and merge the same protected change.

### P0 — Refresh the Repository Homeostasis Engine

Refresh or replace PR #36 on top of current `main` rather than merging the stale branch blindly.

Then:

1. rerun deterministic repository-health checks;
2. verify the workflow trust boundary;
3. obtain independent review;
4. merge RHE only as an observer/proposal system;
5. keep automatic file movement/deletion disabled.

### P0 — Run a fresh structural baseline

Measure the current repository before moving anything:

- root Markdown count;
- documents outside the root policy;
- broken internal links;
- orphaned documents;
- crowded directories;
- oversized documents;
- link density/navigation reachability;
- migration cost proxies.

Issue #38 records a recent refined baseline with structural pressure around `65/100`, 24 root Markdown files, 13 root documents outside the intended policy, and zero broken internal links. Re-measure after refreshing RHE because `main` is evolving quickly.

### P0 — Execute only Structural Migration 001 (#38)

The first migration should remain deliberately small:

```text
VISION.md
GOALS.md
FIELD_DEFINING_QUESTIONS.md
        |
        v
docs/foundations/
```

Add:

`docs/foundations/README.md`

Requirements:

- preserve document meaning/history;
- repair every repository-relative inbound link;
- keep newcomer navigation clear;
- keep broken links at zero;
- do not create new orphans;
- compare RHE metrics before/after;
- record migration cost and reviewer effort;
- merge only if the new structure is measurably simpler.

Do **not** bundle mathematical/scientific foundations, research strategy, community strategy, architecture, governance, schemas, and code movement into the same PR.

## Recommended target topology

A useful long-term target is:

```text
/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── COMMUNITY.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── SUPPORT.md
├── GOVERNANCE.md
├── MAINTAINERS.md
├── ROADMAP.md
├── PROJECT_RULES.md
├── IDKIPS.md
├── docs/
│   ├── README.md
│   ├── foundations/
│   ├── architecture/
│   ├── research/
│   ├── community/
│   ├── decisions/
│   ├── specifications/
│   ├── protocols/
│   ├── planning/
│   ├── audits/
│   ├── findings/
│   └── conversations/
├── schemas/
├── examples/
├── experiments/
├── tests/
├── tools/
├── config/
└── src/idkmesh/            # when the v0.1 product kernel is stable enough
```

The exact taxonomy should remain evidence-driven rather than fixed by aesthetics.

## Candidate later migrations

Only after Migration 001 succeeds, consider one coherent category at a time.

### Architecture/evolution

Candidates include root documents such as `ARCHITECTURE.md`, `EVOLUTION.md`, and `ITERATION_MODEL.md`, with canonical homes under architecture/planning/protocol modules as appropriate.

### Scientific/research foundations

Candidates include `MATHEMATICAL_FOUNDATIONS.md`, `SCIENTIFIC_FOUNDATIONS.md`, `RANDOMNESS_AND_BIOINSPIRED_ALGORITHMS.md`, `BLOCKCHAIN_STRATEGY.md`, and `RESEARCH_QUESTIONS.md`.

These should not all be called "foundations" automatically; some are research programs or strategy documents and should move according to semantic role.

### Community engine

`COMMUNITY_GROWTH_ENGINE.md` can eventually become part of the `docs/community/` module while `COMMUNITY.md` stays at root as a contributor-facing entrypoint.

### Decisions

`DECISIONS.md` should eventually become either a small root index into `docs/decisions/` or move entirely under that module if navigation remains obvious.

## Code structure recommendation

Do **not** perform a large code repackage solely for visual cleanliness yet.

The current priority is to make the canonical local worker, verifier, orchestrator, and Evidence Report executable. When that product kernel stabilizes, separate:

- durable product/runtime code -> `src/idkmesh/`;
- research simulators and experimental policies -> `experiments/`;
- repository/maintenance automation -> `tools/`;
- tests -> `tests/` (or experiment-local tests where isolation is useful).

Current simulator/package paths should be consolidated only when import/CI migration cost is justified by a real product boundary.

## Structural design rule for future self-evolution

Use the repository as a controlled adaptive system:

```text
observe
 -> measure structural pressure
 -> propose one bounded typed rewrite
 -> repair links / simulate checks
 -> independent review
 -> merge
 -> measure actual effect
 -> update structural-policy evidence
```

Iteration count should determine **when to inspect**. Evidence should determine **whether to restructure**.

## Immediate recommendation

1. protect `main` (#35);
2. refresh/recreate PR #36 against current `main` and re-run checks;
3. establish a fresh RHE baseline;
4. execute only #38 as the first structural migration;
5. then return project attention to the executable Verified Swarm Runner path (#34/#5/#4/#16) rather than continuing documentation expansion;
6. allow the next migration only after the first one shows measurable benefit.

This keeps restructuring reversible, testable, newcomer-friendly, and compatible with IDKMesh's guarded self-evolution goals.
