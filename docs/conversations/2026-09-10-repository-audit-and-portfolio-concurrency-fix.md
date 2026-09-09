# Repository audit and Portfolio concurrency fix — 2026-09-10

## Owner request

The repository owner asked ChatGPT to inspect `MSKazemi/idkmesh`, identify one of the most important improvements that could be implemented to an enterprise-quality standard, update documentation, and create or implement a well-scoped issue where justified.

## Audit approach

The audit reviewed current repository guidance, the protected `main` branch state, open issues, recent pull requests, workflow structure, tests, and architecture documentation. The review intentionally avoided duplicating active or already-merged work.

One initially high-impact candidate was issue #387, which documented false-red Evolution Loop checks caused by a global cancelling concurrency group. That issue's implementation had already landed in PR #389, so duplicating it would have added review load without value.

The merged #389 regression test explicitly recorded a second occurrence of the same failure class in `.github/workflows/repository-math-portfolio.yml`. Unlike the remaining `collaboration-observables.yml` exception, the Portfolio workflow runs on `pull_request_target` and therefore can create misleading cross-PR cancellations.

## Finding

Before this change, the Portfolio `portfolio` job used:

```yaml
concurrency:
  group: repository-math-portfolio-observer
  cancel-in-progress: true
```

That group covered both advisory `pull_request_target` observations and canonical checkpoint-producing events.

The consequences were asymmetric:

- unrelated pull requests could cancel each other's advisory observations, producing a red/cancelled status unrelated to the candidate's correctness;
- simply keying every run independently would be unsafe for canonical persistent state because two canonical observers could restore the same checkpoint and publish competing successor lineages.

## Decision

Create issue #413 and implement an event-sensitive concurrency key:

```text
pull_request_target -> advisory-<pull request number>
all canonical events -> canonical
```

Keep `cancel-in-progress: true` so newer observations may supersede older observations within the same logical stream.

The trusted parent-selection allowlist remains unchanged: only `issues`, `push`, `workflow_dispatch`, and `schedule` runs can become persistent portfolio parents. `pull_request_target` remains advisory evidence only.

## Implementation

Branch: `fix/portfolio-advisory-concurrency`

Changes:

1. `.github/workflows/repository-math-portfolio.yml`
   - isolates advisory PR-target concurrency by PR number;
   - preserves one canonical concurrency lineage;
   - does not change permissions, scoring, artifact format, or trust rules.
2. `tests/test_evolution_observer_concurrency.py`
   - removes Portfolio from the known-unfixed exception set;
   - adds focused assertions for advisory isolation, canonical single-lineage behavior, and trusted-parent event exclusion;
   - keeps the repository-wide guard against new unkeyed cancelling groups.
3. `docs/architecture/REPOSITORY_MATHEMATICAL_PORTFOLIO_CONCURRENCY.md`
   - records the concurrency and trust-boundary contract for future maintainers.

## Community impact

This reduces misleading CI failures and manual reruns for contributors. It also converts an implicit workflow assumption into an executable and documented invariant, lowering the chance that a later refactor reintroduces cross-PR cancellation or accidentally forks canonical checkpoint state.

## AI/tool provenance

The audit and implementation were performed with ChatGPT using the repository owner's authorized GitHub connector. Important repository claims were checked against current GitHub files/issues/PR metadata rather than inferred from stale conversation context. Normal repository CI remains the independent verification surface for the candidate branch.

## Open questions

- The remaining explicitly known unkeyed cancelling group in `collaboration-observables.yml` is dispatch/schedule-only and does not affect pull requests. It can be evaluated separately if operational evidence shows that scheduled/manual cancellation is undesirable.
- The Portfolio architecture's main document may later absorb the new concurrency note; the focused document keeps this PR bounded while still preserving the invariant publicly.
