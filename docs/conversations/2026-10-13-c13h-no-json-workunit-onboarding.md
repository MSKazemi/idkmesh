# 2026-10-13: GitHub WorkUnit intake no-JSON onboarding (issue #608)

## Owner request

“Work on an issues and update the docs” in the IDKMesh repository.

## Inspection and overlap correction

Inspected current `main`, the repository rules, open issue #608 and concurrent PRs. C13-C/D parsing, policy composition and the `idkmesh work preview` CLI were already implemented on `main`; previous draft PR [#1084](https://github.com/MSKazemi/idkmesh/pull/1084) duplicated that implementation, so it was closed **without merge**. PR #1078 owns the separate GitHub Projects projection contract.

## Focused contribution — C13-H

Provide a real contributor walkthrough using the existing no-JSON GitHub form, synthetic saved REST issue snapshots and a narrowly scoped project policy. A committed offline integration test checks the actual CLI/service path, deterministic digest, limits on allowed paths, risk-floor behavior, malformed-form fallback, out-of-scope refusal, and the no-dispatch/no-mutation boundary.

## Documentation

Add the newcomer guide and example README. Cross-link the beginner guide, docs index, and intake specification without claiming automated GitHub access, execution, or external verification.

## Validation and limitations

The exact PR head must pass repository CI before integration. The sandbox is still gated by #804; Projects synchronization remains separately owned. All code and docs were AI-assisted and should be independently reviewed. A synthetic fixture is **not** a real external onboarding observation.

## Community impact

Contributors can see the complete form-to-preview path without creating JSON by hand or providing a token. Explicit fallback and refusal examples reduce the risk of mistaking untrusted issue text for execution authority.
