# ChatGPT scheduled quality worker

IDKMesh has an external ChatGPT scheduled worker for bounded repository maintenance
and implementation work. It is an **implementation worker**, not a verifier,
reviewer, merge authority, or replacement for the Jules dispatcher.

## Schedule

The intended cadence recorded on 2026-09-22 was **once every hour**. The
external scheduler is the source of truth for its current configuration and
actual runs; this repository does not verify that cadence.

The scheduler is external to GitHub. This document records the repository-facing
contract; it does not make GitHub Actions responsible for starting the worker.

## Operating loop

Every run must treat current repository state as evidence rather than relying on
memory:

1. refresh current `main` and note the exact base revision;
2. read `AGENTS.md`, `CONTRIBUTING.md`, `PROJECT_RULES.md`, and task-specific rules/specifications;
3. inspect open issues, pull requests, relevant branches, CI, and review state;
4. continue unfinished, failing, or review-blocked scheduled-worker work before starting something new;
5. otherwise choose one bounded, implementation-ready issue;
6. create or reuse a dedicated `chatgpt/` branch from current `main`;
7. implement the smallest correct change with focused tests and documentation;
8. open or update a **Draft** pull request;
9. use CI/review feedback to repair the exact candidate on later runs.

Worker completion is never treated as acceptance.

### Rollout compatibility

The first two ChatGPT-created pull requests predate the `chatgpt/` branch-prefix rule:

- #639 used `ci/reduce-pr-fanout-2026-09-22` and has merged;
- #640 uses `docs/chatgpt-hourly-quality-worker`.

While #640 remains open, the worker treats it as scheduled-worker work and converges it before opening fresh work when an actionable repair exists. This is a temporary compatibility rule, not permission to create additional branches outside `chatgpt/`.

## Non-overlap with Jules

The scheduled ChatGPT lane must not compete with the repository-operated Jules
dispatcher.

It therefore does **not** take issues carrying any Jules execution or queue label:

- `agent-ready`;
- `agent:jules-eligible`;
- `agent:jules-dispatched`;
- `agent:jules-needs-attention`;
- `jules` (legacy manual fallback).

It also fails closed on the Jules hard-veto classes:

- `blocked`;
- `do-not-automate`;
- `human-required`;
- `needs-decomposition`;
- `research-evidence`;
- `security-sensitive`.

This keeps the Jules single-dispatcher invariant intact and prevents two agents
from independently starting the same queued task.

## Task eligibility

A task is suitable only when it is bounded, reviewable, and meaningfully
testable by normal repository checks.

The scheduled worker must skip work that requires:

- genuine human observation or human-only evidence;
- independent research conclusions or real-world evidence collection;
- external-machine testing;
- secrets or credential setup;
- security approval;
- governance judgment;
- broad architecture redesign;
- authority outside normal contributor permissions;
- work already covered by an active overlapping pull request.

When eligibility is unclear, the worker should fail closed rather than infer
permission from arbitrary issue prose.

## Quality and verification

The worker follows the repository's normal contribution rules:

- use `pytest` as the canonical runner; never use `unittest discover` for repository test execution;
- use focused tests or `make smoke` while iterating when local execution exists;
- use `make gate` and `make integration` as appropriate for the final diff;
- never claim a command ran when execution was unavailable;
- preserve trust, provenance, verification, and authority boundaries;
- avoid unnecessary dependencies;
- add deterministic regression tests for testable behavior;
- update public documentation when commands or interfaces change;
- state exact checks, results, risks, limitations, Community Impact, and AI/tool
  provenance in the pull request.

If local execution is unavailable, the worker may still prepare a Draft PR and
must use GitHub CI as evidence for the exact candidate, repairing failures on
later scheduled runs without weakening checks.

## Review backpressure

High frequency must not become high review load.

The lane is bounded to:

- at most **two open implementation PRs** created by this scheduled worker at a
  time;
- at most **one new implementation PR per hourly run**;
- preference for repairing existing PRs before starting a new task;
- no synthetic churn when no safe bounded task is available.

The objective is **verified useful progress per unit of reviewer attention**,
not commit, branch, issue, or pull-request count.

## Authority boundary

The worker must never:

- push directly to `main`;
- self-approve or auto-merge;
- bypass required checks;
- weaken tests or verification to make a candidate pass;
- expose credentials or secrets;
- delete protected branches;
- apply Jules execution labels;
- represent its output as independent human or external-agent review.

The protected integration and human/reviewer decision path remains unchanged.

## Failure/recovery behavior

On each hourly run, repair existing scheduled-worker work before creating new
work:

1. failing CI -> inspect the exact failure and make a bounded repair;
2. actionable review feedback -> address or explain it on the same PR;
3. stale base or overlapping implementation -> re-evaluate and avoid duplicate work;
4. queued/pending CI with no actionable failure -> do not invent a repair;
5. no safe task -> make no repository change and report the blocker rather than
   manufacture activity.

This lane complements, rather than replaces, the event-driven Jules automation
documented in [JULES_AUTOMATION.md](JULES_AUTOMATION.md).
