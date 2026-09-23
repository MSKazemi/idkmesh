# GitHub-First Product Execution Plan

**Date:** 2026-09-22  
**Status:** developer execution plan  
**Decision:** ADR-0013  
**Operational specification:** GitHub-First Operations v0.1  
**Umbrella:** #570

## 1. Goal

Deliver an external-project IDKMesh product that a software team can install into a GitHub repository and use collaboratively **without operating a permanent IDKMesh server**.

The plan is complete only when the second-project pilot demonstrates the claim.

## 2. Non-negotiable boundaries

- no second WorkUnit/ResultManifest/VerificationResult format;
- no worker self-acceptance;
- no verifier merge authority;
- no raw secrets in tracked files;
- no broad repository token inside candidate sandboxes;
- no untrusted issue/PR text selecting executable command templates;
- no automatic server requirement before pilot evidence;
- no provider-specific coordinator branches when a shared connector interface suffices.

## 3. Critical path

```text
C1 connector kernel #574
        |
        +----------------------+
        |                      |
C2 Jules #575          C3 model provider #576
                               |
                         C4 local agent #577
        +----------------------+
        |
C5 GitHub dispatch #578
        |
C6 candidate normalization #579
        |
        +----------------------------+
        |                            |
C8 bootstrap #596             C9 durable state #597
        |                            |
        +-------------+--------------+
                      |
C10 multi-user #598
                      |
C12 governance/security #607
                      |
C13 structured intake/Projects #608
                      |
C7 CLI/API #580
                      |
C14 evidence/release UX #609
                      |
C11 no-server second-project pilot #599
                      |
             evidence-based decision
          GitHub-only default or G2 escalation
```

Parallelism is allowed where dependencies permit; do not parallel-edit the central connector/run-state contracts before they stabilize.

## 4. Work packages

### WP1 — connector kernel (#574)

**Developer output**

- profile validation;
- connector registry;
- health/probe contract;
- secret-reference abstraction;
- capability/risk routing;
- deterministic route explanation;
- normalized errors;
- persistence interface.

**PR size**

Prefer 2–4 bounded PRs rather than one monolith:

1. types/profile/schema;
2. registry/probe/errors;
3. routing/policy;
4. store/service integration.

**Exit gate**

Offline fake connectors pass configure -> validate -> probe -> route.

### WP2 — heterogeneous execution (#575, #576, #577)

Run one hosted agent path and one local/model-backed path through common contracts.

**Exit gate**

Same harmless WorkUnit can reach candidate-ready state through two materially different connectors without coordinator-core provider conditionals.

### WP3 — GitHub dispatch bridge (#578)

Implement:

- explicit label/manual dispatch;
- webhook/event validation;
- delivery idempotency;
- repository policy lookup;
- issue -> WorkUnit preview;
- run reference posted back to GitHub.

Do not auto-dispatch every issue.

**Exit gate**

Same event replayed twice -> one admitted run.

### WP4 — candidate normalization (#579)

Normalize:

- provider-created PR;
- GitHub-native agent PR;
- local patch/artifact.

Bind exact candidate SHA and produce canonical ResultManifest/evidence request.

**Exit gate**

PR-backed and artifact-bundle candidates reach equivalent canonical verification semantics.

### WP5 — external-project bootstrap (#596)

Implement `idkmesh init --github`.

**Generated artifacts**

- `.idkmesh/` config;
- thin reusable workflow callers;
- Issue Form template where enabled;
- optional Project-field setup guidance;
- doctor/preflight instructions.

**Exit gate**

Fresh test repository reaches WorkUnit preview with no IDKMesh server.

### WP6 — durable G0 state (#597)

Implement restart-safe run/admission ledger.

**PR slices**

1. ledger schema/store;
2. optimistic concurrency;
3. idempotent admission;
4. recovery scanner;
5. migration/versioning tests.

**Exit gate**

Kill coordinator after dispatch; recovery continues without duplicate provider work.

### WP7 — multi-user roles/claims (#598)

Implement:

- GitHub actor normalization;
- role/capability policy;
- claim/release/expiry;
- dispatch authorization;
- reviewer/integrator separation;
- provenance actor chain.

**Exit gate**

Two users can race for one WorkUnit without duplicate execution; unauthorized actor cannot cross configured dispatch gate.

### WP8 — security/governance baseline (#607)

Implement `doctor --github` preflight plus generated-workflow hardening.

**Must cover**

- rulesets/protection observation;
- explicit workflow permissions;
- secret-bearing job separation;
- Environments;
- CODEOWNERS recommendations;
- OIDC guidance/example;
- immutable third-party workflow/action references.

**Exit gate**

Untrusted fork/PR cannot reach provider secrets in the generated G0 workflow set.

### WP9 — structured planning UX (#608)

Add:

- WorkUnit Issue Form;
- optional Projects field profile;
- sync/projection logic.

**Exit gate**

New contributor can submit a bounded task without raw JSON; Project removal does not break execution.

### WP10 — CLI/API product UX (#580)

Target CLI:

```text
idkmesh init --github
idkmesh project add
idkmesh connections validate/list/probe
idkmesh doctor --github
idkmesh work preview --issue N
idkmesh run --issue N --agent X
idkmesh run status RUN
idkmesh run cancel RUN
idkmesh evidence show RUN
```

Optional HTTP API wraps the same service layer; it is not mandatory for G0.

**Exit gate**

No provider-specific JSON knowledge is required for the supported happy path.

### WP11 — GitHub evidence/control surfaces (#609)

Implement:

- concise status/job summaries;
- stable evidence links;
- optional read-only Pages projection;
- release provenance;
- optional artifact attestations.

