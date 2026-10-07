# 2026-10-07 — C14-A GitHub Actions run summary

## Owner request

Work on one issue in the current IDKMesh repository.

## Repository selection

The repository was refreshed at `main` revision
`7ac46d39ba629fce7dafc4b25c69cbcee5c1f03e`. Open issues, open pull requests,
recent merged work, `AGENTS.md`, `PROJECT_RULES.md`, `ROADMAP.md`, and the canonical
product slice map were inspected before selecting work.

Active pull requests already cover #921/#737, #478, #607 C12-A, #578, #608 C13-A,
#596 C8-B, and #742, so those paths were excluded. Human-only onboarding/review
evidence issues and live provider smoke tests that require credentials or an external
endpoint were also excluded rather than fabricating evidence.

The selected bounded slice is **C14-A — Actions job/step summary renderer** from
issue #609. No open pull request was found for #609 or C14-A.

## Implementation

Add a pure `idkmesh.github_actions_summary` renderer for a canonical Product Spine
run. The renderer returns bounded Markdown suitable for `GITHUB_STEP_SUMMARY` but
performs no filesystem, network, GitHub, verification, decision, push, or merge
mutation.

Optional presentation detail is accepted only when it binds back to retained
canonical evidence:

- a CandidateReference must hash to the attempt's retained candidate-reference digest;
- a Run Evidence Report must hash to the run's retained evidence-report digest and
  match the run/WorkUnit identity.

The summary exposes run/WorkUnit state, exact source revision, attempt states,
provider-neutral candidate/result/verification evidence, verifier checks when a bound
report is supplied, human-decision status, a GitHub-hosted durable evidence link when
available, and the explicit blocked-authority boundary.

Focused tests cover deterministic rendering, exact digest binding, unsafe/mismatched
input rejection, Markdown/HTML escaping, GitHub-only durable links, and the truthful
early-run case with no optional evidence.

## Verification

Local syntax validation was run with:

```text
python -m py_compile /tmp/github_actions_summary.py /tmp/test_github_actions_summary.py
```

The isolated execution environment does not contain a checkout of the repository and
cannot directly resolve GitHub, so the full repository pytest/testkit gate is delegated
to the protected pull-request CI after the atomic candidate commit is published. Exact
head check results must be reviewed before integration.

## Community impact

This slice makes one run understable from the normal GitHub Actions interface
without requiring a newcomer to inspect raw provider JSON. It adds no new authority and
does not change canonical evidence formats.

## Follow-up boundary

C14-B through C14-H remain separate work. In particular, this slice does not publish or
update issue/PR comments, create durable evidence storage, generate Pages, publish a
release, or create attestations.
