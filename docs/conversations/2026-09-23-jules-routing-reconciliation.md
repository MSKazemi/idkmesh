# Jules automatic-routing reconciliation and throughput hardening — 2026-09-23

## Owner requirements

The project owner asked to continue hardening the Google Jules integration so IDKMesh can develop quickly, automatically route simple coding work, and keep the complete operating model documented in the repository.

## Repository findings

Current `main` already contained an API-backed Jules dispatcher, but the live router/dispatcher contracts had diverged after later repairs:

1. `.github/workflows/issue-model-router.yml` emitted `agent:jules-eligible` and invoked `jules-dispatch.yml` with a `workflow_dispatch` input named `issue_number`.
2. `.github/workflows/jules-dispatch.yml` no longer declared that input.
3. `config/jules-dispatch.json` accepted only `agent-ready`, so the router's automatic eligibility label no longer entered the dispatcher queue.
4. routine dispatch had also reintroduced label bootstrapping and repeated per-label GitHub issue-list calls, despite earlier live rate-limit evidence.
5. issue #753 demonstrated successful REST session creation but remained `QUEUED` without a PR for hours; the repository had no automatic stale/failed-session reconciliation.

These failures explain why a connected Jules installation can still appear idle even when the provider credential and REST session creation work.

## Durable design

IDKMesh now distinguishes two execution ingress paths:

- **automatic route:** `agent:jules-eligible`, emitted by the deterministic Issue Model Router, accepted by the dispatcher only for GitHub author associations `OWNER`, `MEMBER`, or `COLLABORATOR`;
- **manual route:** `agent-ready`, explicitly applied by a maintainer/trusted triager.

Both routes remain subject to the same hard-veto labels, capacity controls, duplicate-session protection, normal CI, and no-auto-merge rule.

The router-to-dispatcher handoff now uses a local reusable workflow through typed `workflow_call.issue_number`. This avoids relying on recursive `GITHUB_TOKEN` events and lets GitHub validate the caller/callee input contract before execution. A stdlib-only `tools/check_jules_contract.py` guard is also part of the required PR Gate so label-policy drift, missing reusable inputs, or privilege expansion becomes a merge-blocking failure.

## Provider-session reconciliation

The Jules API documents these session states:

- `QUEUED`
- `PLANNING`
- `AWAITING_PLAN_APPROVAL`
- `AWAITING_USER_FEEDBACK`
- `IN_PROGRESS`
- `PAUSED`
- `FAILED`
- `COMPLETED`

References:

- https://jules.google/docs/api/reference/sessions/
- https://jules.google/docs/api/reference/types/

The repository policy adds `agent:jules-needs-attention`. Reconciliation adds that blocking label and removes `agent:jules-dispatched` when a session:

- enters a failed/paused/user-attention state;
- cannot be matched after the configured grace period;
- remains `QUEUED`, `PLANNING`, or `IN_PROGRESS` beyond the configured no-update threshold.

The blocking label is added before the active reservation is removed, so the issue cannot become automatically redispatchable during the transition. Reconciliation never creates a replacement provider session.

Current initial thresholds are:

- missing session: 60 minutes;
- QUEUED: 120 minutes;
- PLANNING: 180 minutes;
- IN_PROGRESS: 360 minutes.

These are operational defaults to measure and revise, not claims about normal Jules service latency.

## Throughput and API-pressure decisions

The repository-side concurrency cap remains four active Jules issues, with at most two new dispatches in a recovery sweep.

For lower API pressure and faster batches:

- one GitHub open-issue snapshot feeds active-capacity and queue selection;
- one Jules session-list snapshot feeds reconciliation and duplicate detection;
- session identity uses a stable repository+issue-number marker, so later issue-title edits do not lose or duplicate provider work;
- the provider history scan covers up to 10 pages of 100 sessions and fails closed if pagination is still incomplete;
- label bootstrapping is removed from normal hot-path events and runs only after relevant policy/implementation changes land or when explicitly requested;
- GitHub API quota exhaustion defers safely to a later recovery sweep instead of creating new provider work.

Completed Jules work continues to occupy its issue slot until the issue closes, preserving review backpressure. Failed/stalled work is quarantined and frees its slot so unrelated bounded work can continue.

## Implementation artifacts

Tracked under issue #768:

- `config/jules-dispatch.json`
- `tools/jules_dispatcher.py`
- `.github/workflows/jules-dispatch.yml`
- `tests/test_jules_dispatcher.py`
- `docs/operations/JULES_AUTOMATION.md`
- `AGENTS.md`
- `CONTRIBUTING.md`
- `docs/README.md`

## Verification boundary

The local execution container could not resolve `github.com`, so it could not clone the branch for local pytest execution. The implementation therefore must be validated by the normal IDKMesh pull-request gate on the exact branch head before integration.

The Jules REST API remains an external alpha contract. Provider behavior is observed evidence, not repository authority. Jules output never self-verifies and no dispatcher path merges to `main`.


## Regression-prevention contract

The durable fix is intentionally stronger than repairing the current workflow
pair:

- the Issue Model Router calls `.github/workflows/jules-dispatch.yml` as a
  repository-local reusable workflow instead of shelling out to
  `gh workflow run`;
- the dispatcher exposes `issue_number` through both `workflow_call` and
  operator-facing `workflow_dispatch`;
- the router derives the Jules queue label from routing policy, while the
  router workflow derives the managed automatic label from
  `config/jules-dispatch.json`;
- `tools/check_jules_contract.py` cross-checks routing policy, dispatcher
  policy, reusable-workflow inputs, trust labels, authority limits, and the
  AUTO_CREATE_PR provider contract;
- the unfiltered required PR Gate runs that guard before installing
  dependencies, so future changes cannot silently merge a disconnected
  router/dispatcher pair.

This specifically prevents the failure mode where one PR removes the
`issue_number` input or stops accepting `agent:jules-eligible` while the
other side continues assuming those contracts exist.