**Exit gate**

A maintainer can understand run/candidate/verification/human-decision state using normal GitHub UI.

### WP12 — second-project pilot (#599)

This is the product proof.

Required:

- fresh application repo;
- two+ humans;
- ten+ WorkUnits;
- two worker paths where practical;
- failure/reject/cancel retained;
- duplicate-event test;
- killed-workflow recovery;
- protected human integration;
- tagged release;
- setup/reviewer/compute/provider metrics.

Do not waive requirements to make the demo succeed.

## 5. GitHub capability matrix

| GitHub capability | G0 role | Required? | IDKMesh authority meaning |
| --- | --- | --- | --- |
| Repository | canonical project/code state | yes | source/integration surface |
| Issues | work intake/coordination | yes | proposal, not execution authority |
| Pull Requests | candidate/integration review | yes | candidate + protected integration surface |
| Actions | event coordinator/tests/recovery | yes | execution only |
| Rulesets/branch protection | integration guard | yes/recommended by project risk | repository authority boundary |
| Secrets | provider credential storage | as needed | secret material only |
| Environments | high-risk secret/dispatch gate | recommended | extra authorization, not correctness |
| CODEOWNERS | sensitive-path reviewer routing | recommended | review routing |
| Issue Forms | structured WorkUnit proposal | recommended | input only |
| Projects | team planning/status view | optional | projection only |
| Workflow/job summaries | run evidence UX | recommended | observation only |
| Pages | read-only Control Tower | optional | publication only |
| Releases | product release | pilot yes | release record |
| Artifact attestations | build provenance | optional | provenance, not correctness |
| OIDC | short-lived cloud auth | optional | credential mechanism |
| GitHub App/webhooks | low-latency/multi-repo G2/G3 | later | transport/identity boundary |
| Checks API | richer status via App | later | reporting only |
| Discussions | community/Q&A | optional | no run authority |
| Merge queue | high-throughput integration | later | GitHub integration ordering only |
| cache/artifacts | performance/log retention | optional | never canonical evidence alone |

## 6. Developer Definition of Ready

An issue is ready for an implementation agent/human only if it contains:

- exact objective;
- dependency state;
- allowed/expected files or subsystem;
- forbidden/sensitive surfaces;
- acceptance tests;
- authority/risk notes;
- non-goals;
- evidence expected in PR;
- rollback/failure behavior where relevant.

If those are missing, first create a planning/research WorkUnit.

## 7. PR Definition of Done

Each implementation PR must include:

- issue reference;
- bounded diff;
- tests;
- security/authority impact;
- exact behavior added;
- negative/failure-path tests;
- docs/spec update if contract changes;
- AI/tool provenance where applicable;
- no unrelated stale/reverted main changes;
- current-main rebase/compare before integration.

For state/security/dispatch code, include an explicit adversarial case.

## 8. Test strategy

### Unit

Pure deterministic tests for contracts, routing, idempotency, claims, state transitions, redaction.

### Integration

Use fake GitHub/provider HTTP boundaries and fixture events.

### GitHub workflow

Use safe repository-owned events; never require secrets on untrusted PR-head execution.

### Failure injection

Mandatory before pilot:

- duplicate delivery;
- ambiguous provider submission;
- workflow termination;
- provider timeout;
- malformed candidate;
- stale claim;
- concurrent ledger write;
- verification rejection;
- missing/expired credential;
- missing GitHub protection visibility.

### Live provider smoke

Only after offline contract tests are complete. Use low-risk public WorkUnits and record quota/cost/provenance.

### Pilot

The pilot is the end-to-end acceptance suite.

## 9. GitHub issue taxonomy

Use a small, composable label set rather than creating one label per provider.

Recommended dimensions:

**State**
- `work:ready`
- `work:claimed`
- `work:candidate`
- `work:verifying`
- `work:blocked`

**Risk**
- `risk:low`
- `risk:medium`
- `risk:high`

**Authority**
- existing `authority:agent-candidate`
- `authority:human-required`
- `authority:human-gate`
- `authority:deterministic`

**Capability tier**
- existing `model:t0-deterministic` through `model:t4-peak`

**Execution readiness**
- `agent-ready`

Provider execution labels such as `jules` remain explicit dispatch signals, not generic readiness.

Do not duplicate canonical state in labels if the durable ledger disagrees; labels are a projection.

## 10. Release milestones

### M1 — Connector kernel usable

#574 accepted.

### M2 — Heterogeneous candidate generation

#575/#576/#577 sufficient to demonstrate two paths.

### M3 — GitHub G0 coordinator

#578/#579/#596/#597 complete.

### M4 — Collaborative secure G0

#598/#607/#608 complete.

### M5 — Product UX

#580/#609 complete.

### M6 — G0 proof

#599 complete with retained evidence.

Only then decide whether G2 service work moves into the primary roadmap.

## 11. Developer starting point

At any time, choose the earliest open issue in the critical path whose dependencies are closed/merged.

As of this plan's creation, #574 has started landing. Developers should avoid creating a second connector kernel and instead take the next bounded missing slice in #574 or a dependency-unblocked child.

## 12. Completion criteria for this program

The program is complete when a new team can:

1. create a GitHub repo;
2. run one bootstrap command;
3. see a truthful GitHub preflight;
4. configure secret references;
5. invite collaborators;
6. submit bounded work through GitHub;
7. route to heterogeneous workers;
8. survive retries/restarts;
9. verify exact candidates independently;
10. understand state in GitHub;
11. integrate only through protected human authority;
12. publish a reproducible release;
13. do all of this without a permanent IDKMesh server.

If that works, G0 becomes the documented default deployment profile.
