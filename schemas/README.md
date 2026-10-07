# IDKMesh schemas

This directory contains the machine-readable contracts used by the executable research foundation, the first local Verified Swarm Runner work, and the zero-project-spend compute router.

## Current versions

- `executor-admission-v0.1.schema.json` — admission/execution-reservation/submission record bound to one exact ready input snapshot, embedding the local task claim snapshot. The report is metadata; the durable claim is the admission, and it is not a dispatch credential, verification, acceptance or merge authority; see [Executor Admission v0.1](../docs/specifications/EXECUTOR_ADMISSION_V0_1.md).

- `coordination-preflight-v0.1.schema.json` — read-only dependency and declared-effort report: exact WorkUnit/graph/observation/input bindings, prerequisite pins, blockers, shadow capability/connector recommendation and zero project spend. It is not a claim, reservation or dispatch authorization; see [Coordination Preflight v0.1](../docs/specifications/COORDINATION_PREFLIGHT_V0_1.md).

- `task-claim-v0.1.schema.json` — local coordinator claim snapshot: scoped logical task, exact execution/input binding, owner, per-slot epoch, four deadlines, occupancy and candidate digest. Snapshot metadata grants no execution, acceptance or merge authority; see [Local Task Claims v0.1](../docs/specifications/LOCAL_TASK_CLAIMS_V0_1.md).

