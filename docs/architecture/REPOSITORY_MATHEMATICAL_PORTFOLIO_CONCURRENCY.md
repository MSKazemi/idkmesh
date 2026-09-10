# Repository Mathematical Portfolio Concurrency

**Status:** implemented invariant  
**Introduced:** 2026-09-10  
**Scope:** `.github/workflows/repository-math-portfolio.yml`

## Purpose

The Repository Mathematical Portfolio mixes two classes of observation in one workflow:

1. **advisory pull-request metadata observations** triggered by `pull_request_target`; and
2. **canonical persistent-state observations** triggered by trusted repository events such as `push`, `issues`, `workflow_dispatch`, and `schedule`.

Those classes must not share one cancellation domain.

A global `cancel-in-progress: true` group lets a new pull-request observation cancel a running observation for an unrelated pull request. GitHub renders that cancellation as a failed/red check even when no step failed. This is the same failure class measured for the Evolution Loop in issue #387.

At the same time, canonical portfolio state is artifact-backed and intentionally linear. Canonical runs restore the latest eligible trusted checkpoint and produce its successor; allowing independent canonical concurrency groups could permit two runs to restore the same parent and publish competing successors.

## Invariant

The `portfolio` job therefore uses an event-sensitive concurrency key:

<!-- The expression below is GitHub Actions syntax, not Liquid. Jekyll expands
     Liquid variable and tag delimiters before Markdown runs, so a code fence does
     not protect them; unwrapped, this block fails the Pages build for the whole
     site. Keep the raw wrapper, and do not write Liquid delimiters in this
     comment either -- Liquid parses HTML comments too. -->
{% raw %}
```yaml
concurrency:
  group: repository-math-portfolio-${{ github.event_name == 'pull_request_target' && format('advisory-{0}', github.event.pull_request.number) || 'canonical' }}
  cancel-in-progress: true
```
{% endraw %}

Semantics:

```text
pull_request_target for PR #A -> repository-math-portfolio-advisory-A
pull_request_target for PR #B -> repository-math-portfolio-advisory-B
canonical event             -> repository-math-portfolio-canonical
```

This means:

- a newer observation for the **same PR** may supersede an older one;
- observations for **different PRs** cannot cancel each other;
- all canonical events remain in one cancellation lineage;
- the existing trusted-parent selection rules remain unchanged.

## Trust boundary

Concurrency isolation does **not** make advisory artifacts canonical.

Trusted portfolio parent lookup continues to admit only successful allowlisted canonical events:

```text
issues
push
workflow_dispatch
schedule
```

`pull_request_target` remains excluded from trusted future-state selection. The workflow still checks out the trusted default branch for the privileged metadata observation and retains read-only permissions.

The separate `verify-pr-head` job continues to run on ordinary `pull_request`, with its own per-PR concurrency key and `contents: read` permission.

## Regression coverage

`tests/test_evolution_observer_concurrency.py` enforces four properties:

1. advisory portfolio concurrency is keyed by pull-request number;
2. canonical portfolio concurrency has no per-run key;
3. trusted parent selection does not admit `pull_request_target`;
4. the portfolio observer is no longer allowed in the repository-wide known-unkeyed-cancelling exception set.

The repository-wide scan intentionally permits an unkeyed group only when it is explicitly recorded and understood. New unkeyed cancelling groups fail the test instead of silently expanding the exception surface.

## Non-goals

This change does not alter:

- portfolio scoring, Pareto ranking, UCB behavior, or mathematical policy;
- checkpoint schema or artifact contents;
- workflow permissions;
- branch, issue, PR, review, or merge authority;
- which event classes are trusted as persistent-state parents.

It is a CI correctness and persistent-state serialization fix, not a change to portfolio semantics.

## Related

- issue #413 — portfolio advisory concurrency follow-up;
- issue #387 — measured cross-PR cancellation failure class;
- PR #389 — Evolution Loop fix that established the reviewed advisory/canonical pattern;
- `docs/architecture/REPOSITORY_MATHEMATICAL_PORTFOLIO.md` — portfolio architecture and trust model.
