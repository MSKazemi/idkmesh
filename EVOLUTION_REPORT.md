# IDKMesh Evolution Report

**Status:** reviewed current-state synthesis, not controller state  
**Snapshot date:** 2026-09-10  
**Baseline before this report update:** `main` at `bc7910c0ef2ece8961917cda41fafcca198d8bcb`  
**Audience:** maintainers, contributors, independent reviewers, and researchers

## Purpose

This file answers one operational question:

> **What is the weakest evidence-backed bottleneck in IDKMesh now, what bounded intervention is justified, and what evidence would allow the project to retain, reject, or revise it?**

It is a repository-authored index and synthesis. It is **not** the live Bayesian
checkpoint, the live repository observatory, an approval signal, or an autonomous
policy surface. Volatile machine observations belong in exact-run GitHub Actions
artifacts and job summaries; durable conclusions belong in reviewed repository
artifacts.

The project North Star remains the one stated in the [roadmap](ROADMAP.md):
**verified useful work under scarce human attention and compute**, while keeping
risk and integration authority explicit rather than optimizing raw activity.

## Current repository checkpoint

At the baseline revision above, the repository already contains substantial
mechanism rather than only plans:

- typed WorkUnit/result/verification/experiment/compute/graph contracts;
- deterministic schema and cross-object validation;
- independent verification and evidence machinery;
- replay/non-selecting reporting experiments;
- protocol-neutral worker boundaries plus interoperability mappings;
- zero-project-spend compute routing/admission experiments;
- IDKGraph repository observability and link-integrity tooling;
- persistent Bayesian evolution history, a live repository observatory, a
  mathematical portfolio, and conjunctive non-compensation control;
- ACE community-growth observation/control experiments;
- protected `main` with stable Python 3.11/3.13 PR gates.

Two recent reliability changes are part of this checkpoint:

- [PR #414](https://github.com/MSKazemi/idkmesh/pull/414) isolated Repository
  Mathematical Portfolio advisory cancellation per pull request while preserving
  one canonical persistent-state lineage;
- [PR #419](https://github.com/MSKazemi/idkmesh/pull/419) made ACE Growth Seed
  effects convergent under the serialized ledger writer, with bounded fail-closed
  recovery for dropped pending events.

Those are **implemented and CI-verified mechanisms**. They do not by themselves
constitute independent real-world validation of the larger system.

## Evidence classes

Do not collapse these classes into one word such as “done” or “proven”.

| Evidence class | What counts here | Current interpretation |
| --- | --- | --- |
| **Implemented mechanism** | merged code, schemas, workflows, documented control boundaries | substantial coverage exists on `main` |
| **Synthetic/test evidence** | unit/integration tests, fixtures, mutation tests, simulations, replay checks | broad and useful, but not a substitute for field evidence |
| **Observed repository evidence** | measured GitHub runs, issue/PR state, repository observatory output, retained exact-run artifacts | increasingly available; must remain tied to provenance |
| **Accepted / independent evidence** | genuinely separate review, independently reproduced results, real descendant outcomes, delayed outcome checks | **still the weakest layer** |

A mechanism can therefore be implemented and heavily tested while its external or
causal claim remains unresolved.

## Active evidence gates

Only currently open work is listed here as active.

### Gate 1 — independent current-main control-plane review

[Issue #151](https://github.com/MSKazemi/idkmesh/issues/151) is open and requires
a genuinely separate reviewer to inspect the actual current-main mathematical
control plane, report blockers or disagreements, and link resulting fixes when
needed.

This gate cannot be satisfied by the controller reviewing itself or by another
assistant assertion. It is deliberately an external falsification boundary.

### Gate 2 — real descendant evidence before stronger ACE actuation

[Issue #57](https://github.com/MSKazemi/idkmesh/issues/57) remains open. Its
activation checklist still requires at least one cohort with **real descendant
evidence rather than only raw activity proxies** before stronger autonomous ACE
actuation is justified.

The reliability fix in PR #419 makes seed effects recoverable; it does not satisfy
this outcome-evidence gate.

### Research track — calibrate the mathematical foundation against outcomes

[Issue #86](https://github.com/MSKazemi/idkmesh/issues/86) remains open as the
research program for turning the mathematical foundation into measured,
replaceable repository mechanisms. It is a research/calibration track, not a
blanket authority gate.

## Current measured signals

The durable repository should not hard-code a volatile posterior or live issue
count without exact provenance. Use these machine surfaces for current values:

- the [IDKMesh Evolution Loop workflow](.github/workflows/evolution-loop.yml)
  publishes exact-run `evolution-checkpoint-v2-<run_id>` artifacts;
- [Repository Evolution Observatory](docs/architecture/REPOSITORY_EVOLUTION_OBSERVATORY.md)
  documents the recomputed live repository-health layer;
- [Repository Mathematical Portfolio](docs/architecture/REPOSITORY_MATHEMATICAL_PORTFOLIO.md)
  documents Pareto/UCB attention allocation;
- [Conjunctive Evolution Control](docs/architecture/CONJUNCTIVE_EVOLUTION_CONTROL.md)
  documents the non-compensating combination of history and live guards;
- [ACE Convergent Recovery](docs/architecture/ACE_CONVERGENT_RECOVERY.md)
  documents the current serialized-ledger recovery contract.

`state/evolution-state.json` is a checked-in seed/fallback, **not** a claim to be
the latest trusted live checkpoint. For a live conclusion, name the workflow run
and artifact that produced it.

## Highest-priority bottleneck

**Independent, real-world evidence is lagging the amount of implemented
mechanism.**

That is more important than adding another controller. The repository already has
multiple observation, verification, portfolio, and control layers. The weakest
link is demonstrating—through separate review and real outcomes—which of those
mechanisms deserve continued trust and which assumptions should be revised.

This is consistent with the [roadmap](ROADMAP.md), which says the project must
earn scale and currently needs independently reviewed, real, comparable execution
evidence rather than more first-principles scaffolding.

## Next bounded decision

**Primary next intervention: complete one genuinely independent current-main
control-plane review under issue #151.**

The review should inspect code/workflows rather than PR prose and produce one of:

1. no blocker, with explicit evidence for the reviewed trust boundaries;
2. a bounded blocker/follow-up issue;
3. a focused corrective PR.

Decision rule:

- **retain** the reviewed mechanism when the independent review finds no blocker
  and its evidence is inspectable;
- **revise** it when the review exposes a bounded correctable weakness;
- **reject or disable the affected behavior** when a blocker invalidates a
  safety/authority assumption and cannot be bounded safely.

After that review boundary, the next empirical gate is the real descendant outcome
required by issue #57. Do not infer that evidence from stars, comments, issue
volume, or the controller's own activity score.

## Canonical context

Read this file as the current-state entrypoint, then use the deeper canonical
sources as needed:

- [EVOLUTION.md](EVOLUTION.md) — evolution/evidence philosophy and boundaries;
- [ROADMAP.md](ROADMAP.md) — evidence-gated project priorities;
- [ITERATION_MODEL.md](ITERATION_MODEL.md) — iterative model and safety boundaries;
- [MATHEMATICAL_FOUNDATIONS.md](MATHEMATICAL_FOUNDATIONS.md) — mathematical
  foundations and assumptions;
- [PROJECT_RULES.md](PROJECT_RULES.md) — community, preservation, compute, and
  decision discipline.

## Update procedure

Refresh this report when a material `main` merge changes an evolution mechanism,
an active evidence gate opens/closes, or durable evidence changes the identified
bottleneck.

For each refresh:

1. verify issue/PR state against current GitHub rather than copying an old report;
2. record the date and the pre-update `main` baseline used for the audit;
3. distinguish implemented, synthetic/test, observed, and accepted/independent
   evidence;
4. keep only genuinely open gates in the active-gates section;
5. do not embed volatile posterior values unless an exact workflow run/artifact is
   named;
6. identify one weakest evidence-backed bottleneck and one bounded next decision;
7. run the repository test suite and deterministic Markdown link gate before
   integration.

The generated persistent Bayesian report and live observatory report are runtime
evidence. They must not overwrite or redefine this authored current-state index.