- `enterprise-control-profile-v0.1.schema.json` — experimental enterprise deployment/control posture: deployment/tenant mode, identity and separation of duties, data/egress, secret/workload identity, audit, reliability/DR, supply-chain, and change-management declarations. A valid/declaration-ready profile is not proof of observed enforcement or compliance certification.
- `enterprise-control-profile-baseline-v0.1.schema.json` — retained baseline declaration contract used by the original control-plane preflight example; kept separate because its field vocabulary is intentionally different from the versioned G0/G1/G2/G3 profile contract above.
- `work-unit-v0.2.schema.json` — current bounded unit of independently executable/verifiable work. It adds vendor-neutral capability/resource requirements, explicit security/trust classification, independent-verification policy, the `benchmarking` work kind required by issue #3, and an explicit project-spend budget.
- `compute-policy-v0.1.schema.json` — repository-level financial/eligibility guard for compute. The current project policy sets project compute spend to `$0` and disables paid providers.
- `compute-offer-pool-v0.1.schema.json` — provider-neutral capacity offers used by the selector: availability, cost class, project monetary cost, trust, capabilities, resources, expected wait, success probability, and independence group.
- `candidate-reference-v0.1.schema.json` — provider-neutral immutable candidate identity: either a GitHub pull request bound to exact repository/PR/head SHA or a content-addressed artifact bundle. It carries no verification, acceptance, or integration authority.
- `result-manifest-v0.1.schema.json` — **worker self-report** for one Work Unit attempt: produced candidate artifacts, logs, resource use, self-reported claims/confidence, provenance, and a request for independent verification. It is deliberately not an acceptance verdict.
- `verification-result-v0.1.schema.json` — **independent verifier result** for one ResultManifest: checks, evidence, findings, resource cost, independence/correlation metadata, provenance, and a recommendation. It is deliberately decision support rather than an automated merge/integration verdict.
- `experiment-manifest-v0.1.schema.json` — preregistered experiment design: hypotheses, configurations, metrics, seeds, budgets, and stopping rules.
- `experiment-result-v0.1.schema.json` — one normalized **experiment-run result** with metrics, costs, verification outcomes, artifacts, and provenance.
- `decomposition-benchmark-v0.1.schema.json` — five-arm issue #15 decomposition comparison with per-unit observations, explicit evidence classification, and stable integration/context/verification metrics.
- `ci-plan-v0.1.schema.json` — exact-revision shadow CI recommendation with risk, mandatory dependency closure, optional-budget decisions, and no execution/skip/merge authority.
- `ci-receipt-v0.1.schema.json` — planning-only receipt proving that a shadow plan was emitted; it contains no executed checks or integration verdict.
- `ci-observation-v0.1.schema.json` — normalized exact-SHA GitHub check snapshot with required-baseline completeness and no authority.
- `gate-audit-report-v0.1.schema.json` — diagnostic report emitted by `idkmesh gate-audit`: per-verifier accuracy, pairwise error correlation, measured effective votes vs the accuracy-dependent ceiling, and seeded-probe breach rate. Decision support about the review layer itself; it grants no acceptance or merge authority.
- `gate-audit-report-v0.2.schema.json` — `gate-audit-report-v0.1` plus an optional finite-sample bootstrap uncertainty section (issue #520), emitted only when `idkmesh gate-audit` is run with `--bootstrap`. Every v0.1 field keeps its v0.1 meaning; nothing about v0.1 changed to add this.
- `gate-audit-dependence-v0.1.schema.json` — measured per-pair verifier error-dependence emitted by `idkmesh gate-audit-dependence` (issue #654): each verifier pair's phi error-correlation over the same non-probe candidates `gate-audit-report-v0.1` uses, bound to the identical input digest so the two artifacts are provably about the same audited panel. `gate-audit-report-v0.1` exposes only the panel *mean* pairwise correlation; this artifact exists so a future adaptive verifier-allocation revision has real per-pair evidence instead of reconstructing it from the mean or from provider/family identity. An unmeasurable pair (zero error variance on one side) is recorded as `measurable: false` with `phi_error: null`, never as correlation 0. It carries `authority: diagnostic_only` and has no routing, acceptance, EvaluatorPlan, or merge authority.
- `marginal-evidence-report-v0.1.schema.json` — diagnostic add-one verifier analysis emitted by `idkmesh gate-marginal`: binds one current panel plus candidate verifier set to the exact verdict matrix, reports gate-rule-specific panel deltas, correlation/transition/probe evidence, explicit unresolved/censoring states, and optional paired-bootstrap uncertainty. It carries `authority: diagnostic_only` and has no routing, EvaluatorPlan, acceptance, or merge authority.
- `marginal-evidence-benchmark-config-v0.1.schema.json` — preregistered design/holdout configuration for the #693 selector benchmark: exact current/candidate verifier sets, family metadata, deterministic random seed, and bootstrap settings with local relative matrix paths.
- `marginal-evidence-benchmark-report-v0.1.schema.json` — diagnostic held-out comparison of the marginal effective-vote selector against random, highest-accuracy, different-family-first, and minimum-correlation baselines. The report binds the frozen design-only selection plan and both split digests and grants no routing or integration authority.
- `marginal-evidence-synthesis-config-v0.1.schema.json` — frozen manifest for descriptive cross-cohort synthesis of at least two marginal-evidence benchmark reports. It binds one evidence class, the frozen v0.1 selector-rule version, and distinct local relative report paths.
- `marginal-evidence-synthesis-report-v0.1.schema.json` — diagnostic cross-cohort aggregation preserving per-cohort selector outcomes plus descriptive panel-error/effective-vote summaries. It intentionally contains no winner, ranking, threshold-tuning result, routing recommendation, or integration authority.
- `ci-evaluation-v0.1.schema.json` — shadow plan/outcome comparison recording mapped misses, attribution gaps, modeled savings, and permanent v0.1 promotion ineligibility.
- `human-decision-record-v0.1.schema.json` — a recorded, accountable human integration decision (`accept`/`reject`/`escalate`) against one Run Evidence Report: who decided, what they decided, when, and why, bound to the exact report by content digest. It is deliberately a record of a decision, not an executor of one: it carries no canonical-state-write, git-push, or merge authority. Produced by `experiments/record_human_decision.py`.
- `idkmesh-human-decision-request-v0.1.schema.json` — HTTP request-body contract reserved for #740: the caller may provide only the explicit decision, rationale, selected attempt and exact evidence-report binding. Authenticated principal identity, decision ID, timestamp and authority are server/trusted-context derived; `Idempotency-Key` remains an HTTP header under API Conventions v0.1.
- `idkmesh-human-decision-response-v0.1.schema.json` — successful immutable decision-recording response wrapper: returns the canonical Human Decision Record plus its digest. Exact idempotent replay returns the same record; the wrapper does not execute integration, Git push or merge.
- `search-visibility-observation-v0.1.schema.json` — evidence contract for dated Google/Bing/ChatGPT/Gemini/Claude/Perplexity/Copilot/Yahoo visibility observations. It records surface, query, mapped intent, target URL, whether IDKMesh surfaced, and optional citation/position evidence without manufacturing a cross-engine ranking score.
- `enterprise-resource-ref-v0.1.schema.json` — tenant/project-scoped enterprise resource reference. Scope is part of resource identity and is not inferred from an unscoped resource id.
- `enterprise-actor-context-v0.1.schema.json` — normalized trusted human/service/provider/node identity claims for E3 authorization. It is an authorization input only when produced by a trusted authentication adapter; issue/task/model text is not an identity source.
- `enterprise-authorization-decision-v0.1.schema.json` — deterministic allow/deny/requires-approval evidence bound to tenant/project resource identity, policy revision, identity revision, risk, and data class. The decision object performs no side effect and carries no merge authority itself.
- `enterprise-audit-event-v0.1.schema.json` — E4 privileged-operation audit evidence: tenant/project, request/run correlation, actor + service identities, exact resource revision, authorization decision digest/reason/approval, outcome, retention, previous/current SHA-256 chain links, and an explicit no-authority ceiling.
- `enterprise-github-identity-binding-v0.1.schema.json` — maintainer-reviewed table binding trusted numeric GitHub actor ids to enterprise `ActorContext` roles, tenant/project scopes, and data clearance (E3-B, issue #670). The numeric actor id is the primary trust key; issue/PR/comment text is never a binding source.
- `enterprise-oidc-identity-binding-v0.1.schema.json` — maintainer-reviewed table binding trusted `(issuer, subject)` enterprise IdP (OIDC/SAML/SSO) claim pairs to enterprise `ActorContext` roles, tenant/project scopes, data clearance, and expected relying-party audience (E3-C, issue #670). The `(issuer, subject)` pair is the primary trust key; issue/PR/comment text is never a binding source.
- `idkmesh-api-error-v0.1.schema.json` — the frozen standard error envelope every IDKMesh JSON API returns (`docs/specifications/API_CONVENTIONS_V0_1.md` section 5, [ADR-0018](../docs/decisions/ADR-0018-freeze-api-conventions-v0-1.md)). `code` is the compatibility-sensitive contract; `message` is explanatory only.
- `idkmesh-idempotency-v0.1.schema.json` — idempotency and conflict metadata for externally retried mutations (`docs/specifications/API_CONVENTIONS_V0_1.md` section 12, issue #737): the admission form reserves one idempotency key against one canonical request digest before any side effect (exact replay returns the original logical result, never a second attempt), and the conflict form records a 409 `idempotency_conflict` when the same key is presented with a different digest. Key/request/run ids are deduplication metadata, never work slots or authority; see [API Conventions v0.1](../docs/specifications/API_CONVENTIONS_V0_1.md).

- `idkmesh-list-v0.1.schema.json` — the frozen standard paginated list envelope for IDKMesh JSON list endpoints (`docs/specifications/API_CONVENTIONS_V0_1.md` section 10, ADR-0018). Uses an opaque cursor, never an offset, so mutable event/run streams stay safe to page.
- `control-tower-snapshot-v0.1.schema.json` — the deterministic, read-only human-facing projection of one validated Run Evidence Report returned by the Control Tower Local API's inspection endpoint (`docs/specifications/CONTROL_TOWER_LOCAL_API_V0_1.md`). Grants no actuation authority.
- `idkmesh-control-tower-status-v0.1.schema.json` — the authenticated discovery/status document from `GET /api/v1/status`: accepted media types, published schema URLs, and explicitly enabled/disabled capabilities (issue #737).
- `idkmesh-control-tower-inspection-response-v0.1.schema.json` — the success envelope wrapping one digest-bound `control-tower-snapshot` from `POST /api/v1/run-evidence/inspect` (issue #737).
- `idkmesh-readiness-v0.1.schema.json` — the minimal `GET /readyz` readiness document (`idkmesh/service_runtime.py:readiness_document()`), shared by every IDKMesh HTTP service and carrying no project/evidence state (issue #737).
- `idkmesh-api-operational-metrics-v0.1.schema.json` — privacy-safe aggregate Control Tower HTTP telemetry for #744: fixed status classes, cumulative latency buckets, bounded concurrency/admission gauges and counters, operation counts, coarse dependency configuration state, and explicit no-payload-label guarantees.
- `idkmesh-product-spine-run-v0.1.schema.json` — an immutable read projection over one Product Spine lifecycle (`idkmesh/product_spine.py:ProductSpineRun`), printed by `idkmesh run create/status/cancel --json` and served read-only by `GET /api/v1/runs/{run_id}` (issue #739). Carries no canonical-state-write, git-push, or merge authority.
- `idkmesh-control-tower-run-response-v0.1.schema.json` — the success envelope wrapping the run projection above for `GET /api/v1/runs/{run_id}` (issue #739). Reuses the exact `PersistedProductSpineRun` shape the CLI's `run status --json` already prints, so the HTTP and CLI surfaces cannot silently disagree.

All current schemas use JSON Schema Draft 2020-12.

## WorkUnit v0.2 contract

The current WorkUnit contract explicitly separates several concerns that were implicit or missing in v0.1:

- `kind` supports at least coding, testing, review, benchmarking, and documentation work;
- `requirements.capabilities` describes vendor-neutral worker capabilities;
- `requirements.resources` describes minimum CPU/memory/disk/GPU needs;
- `security` declares risk class, data classification, minimum worker trust, and whether sandboxing is required;
- `permissions` bounds network, filesystem, secret, and process authority;
- `verification_policy` states how independent validation is combined;
- `validators` states concrete required checks;
- `evidence_requirements` tells a verifier what evidence must exist without needing a worker's private reasoning;
- `budget.project_spend_usd_max` states the most the IDKMesh project may pay for that Work Unit;
- `budget.paid_fallback_allowed` states whether the Work Unit would permit a paid fallback **if** repository policy also permits it;
- `dependencies` represents WorkUnit graph relationships;
- `provenance` records origin and optional source revision/timestamp.

A Work Unit cannot grant financial authority. Repository policy is applied first and acts as a hard ceiling. Therefore a Work Unit may tighten the project spending constraint but cannot relax it.

The coordinator contract remains model/provider neutral. Model and adapter details belong in worker/result provenance, not in WorkUnit scheduling semantics.

## Zero-project-spend compute contracts

The active machine-readable policy is `config/compute-policy.json`:

```text
project_spend_usd_max = 0
paid_providers_enabled = false
```

Allowed cost classes currently include:

- `local_owned` — a participant's own already-available machine;
- `donated` — explicitly volunteered capacity;
- `public_project_ci` — public-project CI only when the task legitimately fits that service's terms;
- `grant` — capacity funded externally without a project invoice;
- `free_tier` — genuine free quota within its terms and limits.

`paid` is represented in the offer schema for interoperability/testing but is disabled by repository policy.

The selector prototype is `experiments/free_compute_router.py`. It filters provider-neutral offers against both repository policy and Work Unit requirements. Its fail-closed invariant is:

> **No eligible zero-project-cost offer -> no selection. Never silently convert resource scarcity into project spending.**

CI includes a negative test in which a synthetic GPU Work Unit tries to authorize `$100` and paid fallback while the only available matching GPU is a paid offer. Repository policy must still reject it and return no eligible offer.

“Zero cost to the project” does not mean zero real-world cost. Donors can bear electricity, bandwidth, thermal load, hardware wear, and opportunity cost. Donated compute therefore must remain opt-in, transparent, resource-capped, and easy to stop.

## Critical separation: candidate, verification, integration

IDKMesh keeps these concepts separate:

```text
Work Unit
   -> worker attempt
   -> ResultManifest (candidate + worker self-report)
   -> independent verifier(s)
   -> VerificationResult (checks + evidence + recommendation)
   -> experiment/integration/human decision
```

A worker may report that it completed successfully and may report confidence, but those fields are evidence about the worker's own state, not proof that the artifact is correct. The `ResultManifest` therefore does not contain an `accepted` field or an independent-verifier verdict.

Likewise, a `VerificationResult` may recommend `accept_candidate`, but that recommendation does not authorize a merge or mutate canonical state. Integration policy remains a separate layer.

The harness validates semantic and cross-object invariants in addition to JSON structure:

- configuration IDs within one ExperimentManifest must be unique before WorkUnit loading or experiment execution; configuration identity is part of both emitted run identity and the deterministic smoke-score key, so duplicates would make distinct experimental arms ambiguous;
- produced artifact IDs within one ResultManifest must be unique before verification evidence references are resolved;
- VerificationResult must reference the exact ResultManifest/WorkUnit attempt;
- evidence IDs referenced by checks must exist;
- required WorkUnit validator IDs must appear as verification checks;
- validator IDs requested by the ResultManifest must appear;
- when a WorkUnit requires independence, verifier identity must differ from worker identity;
- an `accept_candidate` recommendation requires verification status `passed` and all required checks passed.

Negative fixtures:

- `examples/results/invalid-self-acceptance.result-manifest.json` adds worker-side `accepted: true` and must fail schema validation;
- `examples/results/invalid-non-independent.verification-result.json` is schema-valid but deliberately violates the WorkUnit's independence rule and must fail cross-object contract validation;
- `examples/work-units/invalid-missing-security.work-unit.json` omits required security/trust classification and must fail schema validation.

## Versioning rule

`0.x` schemas are experimental. A change is breaking when a previously valid document can become invalid or when the meaning of an existing field changes. Breaking changes require a new schema file/version; old schema files remain in the repository so historical experiments stay reproducible.

That rule is why issue #3 is completed through `work-unit-v0.2.schema.json` instead of silently changing `work-unit-v0.1.schema.json`.

**Compatibility note:** adding mandatory monetary-budget fields to v0.2 is currently an in-development contract change made before a stable release. Once a schema version is used for durable external artifacts, future breaking changes must use a new version rather than modifying that file in place.

Additive research-specific data should normally go in the `extensions` object, using a namespaced key such as `org.example.my_metric`, until there is evidence that the field belongs in the shared core.

## Schema migrations

Breaking changes ship as new, separately versioned files (the versioning rule
above and [ADR-0020](../docs/decisions/ADR-0020-schema-backward-compatibility-gate.md));
this ledger is the explicit migration note issue #737 requires alongside each
one. Every entry names the exact file superseded and what its consumers must
change. `tools/schema_migration_note_check.py` fails CI when a version
successor has no entry here, when an entry names the wrong predecessor, or
when an entry names a file that is not a successor.

- `evaluator-plan-v0.2.schema.json` supersedes `evaluator-plan-v0.1.schema.json`: replaces the file-content checks (`allowed_files`, `max_candidate_bytes`, `required_json`) with a declared `backend` object and re-pins the verifier adapter consts; consumers must dispatch on `backend.type` instead of the removed top-level fields.
- `evaluator-plan-v0.3.schema.json` supersedes `evaluator-plan-v0.2.schema.json`: renames `backend.required_added_text` to `backend.required_added_substrings`, so a required source change is a list of substrings rather than one exact added text; wrap single-text expectations in a one-element list.
- `evaluator-plan-v0.4.schema.json` supersedes `evaluator-plan-v0.3.schema.json`: adds required `backend.required_removed_substrings`, so producers must state what must be removed; use an empty list when nothing must be removed.
- `gate-audit-report-v0.2.schema.json` supersedes `gate-audit-report-v0.1.schema.json`: adds the required `uncertainty` section (finite-sample bootstrap, issue #520) and pins `provenance.input_digest_sha256` to `sha256:<64 lowercase hex>`; only `idkmesh gate-audit --bootstrap` emits v0.2, so reports produced without it remain v0.1.
- `work-unit-v0.2.schema.json` supersedes `work-unit-v0.1.schema.json`: adds required `requirements`, `security`, and `verification_policy` sections plus required `budget.project_spend_usd_max` and `budget.paid_fallback_allowed`, widens `kind` with `benchmarking`, and optionally records `provenance.source_revision`/`created_at`; migrate by filling the new required sections (zero spend with `paid_fallback_allowed: false` under the current project policy).

## Compatibility notes

- WorkUnit v0.1 remains available for historical Phase 0 artifacts.
- The current harness validates new WorkUnits against v0.2.
- The valid v0.2 Phase 0 smoke fixture includes the new zero-project-spend budget fields.
- The deliberately invalid Work Unit fixture remains invalid and is used only as a negative test.
- ResultManifest v0.1 remains compatible with the v0.2 smoke fixture because it references the WorkUnit by stable `id` plus document `version`; the fixture references WorkUnit version `2`.
- VerificationResult v0.1 binds to a ResultManifest plus the same WorkUnit id/version/attempt and adds independent evidence without redefining worker output semantics.
- Future ResultManifest or VerificationResult revisions should only be created when their own semantics require a breaking change.
- ExperimentManifest v0.1 remains structurally unchanged. The harness enforces unique `configurations[].id` values as a semantic preflight invariant because JSON Schema `uniqueItems` would only compare complete configuration objects, not their logical IDs. This narrows executable manifests without rewriting historical schema files.

## Design principles

1. **Bounded authority** — a Work Unit states scope and permissions.
2. **Proposal is not proof** — worker output and independent verification are separate protocol objects/stages.
3. **Verification is not integration authority** — verifier recommendations remain evidence for a later policy/human decision.
4. **Uncertainty is data** — assumptions, confidence, and unresolved statements can travel with the work without becoming truth by assertion.
5. **Project spending is an authority boundary** — task inputs and agents cannot authorize billing; repository policy is the hard ceiling.
6. **Cost is part of quality** — project money, donated resource use, compute, time, tokens, communication, and human attention must be distinguishable and measurable.
7. **Provenance from day one** — experiments and outputs should be traceable.
8. **Reproducibility before sophistication** — early contracts should remain understandable and replayable.
9. **Vendor-neutral core** — WorkUnit semantics describe needed capabilities, not a specific model/provider/tool.
10. **Safe CI** — repository CI validates manifests and fixtures but does not execute commands supplied by experiment manifests.

See `PROJECT_RULES.md`, `docs/decisions/ADR-0006-zero-project-spend-compute.md`, `docs/architecture/OPPORTUNISTIC_COMPUTE_FABRIC.md`, `docs/research/PHASE_0_SPEC.md`, `docs/research/VERIFICATION_DEBT_AND_BACKPRESSURE.md`, issues #3, #5, #11, #14, #15, #17, and the completed Phase 0 issue #19.

The WorkUnit composability benchmark and its strict synthetic-versus-observed
evidence boundary are documented in
`docs/specifications/WORK_UNIT_COMPOSABILITY_V0_2.md`.

## Closed-object policy

Every top-level object schema in this directory declares its
`additionalProperties` policy explicitly, and is closed (`false`) by default —
issue #737's "`additionalProperties: false` used where intentional". The only
open documents are the four legacy unversioned contracts recorded with reasons
in `tests/test_schema_validity.py`, which shipped open before the policy and
cannot be closed in place under [ADR-0020](../docs/decisions/ADR-0020-schema-backward-compatibility-gate.md);
where a strict versioned successor exists, closure lives there. New public
objects ship closed; the same test module enforces the policy in CI.
