# Jules review-reservation lifecycle and development-speed hardening — 2026-09-24

## Owner request

Continue hardening the Google Jules + GitHub automation so IDKMesh can develop quickly while keeping the dispatch process solid, documented, and safe.

The owner previously asked for:

- automatic selection of simple coding issues for Jules;
- clear ownership of who labels, who dispatches, and who verifies;
- event-driven speed rather than slow polling;
- explicit documentation of the complete path.

## Repository state inspected

Current `main` already contains a substantially more mature Jules control plane than the original pilot:

- deterministic `agent:jules-eligible` routing for trusted low-risk issues;
- explicit manual `agent-ready` approval;
- REST API dispatch through the official Jules API;
- `AUTO_CREATE_PR`;
- provider-concurrency accounting;
- GitHub Actions backpressure;
- stale/missing/failed-session reconciliation;
- typed reusable-workflow handoff between Issue Model Router and Jules Dispatcher;
- `agent:jules-needs-attention` fail-closed quarantine.

Live queue inspection found six open Jules-eligible issues and four open
`agent:jules-dispatched` reservations.

## Throughput defect found

The repository review cap was still tied to the lifetime of the parent GitHub issue.

Examples observed on 2026-09-24:

- issue #652 produced Jules PR #790, which completed/merged, but the broader issue remained open with `agent:jules-dispatched`;
- issue #669 produced Jules PR #792, which completed/merged, but the broader issue remained open with `agent:jules-dispatched`;
- issue #577 produced Jules PR #803 but remains intentionally open for broader C4 work;
- waiting eligible issues included #580 and #677.

Because `max_in_flight=4` counts open dispatch reservations, long-running umbrella issues can pin review slots after the actual Jules candidate review has ended.

## Provider contract checked

The current official Jules REST API documents:

- `Session.outputs[]`;
- `SessionOutput.pullRequest`;
- `PullRequest.url`;
- Get Session returning the full completed Session including outputs.

References:

- https://jules.google/docs/api/reference/types/
- https://jules.google/docs/api/reference/sessions

## Durable decision

Repository review capacity should follow the **actual Jules candidate review lifecycle**, not the lifetime of an umbrella issue.

The lifecycle becomes:

```text
agent:jules-eligible / agent-ready
 -> agent:jules-dispatched
 -> provider work
 -> open Jules PR keeps repository review reservation
 -> PR closed/merged
 -> agent:jules-completed
```

`agent:jules-completed` is terminal for that bounded attempt and is a hard automatic-redispatch veto. A maintainer must explicitly re-triage the broader issue before another agent attempt.

A completed Jules Session with no usable PR output fails closed to
`agent:jules-needs-attention`.

## Implementation

Issue #813 records the defect and acceptance criteria.

Implementation branch:

`fix/jules-review-lifecycle-20260924`

Changed surfaces:

- `config/jules-dispatch.json`;
- `tools/jules_dispatcher.py`;
- `tests/test_jules_dispatcher.py`;
- `tools/check_jules_contract.py`;
- `docs/operations/JULES_AUTOMATION.md`.

The dispatcher now:

1. fetches the full completed Jules Session;
2. extracts `outputs[].pullRequest.url`;
3. requires each PR URL to belong to the same GitHub repository;
4. checks current GitHub PR state;
5. keeps the reservation while any output PR is open;
6. releases it to `agent:jules-completed` once all output PRs are closed/merged;
7. moves completed sessions with no usable PR output to attention.

## Safety / authority

This change does not:

- raise Jules provider concurrency;
- raise repository review concurrency;
- weaken GitHub Actions backpressure;
- grant pull-request write or merge authority;
- let issue prose choose credentials or execution permissions;
- treat Jules output as independent verification.

Normal IDKMesh CI and explicit review remain authoritative.

## Expected development-speed effect

The change removes false review occupancy from long-lived parent issues while keeping the actual number of active/open Jules candidates bounded.

That means waiting small tasks can start when prior Jules PR review is actually finished instead of waiting for an unrelated umbrella issue to close.

## Verification

Focused regression coverage was added for:

- completed Session + open PR => reservation retained;
- completed Session + closed/merged PR => reservation released to completion state;
- completed Session + no PR output => fail closed to attention;
- completion label blocks redispatch;
- policy/contract guard requires the terminal completion lifecycle.

Repository-wide PR Gate remains the integration authority for the exact branch.
