# Open-issue continuation — Phase B2 Task 002 evidence

**Date:** 2026-08-29
**Primary issue:** [#5](https://github.com/MSKazemi/idkmesh/issues/5)

## Project-owner request

> Go ahead and work on the issues.

The repository instructions supplied with the request required current-issue
inspection, bounded pull requests, exact-diff review, green current-head
evidence, and a fresh `main` snapshot after every integration.

## Interpretation and actions

The live tracker and open pull requests were inspected before changing files.
Issue #152 was not used as a machine-work target because its remaining gate is
genuinely independent human review under #167. While PR #310 was being checked,
it merged externally; the workspace was refreshed to canonical `main` at
`90e5cb8` rather than continuing on its stale source branch.

The next bounded issue #5 slice is frozen Phase B2 Task 002:

- reconstruct the already-canonical one-file candidate against exact source
  `9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2`;
- package it as ResultManifest v0.1;
- run the frozen public EvaluatorPlan v0.3 metadata verifier;
- retain behavioral evidence that a frozen cohort without
  `definition_digest` fails for that field;
- seed a weakened-schema regression inside the isolated verifier checkout and
  require the new self-test to reject it with a diagnostic;
- attach evidence without changing the frozen cohort definition digest.

The plan was posted publicly on issue #5 before implementation.

## Authority boundary

The worker harness operates on an isolated checkout. Candidate code is not
executed by the metadata verifier. The weakened-validator probe runs only in a
separate subprocess and does not alter the frozen schema or candidate patch.
The harness grants no canonical write, push, merge, or automatic-selection
authority.

## Community impact

The replay test and retained diagnostics let another contributor reproduce the
Task 002 result without relying on this chat or on a transient CI artifact.
