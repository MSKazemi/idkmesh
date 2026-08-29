# R1 real-corpus readiness gate

**Date:** 2026-08-29

**Related:** issues 30 and 70

## User requirement

Take an unclaimed issue from the parallel issue stream, implement the highest-value
remaining step professionally, preserve evidence boundaries, push a focused
non-draft pull request, and do not merge it from the worker stream.

## Live-state and artifact audit

Issue 30 was open and unassigned, with no competing open pull request or matching
remote branch. The issue was publicly claimed before implementation. The merged R1
surface already contained the six-condition synthetic harness, the help/hurt sweep,
and the real-result replay adapter.

Issue 70 remained open and still required at least 20 eligible held-out coding work
units. The repository's current successor-v2 BenchmarkCohort was only a five-task
pilot scaffold with pending evidence. Recent real Task 001 artifacts were calibration
and infrastructure evidence, not a multi-signature held-out R1 corpus.

## Decision

The replay analysis remains unchanged. A separate, fail-closed readiness audit now
joins the existing BenchmarkCohort validation to the replay's exact normalization.
This prevents a pilot, a selectively retained candidate pool, or a renamed structural
signature from silently being reported as the first real R1 result.

The gate also requires every verified or attempt-bearing task to be eligible. An
extra analyzed pilot cannot be hidden behind 20 eligible tasks because the unchanged
replay would consume all 21.

For the preregistered two-candidate comparison, readiness requires an exact retained
pool of two baseline attempts and one second-signature attempt per work unit. The
frozen replay then compares `A + A` with `A + B`, preserving equal selected-candidate
budgets. Every attached attempt must remain conclusive, independently tested,
cost-accounted, and signature-consistent.

The cohort definition digest intentionally excludes evidence/attempts. Exact attached
counts therefore cannot prove no generated candidate was omitted; prospective attempt
commitments and collection provenance remain mandatory human-review evidence.

## Deterministic evidence

The unit fixture uses 20 explicitly synthetic contract tasks and proves both the
passing contract shape and fail-closed behavior for:

- a five-task pending pilot scaffold;
- post-outcome signature drift;
- missing compute accounting;
- unequal diversity-arm configuration.

The committed current repository-state audit reports `blocked` and zero eligible
work units. Its evidence class is `repository_contract_state_not_coding_outcome`,
and `supports_empirical_r1_claim` is false.

## Authority and interpretation boundary

The audit reads committed contracts and emits a report. It cannot select candidates,
write canonical state, push, or merge. A passing mechanical audit would still require
human review of temporal freeze and held-out provenance, followed by the unchanged
replay. This work therefore advances issue 30 but does not close it while issue 70's
real-corpus gate remains unmet.

## AI/tool provenance

Codex performed the repository/live-state audit and implemented the bounded tooling,
tests, documentation, workflow reproduction check, and conversation record. No
synthetic fixture or calibration artifact was relabeled as real coding evidence.
