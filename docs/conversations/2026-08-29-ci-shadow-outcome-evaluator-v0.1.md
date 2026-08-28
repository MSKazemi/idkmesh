# CI shadow outcome evaluator v0.1 — 2026-08-29

## Owner direction

Continue improving the repository's CI and algorithmic self-improvement while respecting all branch-to-main merge rules and good practices. The broader goal is a useful entity that learns from actions and iterations rather than merely accumulating ideas.

## Implemented interpretation

The existing shadow planner could recommend checks but could not compare a recommendation with what the full CI baseline actually observed. This turn adds that missing evidence join without granting automation authority.

For one immutable head SHA, the evaluator:

1. normalizes GitHub check runs and their workflow identities;
2. verifies the plan, planning receipt, policy digest, and head binding;
3. maps observed failures to planner check identities using reviewed policy;
4. records covered failures, missed mapped failures, and unattributed failures;
5. reports modeled planner savings separately from measured compute;
6. remains categorically unable to execute, skip, approve, merge, or write.

The full `PR Gate` continues to run and remains the required branch-protection baseline. A trusted-default-branch `workflow_run` observes its completed exact head with read-only permissions.

## Decision and limitations

One observation is not learning and cannot promote selective CI. Version 0.1 always emits `promotion.eligible = false`. A later reviewed cohort must include 50–100 representative observations, failure cases, measured runtime and cancellation data, stable attribution, randomized audits, and delayed regression evidence. Unknown mappings are surfaced as attribution gaps instead of being guessed away.

## Community impact

Contributors get a readable, reproducible explanation of what the planner predicted and what CI found. The design keeps protected checks unchanged and makes uncertainty visible, so community compute can eventually be allocated more intelligently without weakening review safety.
