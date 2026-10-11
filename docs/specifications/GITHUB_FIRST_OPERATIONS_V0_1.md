---
description: "Minimum behavior for running IDKMesh in the GitHub-first G0 profile: from issue to WorkUnit preview, routing, a dispatch gate, and one admitted run."
---
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

Current C8-B safe surface:

```bash
idkmesh init --github --dry-run --idkmesh-ref v0.1.0
idkmesh init --github --dry-run \
  --idkmesh-ref 0123456789abcdef0123456789abcdef01234567 --json
```

The current implementation exposes the deterministic bootstrap plan only. It
performs no filesystem writes, GitHub mutations, secret access, workflow
execution, or repository administration. Omitting `--dry-run` fails closed
until C8-C/C8-D rendering and C8-F safe re-run/conflict handling are
implemented.

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

### 6.2.1 Canonical C9-A record contract

The versioned record shape for the first durable-ledger slice is [GitHub Durable Ledger Record v0.1](GITHUB_LEDGER_RECORD_V0_1.md), with machine-readable schema `schemas/github-ledger-record-v0.1.schema.json`. It freezes compact run/event/route/idempotency/attempt/provider/evidence references without choosing the Git storage layout or granting any next-stage authority. C9-B/C9-C must preserve this record meaning when they define serialization and optimistic append behavior.

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

### 14.1 Current GitHub-native projections

Two bounded implementation layers intentionally have different responsibilities:

- `idkmesh.github_actions_summary.render_github_actions_summary()` renders the
  richer read-only Actions step summary from digest-bound Product Spine,
  candidate, and Run Evidence Report projections. It performs no GitHub
  mutation.
- `idkmesh.github_status_comment.sync_github_run_status_comment()` maintains
  one concise issue/PR comment per run. Its stable marker/comment identity is
  independent of run lifecycle state, so later canonical states update the
  retained comment rather than appending another comment.

The mutable C14-B status comment preserves the earlier C5-H immutable dispatch
receipt as a separate compatibility surface; C14-B does not change C5-H replay
semantics.

Status-comment idempotency rules are:

1. reserve the stable run/comment identity before the first GitHub POST;
2. exact replay of the same rendered projection performs no GitHub request;
3. a changed projection reserves an update and PATCHes the retained comment ID;
4. an interrupted PATCH may retry the **same** desired projection because
   writing the same body to the same comment is idempotent;
5. a different desired projection is blocked while an earlier PATCH reservation
   is unresolved, preventing lifecycle updates from overtaking each other;
6. an ambiguous first POST is not retried automatically because doing so could
   create a duplicate comment; reconciliation is required first.

An optional durable-evidence link is accepted only through the C14-C immutable
GitHub evidence-link contract described below. A GitHub-hosted URL by itself is
not sufficient: moving branch/tag links and Actions artifacts are not durable
canonical evidence.

The REST transport accepts both normal issue-comment HTML URLs and pull-request
conversation comment URLs because GitHub exposes both through the Issues
comments API.

Neither Actions summaries nor status comments can select/accept a candidate,
record a human decision, write canonical application state, push Git, or merge.

### 14.2 Durable evidence links after runner teardown (C14-C)

The canonical implementation is
`idkmesh.github_evidence_link.DurableGitHubEvidenceReference` plus
`validate_durable_github_evidence_url()`.

For a Git-backed evidence file to be called **durable** by GitHub-native
presentation surfaces, the link must identify all three parts of the immutable
Git object location:

1. repository in `OWNER/REPO` form;
2. an exact 40- or 64-hex Git commit revision;
3. a non-traversing repository-relative file path.

Accepted canonical URL forms are:

```text
https://github.com/OWNER/REPO/blob/<exact-commit>/path/to/evidence.json
https://raw.githubusercontent.com/OWNER/REPO/<exact-commit>/path/to/evidence.json
```

The contract deliberately rejects:

- `/blob/main/...`, `/blob/master/...`, release/tag names, or any other
  moving symbolic ref;
- GitHub Actions run/artifact URLs and caches;
- commit landing pages that do not identify an evidence file;
- query strings, fragments, embedded credentials, alternate ports, and
  non-HTTPS URLs;
- non-canonical percent encoding, empty/dot/traversal path segments, or
  backslash-separated paths;
- a different repository when the publishing surface has an explicit
  repository binding.

The helper performs **structural provenance validation only**. It does not fetch
the file, prove that the commit is still reachable from a branch, verify the
evidence contents, or convert a presentation link into correctness evidence.

Actions artifacts and caches remain useful transport/diagnostic surfaces but
must never be the only retained copy of canonical evidence. Essential evidence
must first be stored in the durable Git/ledger retention path owned by C9; C14
then links to that retained object. A runner may terminate after publication
without invalidating the exact-commit permalink.

C14-C does not grant repository-write authority. Producing/retaining the
evidence file is a separate trusted ledger/publication responsibility; this
slice only constructs and validates immutable references to already-retained
files.

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
