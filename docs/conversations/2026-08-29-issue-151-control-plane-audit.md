# Issue #151 control-plane audit and hardening

Date: 2026-08-29

## Request

Select another inactive, unclaimed issue, solve it professionally, integrate the
result, and close the issue only when its acceptance criteria are genuinely met.

## Selection

Issue #151 was unassigned, had no active linked pull request, and explicitly asked
for an independent audit of the converged mathematical evolution control plane.
The implementation agent claimed it publicly, then assigned a separate read-only
audit agent to inspect current-main behavior before any closure decision.

## Independent findings

The audit confirmed the read-only authority boundary and hard mathematical guards,
but found an ordinary-PR artifact provenance collision, JSON-only checkpoint
validation, silent seed fallback after selected-checkpoint failures, stale review
evidence, an over-broad review-event trigger, and one artifact-retention
documentation contradiction.

## Decision and changes

All findings were treated as blockers rather than deferred:

- allowlist trusted workflow event provenance and require exact unexpired artifacts;
- bind checkpoint repository/workflow/run/head/event/parent and file hashes in manifests;
- fail closed after checkpoint selection;
- validate Bayesian, ledger, and portfolio state semantically;
- count review evidence only on the exact current PR head using the latest
  substantive state per non-author, non-bot reviewer;
- remove the checkpoint-producing `pull_request_review` trigger;
- align portfolio retention documentation with raw-body minimization;
- add focused security, integrity, semantic, and review regression tests.

The audit is preserved canonically in
`docs/audits/2026-08-29-evolution-control-plane-independent-audit.md`.

## Integration rule

The branch must be refreshed against current `main`, reviewed at its exact head by
a reviewer separate from the authoring work, pass all required checks for that SHA,
and be squash-merged. Only then may issue #151 close.
