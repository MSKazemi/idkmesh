# GitHub-First Operations v0.1

**Status:** experimental implementation contract  
**Date:** 2026-09-22  
**Authority:** operational coordination only; no object in this specification grants acceptance or merge authority.

This specification defines the minimum behavior for running IDKMesh in the **G0 GitHub-first deployment profile** from ADR-0013.

It sits above existing WorkUnit/ResultManifest/EvaluatorPlan/VerificationResult semantics and beside Connector Control API v0.1.

## 1. Scope

G0 must support this lifecycle:

```text
GitHub issue/spec
 -> WorkUnit preview
 -> policy/risk/capability route
 -> explicit dispatch gate where required
 -> one admitted run
 -> connector/provider execution
 -> candidate reference
 -> ResultManifest normalization
 -> independent verification
 -> evidence/status publication
 -> human integration
```

The coordinator may stop between any two arrows and resume in a later workflow run.

## 2. Repository layout

A bootstrapped project should converge on a layout similar to:

```text
.idkmesh/
  project.json
  connectors.json
  policy.json
  README.md

.github/
  workflows/
    idkmesh-preview.yml
    idkmesh-dispatch.yml
    idkmesh-observe.yml
    idkmesh-verify.yml
    idkmesh-recovery.yml
```

Generated workflows should be thin callers of a versioned reusable IDKMesh workflow/action where practical. Generated repositories must not duplicate the full coordinator implementation.

The exact filenames may change before v1.0; semantics below are the contract.

## 3. Bootstrap command contract

Target command:

```bash
idkmesh init --github
```

Required behavior:

1. detect Git repository/default branch/remotes;
2. refuse ambiguous/unrecognized destructive situations;
3. create or update the `.idkmesh/` config skeleton;
4. create thin GitHub workflow wrappers;
5. emit secret-reference placeholders only;
6. emit a preflight report;
7. support `--dry-run`;
8. support re-run/idempotent update;
9. never overwrite unknown user changes without explicit conflict reporting;
10. pin reusable workflow/action dependencies to an explicit released version or immutable revision;
11. print owner/admin steps that require GitHub settings access.

Bootstrap must not silently mutate rulesets, secrets, environments, teams, or repository administration.

## 4. Work intake

### 4.1 Human-readable source

Primary source types:

- GitHub Issue;
- manually supplied existing WorkUnit;
- future Project/Discussion/spec references only through explicit conversion.

### 4.2 Structured Issue Form

When installed, the WorkUnit request form should collect:

- objective;
- task class;
- expected outputs;
- allowed paths;
- forbidden/sensitive paths;
- dependencies;
- acceptance checks;
- risk hint;
- external-processing/data-sensitivity hint;
- review/human-gate hint;
- preferred connector hint.

All issue fields are untrusted.

They may inform preview, but may not set:

- secret references;
- raw secret values;
- executable command templates;
- workflow permissions;
- repository administration;
- merge authority;
- unrestricted filesystem/network scope.

### 4.3 Preview

Preview must perform no dispatch.

It returns/records:

- exact issue/spec revision where practical;
- exact repository base SHA;
- canonical or proposed WorkUnit;
- derived warnings;
- risk/authority class;
- route candidates;
- required human gate.

## 5. Run identity and idempotency

A run has a stable `run_id`.

Before dispatch, compute an idempotency identity from at least:

- repository/project identity;
- WorkUnit ID/version/digest;
- exact base/source SHA;
- attempt number or dispatch slot;
- explicitly selected connector if selection is fixed;
- triggering delivery/event identity where applicable.

The system must atomically or conflict-safely persist admission before or together with provider submission so retries do not create duplicate external work.

If provider APIs expose their own idempotency key, use it in addition to the local durable gate.

## 6. Durable run ledger

### 6.1 Required properties

The G0 ledger is:

- durable beyond an Actions runner lifetime;
- append-only/event-preserving;
- conflict-safe;
- reconstructable;
- secret-free;
- bounded to compact metadata/digests/references;
- independent from Actions cache/artifact retention.

### 6.2 Minimum run record

Persist:

- `run_id`;
- project/repository;
- WorkUnit ID/version/digest;
- exact base SHA;
- attempt;
- connector/driver/version;
- initiating GitHub actor;
- dispatch approval actor/evidence where required;
- external provider/session/job reference;
- state;
- event history or event references;
- candidate locator/head SHA;
- ResultManifest reference/digest;
- VerificationResult references/digests;
- human decision reference;
- failure/cancellation classification;
- timestamps necessary for audit.

### 6.3 Ledger implementation constraints

The first implementation may use a dedicated Git-native branch/path or another GitHub-native immutable/conflict-safe representation.

It must not require writes to the protected application code branch merely to update run state.

The ledger implementation must expose compare-and-set/optimistic conflict behavior so concurrent workflows cannot silently overwrite each other.

## 7. State machine

Canonical operational states:

```text
created
 -> admitted
 -> dispatched
 -> waiting_for_agent
 -> candidate_ready
 -> verification_pending
 -> verified | verification_failed
 -> awaiting_human_decision
 -> integrated | rejected

terminal alternatives:
cancelled
failed
```

Retries create new attempt identities; they do not rewrite history.

Provider-specific intermediate states remain extensions and cannot redefine canonical state.

