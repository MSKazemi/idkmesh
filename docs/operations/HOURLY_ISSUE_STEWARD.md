# Hourly Issue Steward

## Purpose

The Hourly Issue Steward is an automated maintenance loop for IDKmesh. Its goal is to improve the repository continuously without lowering engineering, scientific, architectural, or documentation standards.

The steward executes once per hour and handles **at most one issue per run**. The one-issue limit is intentional: it keeps each change reviewable, reduces interference between concurrent work, and makes validation evidence attributable to one bounded change.

## Per-run workflow

1. Inspect open issues and open pull requests.
2. Select one valuable, well-scoped issue that is not already being actively solved by another pull request.
3. Read the relevant code, tests, architecture, project rules, and documentation before editing.
4. Implement the change on a dedicated branch. Integrate it with existing modules and contracts rather than creating an isolated parallel mechanism.
5. Add or update deterministic tests and fixtures for changed behavior.
6. Run the applicable repository validation: focused tests plus the relevant full-suite, schema, self-test, CLI, lint, type, build, or workflow-equivalent checks that apply to the touched area.
7. Update documentation whenever behavior, interfaces, configuration, architecture, concepts, workflows, or user-visible usage change.
8. Review the exact diff for correctness, maintainability, security, backwards compatibility, duplication, naming, and consistency with the rest of IDKmesh.
9. Create or update a pull request that links the issue and records design, integration points, verification, documentation changes, risks, AI/tool provenance, and scientific rationale where relevant.
10. Merge only when current evidence for the exact head SHA satisfies the repository's merge-safety policy. Otherwise leave the pull request open with a precise status and do not weaken quality gates.
11. After a successful merge, close the linked issue when appropriate and re-read current `main` before the next run.

## Engineering quality gates

A change is not considered complete merely because it compiles or appears locally correct. The steward should prefer small, coherent changes with clear contracts and tests.

Before merge, the steward should verify, as applicable:

- behavior is covered by regression tests;
- public interfaces use appropriate type hints and existing naming conventions;
- deterministic experiments remain reproducible through explicit seeds and fixtures;
- new dependencies are avoided unless clearly justified;
- existing schemas, configuration, state formats, and CLI contracts are preserved or deliberately migrated;
- related modules are updated together when an interface changes;
- duplication and one-off parallel implementations are avoided;
- security and failure modes are considered;
- backwards compatibility is preserved unless the issue explicitly authorizes a breaking change;
- documentation and examples match the implementation;
- the PR remains focused on the selected issue.

The canonical repository instructions in `AGENTS.md`, `PROJECT_RULES.md`, `CONTRIBUTING.md`, workflow definitions, and `docs/planning/BRANCH_CONVERGENCE_POLICY.md` take precedence if they impose stricter requirements.

## Scientific and mathematical validity

IDKmesh intentionally draws on ideas from computer science, biology, economics, complex systems, optimization, and related fields. The steward must distinguish inspiration from validated claims.

For changes involving scientific, mathematical, biological, economic, or algorithmic assertions:

- use established formulations or clearly identify novel/experimental formulations;
- state assumptions and scope conditions;
- avoid presenting analogies as empirical facts;
- prefer reproducible simulations, tests, benchmarks, or derivations when the claim can be checked computationally;
- cite authoritative literature or primary sources in documentation when a design materially depends on an external scientific result;
- record uncertainty and limitations rather than inventing evidence;
- ensure implementation semantics actually match the documented model.

A scientifically interesting idea is not sufficient for merge by itself; it must also fit IDKmesh's architecture and have an observable, testable role in the system.

## Integration requirement

Every implementation should answer: **where does this change connect to the rest of IDKmesh?**

The steward should inspect neighboring modules, schemas, state/configuration, workflows, tests, and documentation before creating a new abstraction. If an issue would create a second source of truth or a disconnected subsystem, the preferred solution is to integrate with an existing contract or explicitly document why a new boundary is necessary.

## Merge safety

The steward follows the repository's branch-convergence rules. In particular:

- never bulk-merge stale branches;
- review the exact pull-request diff;
- use validation evidence for the current PR head SHA;
- do not bypass required checks, unresolved substantive review comments, or conflicts;
- prefer squash merge for ordinary bounded work when repository policy allows it;
- after every merge, refresh `main` and reassess subsequent work because prior eligibility may be stale.

If the branch is not mergeable with high confidence, the correct result of a run is a high-quality open PR with a precise explanation of what remains.

## Documentation rule

Documentation is part of the implementation, not a post-merge cleanup step. Update the relevant README, architecture, API, configuration, examples, decision records, or focused docs in the same PR whenever the implementation changes what contributors or users need to understand.

Pure internal refactors with no behavioral, interface, configuration, architectural, or conceptual impact may require no documentation change, but the PR should state why.

## Run report

Each run should summarize:

- selected issue;
- branch and pull request;
- important files changed;
- integration points touched;
- tests and validation executed;
- documentation updated (or why none was required);
- scientific evidence/assumptions, if applicable;
- merge status;
- remaining risks or blockers.

## Automation cadence

The external steward task is configured to run once per hour. Scheduling is intentionally outside repository CI so the repository remains portable and the maintenance policy can evolve independently of one automation provider.
