# Canonical run-state to GitHub labels (C13-E, v0.1)

**Issue:** [#608](https://github.com/MSKazemi/idkmesh/issues/608).
**Status:** read-only offline planning only; no GitHub writes or Projects API sync.

The pure `plan_github_run_labels()` function accepts a trusted canonical Product Spine run ID, state, source SHA-256 digest, and existing GitHub labels. It produces an idempotent add/remove plan with a no-op flag. It never grants dispatch, verification, human approval, integration or merge authority.

## Ownership boundaries

Only `idkmesh:work:`, `idkmesh:verify:`, and `idkmesh:human:` labels are managed by this projection. Ordinary issue labels and connector routing labels (`idkmesh:route:`, `idkmesh:risk:`, etc.) are retained unchanged. A stale or malicious manually assigned managed label is replaced from the trusted run snapshot, never interpreted as authority.

| Canonical run state | Work label | Verification label | Human label |
| --- | --- | --- | --- |
| proposed, previewed | proposal | not-started | unrecorded |
| admission_blocked | admission-blocked | not-started | unrecorded |
| admitted | dispatch-admitted | not-started | unrecorded |
| dispatched | dispatched | not-started | unrecorded |
| attempt_failed | attempt-failed | not-started | unrecorded |
| candidate_observed | candidate-observed | not-started | unrecorded |
| normalized | candidate-normalized | not-started | unrecorded |
| verification_requested | verification-pending | pending | unrecorded |
| verification_error | verification-error | error | unrecorded |
| evidence_ready | evidence-ready | evidence-ready | unrecorded |
| awaiting_human_decision | human-decision-pending | evidence-ready | pending |
| decided | human-decision-recorded | evidence-ready | recorded |
| cancelled | cancelled | unknown | unknown |

The `decided` state only says a human decision is **recorded**, not that the candidate was accepted. The `evidence_ready` state is not a claim of successful verification.

## Example

```python
from idkmesh.github_run_label_projection import plan_github_run_labels

plan = plan_github_run_labels(
    run_id="run/example-123",
    run_state="candidate_observed",
    canonical_source_digest="sha256:" + "a" * 64,
    expected_source_digest="sha256:" + "a" * 64,
    existing_labels=("bug", "idkmesh:route:blocked", "idkmesh:work:proposal"),
)
print(plan.to_dict())
```

The example digest is synthetic and establishes **no evidence** for a real run. The caller must verify the run state and digest from the trusted ledger/store, bind the intended repository/issue, and re-read the canonical source and expected revision before any future GitHub API write. This planner does none of those checks against a live system. Missing GitHub/Projects permissions must never block WorkUnit execution.

The planner rejects unsupported states, invalid IDs or digests, stale expected digests, duplicate case-insensitive labels, malformed labels, and over 1,000 existing labels. Output is deterministic regardless of input ordering; complexity is `O(L log L)` for up to 1,000 labels. Repeat planning against `target_labels` yields `noop=True`.

## Verification and remaining work

Run `python -m pytest -q tests/test_github_run_label_projection.py tests/test_github_routing_projection.py`. This is C13-E **planning groundwork**, not a finished C13-E publication adapter or C13-G synchronization. A future writer requires source-digest freshness checks, destination authorization, concurrency recovery, and idempotent GitHub API operations. See [Projects synchronization](GITHUB_PROJECTS_SYNC_V0_1.md).
