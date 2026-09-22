# IDKMesh Run Evidence Report

- **Run:** `two-attempt-evaluator-plan-good-vs-bad`
- **Work Unit:** `verification/patch-smoke` v1
- **Source run digest:** `sha256:41ecefda10fe809fcec0acbb0d39d39d4044f26b127eb83e64d1a8c94a3bec3d`
- **Supported attempts:** 1
- **Rejected attempts:** 1
- **Inconclusive attempts:** 0
- **Control errors:** 0
- **Verification disagreement:** yes
- **Human integration decision:** **pending**

## Attempts

| Attempt | Worker state | Worker | Verifier | Recommendation | Evidence state | Required checks |
| --- | --- | --- | --- | --- | --- | --- |
| attempt-001 | verified | fixture/patch-worker | idkmesh-local-verifier | accept_candidate | supported | result-manifest-schema=passed, independent-review=passed |
| attempt-002 | verified | fixture/patch-worker | idkmesh-local-verifier | reject_candidate | rejected | result-manifest-schema=passed, independent-review=failed |

## Warnings

- Generated evidence is decision support only; this report does not select, accept, merge, or integrate a candidate.
- Independent verification recommendations disagree; preserve the disagreement for human/governance review.

## Authority boundary

This generated report is a read-only aggregation of worker and verifier evidence. 
It deliberately contains **no selected candidate** and cannot approve, merge, push, or modify canonical project state.