## 8. Recovery

A scheduled/manual recovery workflow must be able to:

1. scan non-terminal runs;
2. rehydrate state from durable ledger;
3. inspect external provider/job/PR state;
4. normalize newly discovered candidate state;
5. schedule verification if needed;
6. repair missing human-visible status projections;
7. stop without duplicating dispatch.

Recovery is required because normal event delivery is not assumed perfect.

## 9. Multi-user claims and authority

### Roles

Minimum capability roles:

- owner/admin;
- dispatcher;
- worker;
- verifier/reviewer;
- maintainer/integrator;
- node operator.

### Claims

A WorkUnit claim record must include:

- WorkUnit identity/digest;
- claimant identity;
- claim time;
- expiry/release policy;
- state;
- optional run binding.

Claims use deterministic conflict resolution. A stale claim can expire/release without deleting history.

### Authority invariants

- issue author is not automatic dispatcher;
- dispatcher is not automatic verifier;
- verifier is not automatic integrator;
- model tier does not confer repository authority;
- automation cannot grant itself a higher project role.

## 10. GitHub Actions security contract

Generated workflows must:

- declare explicit minimal `permissions`;
- default to `contents: read`;
- disable credential persistence on checkout unless required;
- separate untrusted PR-head execution from secret-bearing jobs;
- treat issue/comment/provider payloads as untrusted;
- pin security-sensitive third-party actions/reusable workflows to reviewed immutable references;
- materialize provider secrets only after policy and authority checks;
- redact secret/header values from errors and summaries.

## 11. Environments

Projects may configure GitHub Environments for:

- high-risk dispatch;
- release/publish;
- external processing requiring explicit approval.

Environment approval is an additional authorization boundary, not proof of candidate correctness.

Environment usage must remain optional for projects/plans where unavailable.

## 12. Rulesets / branch protection preflight

`idkmesh doctor --github` should observe/report, where API permissions allow:

- default branch;
- whether PR-based integration is required;
- force-push/deletion guards;
- required checks;
- review requirements;
- CODEOWNERS-sensitive-path coverage where inferable;
- broad bypass actors when observable.

Report:

- PASS;
- WARN;
- FAIL;
- UNKNOWN (insufficient GitHub permission/API visibility).

UNKNOWN must not be falsely reported as secure.

## 13. GitHub Projects integration

Projects is an optional projection.

Recommended fields:

- IDKMesh state;
- priority;
- risk;
- task class;
- worker/connector class;
- verification state;
- human decision state;
- blocker/dependency summary;
- iteration/milestone.

Project edits never directly broaden execution permissions or create canonical verification evidence.

Removing Projects must not break execution.

## 14. Human-visible status

For each run, publish one concise, idempotently updated status surface using issue/PR comments, job summaries, or checks.

Minimum visible information:

- WorkUnit/run/attempt;
- exact base/candidate SHA;
- connector/worker;
- state;
- required verification;
- verification result;
- human action needed;
- blocked authority;
- durable evidence link/reference.

Avoid one comment per event.

## 15. Pages

Optional read-only Control Tower projection may show:

- active WorkUnits;
- run states;
- verification debt;
- failures/blockers;
- provenance timeline;
- project health.

Pages must be generated only from public-safe data and must never expose secret-bearing/private provider payloads.

Pages has no mutation/approval authority.

## 16. Releases and provenance

For pilot/released projects:

- create normal GitHub Release;
- bind release to exact source tag/SHA;
- retain build/test evidence;
- when supported/configured, generate artifact attestations for distributable artifacts;
- never equate artifact provenance with functional correctness.

## 17. OIDC

When accessing a supported cloud execution/storage service, OIDC short-lived credentials are preferred over long-lived cloud access keys.

OIDC is optional and outside core G0 requirements.

## 18. Failure semantics

Required classes include:

- policy_denied;
- auth/configuration failure;
- provider unavailable/rate limited/quota exhausted;
- duplicate/replayed event;
- concurrency conflict;
- provider submission ambiguity;
- candidate normalization failure;
- verification failure;
- timeout;
- cancellation;
- recovery-required state.

A provider submission ambiguity must fail safe: do not blindly resubmit if it is unknown whether the provider accepted the first request.

## 19. Test matrix

Minimum deterministic tests:

- init dry-run/idempotency/conflict;
- malformed/untrusted issue fields;
- duplicate GitHub delivery;
- concurrent dispatch admission;
- provider submit success/definite failure/ambiguous failure;
- workflow-kill recovery fixture;
- claim collision/expiry;
- permission-policy fixtures;
- branch/ruleset preflight fixtures;
- candidate exact-SHA normalization;
- verifier result binding;
- Projects/Pages disabled path;
- secret-redaction regression.

Minimum live/pilot tests:

- two human actors;
- one hosted connector;
- one heterogeneous second path where available;
- ten WorkUnits;
- one duplicate/replayed event;
- one killed coordinator workflow;
- one failed candidate;
- one rejected candidate;
- protected release.

## 20. Compatibility

This specification must not redefine:

- WorkUnit semantics;
- ResultManifest semantics;
- EvaluatorPlan ownership;
- VerificationResult semantics;
- Connector Control API connection/run meaning.

A change that alters those meanings requires a new explicit version or the corresponding canonical contract update.
