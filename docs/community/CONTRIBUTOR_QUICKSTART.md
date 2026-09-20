# Contributor Quickstart

IDKMesh needs external contributors more than it needs more owner-authored activity.

You do **not** need to understand the whole architecture before helping. Pick one
bounded task, make the smallest useful contribution you can, and let the review
process teach you the rest.

## Choose a first contribution

### 20-45 minutes: newcomer usability

- [#542 — walk the newcomer path and record where it breaks](https://github.com/MSKazemi/idkmesh/issues/542)
- [#403 — first-run report: what confused you?](https://github.com/MSKazemi/idkmesh/issues/403)

These require no code. Honest confusion is useful project evidence.

### 30-60 minutes: Python testing

- [#540 — add a smoke test that every argparse tool supports `--help`](https://github.com/MSKazemi/idkmesh/issues/540)

This is a focused Python/subprocess test with a clear pass/fail condition.

### 45-90 minutes: research / reproducibility

- [#541 — independently verify the benchmark publication counts](https://github.com/MSKazemi/idkmesh/issues/541)

This checks published numbers against raw committed cohort data.

### External-machine testing

- [#401 — install `gate-audit` and report setup/test results](https://github.com/MSKazemi/idkmesh/issues/401)

Windows, macOS, and non-Ubuntu Linux evidence is especially useful.

### Deeper independent review

- [#167 — independently review the IDKGraph orphan cohort](https://github.com/MSKazemi/idkmesh/issues/167)

This is a larger evidence/review task rather than a coding task.

## Before you start

1. Read [CONTRIBUTING.md](../../CONTRIBUTING.md).
2. Open the issue and check assignees, comments, and linked pull requests.
3. Comment with the bounded piece you intend to do.
4. Keep the first pull request small.
5. Report the exact commands you actually ran.
6. If AI helped, say what tool/model was used when known and what you personally verified.

A failed reproduction, confusing setup, or negative result can be useful if it is
clear and reproducible.

## What maintainers should optimize for

The immediate community goal is not raw issue count, PR count, stars, or
AI-generated activity. It is:

```text
first external contribution
        ->
useful review
        ->
second contribution
        ->
recurring contributor
        ->
reviewer / steward
```

The repository should therefore keep several live newcomer tasks across
different contribution styles and refresh links when tasks close. The norms behind this funnel are documented in [Contributor Experience Guidelines](CONTRIBUTOR_EXPERIENCE.md): real choice of task, an early winnable task, a visible review path, visible progress, real recognition, and one skill-matched next step after a verified contribution.

## Where to go next

- [Starter task catalog](STARTER_TASKS.md)
- [Contributor pilot](CONTRIBUTOR_PILOT_2026_09.md)
- [Community growth strategy](COMMUNITY_GROWTH_STRATEGY.md)
- [Open good first issues](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22good+first+issue%22)
- [Open help wanted issues](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22help+wanted%22)
- [Co-maintainer / bring-your-own-agent invitation](https://github.com/MSKazemi/idkmesh/issues/407)
