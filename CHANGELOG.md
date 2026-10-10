# Changelog

Notable changes are summarized here; this is not an exhaustive commit log.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). IDKMesh is
pre-1.0 research software and does not yet follow semantic versioning: contracts under
`schemas/` carry their own explicit versions (for example `work-unit-v0.2`), and those
versions, not the release tag, are what downstream code should depend on.

This file starts at the first public release. Earlier changes remain in git history
and the release notes for that tag.

## [Unreleased]

### Added

- Preregistration v2 (`docs/research/PREREG_AGENT_VALUE_FORECAST_V2.md`) and
  the E048 runner (`experiments/temporal_holdout.py`) register, before any data
  exists, a temporal-holdout replication of the agent-value forecast on SWE-bench
  submissions added after the pinned commit. Upstream currently has none; the
  runner reports that and does nothing else.

- T1 / E047 (`experiments/submission_provenance.py`) adds provenance for public
  SWE-bench submissions: model, model organisation, scaffold and attempts,
  with canonicalised model names. Verified's 169 competent submissions come
  from 66 identifiable models and 12 organisations; 81 are multi-attempt. In
  an exploratory re-run with one submission per model, H1 still holds on both
  Verified and Lite. Choosing one agent per model organisation loses to
  complementarity selection (Lite, k = 5, p = 0.0026).

- E046 confirmatory results (`experiments/E046-agent-value-forecast.md`). The
  analysis frozen by PREREG_AGENT_VALUE_FORECAST_V1 was run unchanged on the
  held-out SWE-bench Lite split (78 agents × 300 tasks). Per-item difficulty
  (beta-binomial) forecast team coverage with error 0.0316, against 0.1619 for
  the Kish design effect and 0.0816 for shared shock (H1 supported). H2 and H3
  passed the registered rule but are fragile under a disclosed post-hoc check
  on tasks disjoint from Verified. Test, Multilingual and Multimodal were
  infeasible (fewer than 20 competent agents).

- Preregistration v1 for forecasting the value of the next coding agent
  (`docs/research/PREREG_AGENT_VALUE_FORECAST_V1.md`, issue #973). It freezes
  the E046 analysis (`experiments/agent_value_forecast.py`, SHA-256 recorded)
  before the four held-out SWE-bench splits are opened. The analysis covers
  dependence models, coverage forecasters and complementarity selection,
  with H1–H3 decision rules. The exploratory output on the already-seen
  Verified split is retained and labelled as such.

- The scientific program (`docs/research/SCIENTIFIC_PROGRAM.md`, umbrella
  issue #968) states the one question IDKMesh is organised around: *when does
  adding another AI agent, as worker or verifier, increase independently
  verified useful work, and can that be predicted from a small pilot?* It also
  defines the audience, hypotheses H1–H6, experiments X1–X10, algorithms
  A1–A7, engineering targets T1–T6, the checked novelty boundary, and phases
  S0–S5. `RESEARCH_QUESTIONS.md` is now labelled as the long-horizon backlog.
- E045, an exploratory pilot (`experiments/public_agent_dependence.py`). It
  reads public execution-graded SWE-bench Verified results, at a pinned
  upstream commit, for 169 competent coding systems × 500 tasks. Mean pairwise
  φ is 0.4763, 26/500 tasks are solved by no system, and oracle best-of-10
  covers 0.8521 where independence predicts 0.9997.

- Transport-neutral Human Decision service core for issue #740
  (`idkmesh/human_decision_service.py`). It records an `accept` / `reject` /
  `escalate` decision with a rationale into an append-only SQLite store whose
  triggers reject UPDATE and DELETE, bound to the exact retained Run Evidence
  Report digest (a stale or swapped digest fails closed) and to a selected
  attempt that must exist in that report. The decider comes only from a trusted,
  authenticated, unrevoked, unexpired human `ActorContext`; the request body
  cannot supply identity, timestamp, decision id or authority. `Idempotency-Key`
  semantics follow API conventions section 12 and are bound to the principal:
  same principal, key and request replays the original record; a different
  request or a different principal with the same key is `idempotency_conflict`.
  Responses match the frozen `idkmesh-human-decision-response-v0.1` schema and
  returned records are copies. Not yet built: no HTTP endpoint or CLI calls this
  core, it performs no tenant/role policy authorization (`decisions:write`), and
  it emits no audit-ledger event; those remain owned by #740 with #670/#671/#743,
  so a local session token still cannot record a decision.
||||||| parent of 91d5a48 (research: define the scientific program and add the E045 public agent-dependence pilot)
- API-11A client read-model completion for issue #746: the official
  dependency-free Python client (`idkmesh.api_client.ControlTowerClient`) now
  covers the whole resource-oriented Control Tower read model — `list_runs`
  (bounded `state`/`project_id` filters, keyset pagination), `get_run_attempts`,
  `get_work_unit`, `list_work_units`, `get_project`, and `list_connections`
  (secret-free connector metadata from `GET /api/v1/connections`) alongside the existing
  status/inspection/run/evidence/event methods. Every resource response is
  identity-bound to the requested id and fails closed with `ProtocolError` on a
  mismatch; list validation happens before any transport I/O; cursors stay
  opaque. The client surface is documented in
  [Control Tower Local API v0.1](docs/specifications/CONTROL_TOWER_LOCAL_API_V0_1.md).
  Human-decision recording remains absent until the authenticated mutation
  adapter (issue #740) exists; health/readiness probes, `openapi.json`,
  `metrics`, and the `events/stream` SSE stream stay plain HTTP.
- Read-only connector listing on the Control Tower for API-3 / issue #738:
  authenticated `GET`/`HEAD /api/v1/connections` serves the connection rows
  `idkmesh connections import` persists, through the existing `/api/v1`
  service rather than a second HTTP server. Items are a strict public-safe
  projection (`schemas/idkmesh-connection-resource-v0.1.schema.json`) in the
  shared `idkmesh-list-v0.1` envelope with bounded keyset pagination and an
  opaque cursor; secret references and settings are never returned, and a
  legacy/free-form row fails closed with `500 connection_record_invalid`
  instead of being serialized. The endpoint is advertised in `openapi.yaml`,
  the runtime OpenAPI document, and `GET /api/v1/status`, and its 200/400/403/
  503 responses are runtime representatives in
  `tests/test_api_contract_conformance.py`. No connector create, probe,
  enable/disable, secret resolution, dispatch, or provider call is added.
- Public-safe GitHub evidence projection for issue #609 (C14-D):
  `idkmesh/github_public_evidence.py` builds a strict whitelist over
  digest-bound Product Spine, CandidateReference, and Run Evidence Report
  state, gated by a trusted public-classification policy, and its JSON
  renderer rejects any mapping outside that whitelist. Raw prompts, logs,
  provider payloads, warnings, identities, artifact locators, and secrets are
  never projected, and every authority flag is fixed to `false`. See
  [GitHub Public Evidence Projection v0.1](docs/specifications/GITHUB_PUBLIC_EVIDENCE_V0_1.md).
  No Pages generator, GitHub mutation, or repository-visibility probe is
  included.

- Canonical capability truth matrix for issue #944:
  `docs/capability-matrix-v1.json` is the machine-readable public claim
  boundary, with generated human/site projections and a normal-CI drift guard.
  Release wording must use the matrix's `verified_revision` and the #943
  evidence level (0 planned through 5 production-qualified) rather than
  inferring maturity from code presence alone. This matrix/drift mechanism is
  evidence level 1 (implemented); it does not promote the project itself to
  production-qualified.

- GitHub governance baseline policy object for issue #607 (C12-A):
  `idkmesh/github_governance_policy.py` defines deterministic
  required/warn/optional guards for read-only, candidate, secret-bearing,
  high-risk, and cloud dispatch and for integration. Automatic GitHub admin
  mutation and treating ruleset metadata as proof of independent review are
  structurally forbidden. Policy only: no GitHub API call, ruleset evaluation,
  workflow lint, or `doctor --github` output is added yet. See
  [Main protection](docs/admin/MAIN_PROTECTION.md).

- Privacy-safe API observability slice for issue #744: the loopback Control
  Tower now exposes authenticated `GET /api/v1/metrics` with fixed-cardinality
  request/status/error counters, cumulative latency buckets, concurrency and
  overload/drain signals, evidence-inspection counts, and coarse optional-store
  configuration state. Valid W3C `traceparent` v00 is passed through without
  treating trace context as identity. The schema deliberately has no path,
  query, request-id, authentication, prompt, evidence, run, or WorkUnit label
  fields. Local-profile SLO/alert targets are documented in
  [API Observability v0.1](docs/specifications/API_OBSERVABILITY_V0_1.md).
  OpenTelemetry export and Human Decision ingestion metrics remain follow-up
  work; no new runtime dependency or actuation authority is introduced.

- Dependency-free OTLP metrics mapping for issue #744:
  `idkmesh.otel_metrics.build_otlp_metrics_request()` converts one validated
  API operational-metrics document into an OTLP `ExportMetricsServiceRequest`
  JSON object (cumulative monotonic sums, gauges, and a histogram whose
  cumulative source buckets are differenced into OTLP per-bucket counts), and
  `render_otlp_metrics_json()` renders it as deterministic strict JSON. The
  adapter is transport-free (no network I/O, credentials, retries, spans, or
  clock reads) and fails closed if the source document is inconsistent,
  relaxes its privacy flags or authority ceiling, or manufactures a
  `not_implemented` counter. A collector transport and Human Decision
  ingestion telemetry remain follow-up work under #744. See
  [API Observability v0.1](docs/specifications/API_OBSERVABILITY_V0_1.md).

- Enterprise Audit Ledger v0.1 (issue #671): a dedicated SQLite append-only
  security/audit stream separate from ordinary logs and Product Spine events.
  Each fixed-shape event binds tenant/project, request/run correlation,
  normalized actor + audit-writer identity, exact resource revision, the
  canonical Enterprise Authorization Decision digest, stable reason/approval
  references, outcome, evidence digest, retention eligibility, and SHA-256
  previous/current chain links. UPDATE/DELETE triggers enforce append-only
  storage; replay verification detects rewrites/gaps and saved head checkpoints
  detect suffix truncation. A tenant-scoped `AuditExportSink` contract and
  deterministic NDJSON sink support governed SIEM/archive adapters; retention
  exposes a legal-hold hook but no delete authority. See
  [Enterprise Audit Ledger v0.1](docs/specifications/ENTERPRISE_AUDIT_LEDGER_V0_1.md).

- Documented examples for every advertised API surface (issue #737):
  `examples/api/` gains nine fixtures — the inspection, project, WorkUnit and
  run-evidence response envelopes, one SSE event, the inspect request body
  (`run-evidence-report`), both `idkmesh-idempotency-v0.1` forms, and a
  `human-decision-record` — so every schema `openapi.yaml` serves or accepts
  now has a committed, CI-validated example. A completeness guard fails if a
  future response or request body loses its example. Digest fields that name
  embedded fixture content carry the real canonical digest of it and are
  recomputed in CI (digests naming unembedded content stay deterministic
  placeholders, per `examples/api/README.md`). As part of this,
  `tests/test_example_contract_coverage.py` now resolves cross-file `$ref`s
  through a schema registry: the resource-referencing response contracts
  could not be validated at all without it, and a guard test proves
  corruptions inside a `$ref`'d member are seen rather than skipped.

- API contract conformance, documented-examples leg (issue #737):
  `tests/test_api_contract_conformance.py` binds every `examples/api/`
  fixture to the exact response it documents and resolves that response's
  target schema from `openapi.yaml` itself (text-scanned, stdlib-only, like
  the PR Gate's shared scripts), then validates the fixture against that
  advertised contract. A cross-check keeps the catalog, the example/schema
  pairing in `tests/test_example_contract_coverage.py`, and the endpoint
  binding in agreement, so the catalog cannot drift away from the tests
  without one of them failing (API Conventions section 19: "examples
  validate in CI").

- Closed-object schema policy (issue #737, "`additionalProperties: false`
  used where intentional"): every top-level object schema in `schemas/`
  must now declare its `additionalProperties` policy explicitly and is
  closed by default, enforced by `tests/test_schema_validity.py` in CI. The
  only open documents are the four legacy unversioned contracts recorded
  with reasons (`experiment-result`, `goal-graph`, `result-manifest`,
  `work-unit`), which shipped open before the policy and cannot be closed
  in place under ADR-0020; strictness lives in their versioned successors.

- API contract conformance, runtime leg (issue #737): the same
  `tests/test_api_contract_conformance.py` serves representative responses
  over real loopback HTTP (the shipped `create_server` entry point, one
  server with a Product Spine store and one without) and validates each
  against the schema `openapi.yaml` advertises for it. An exhaustiveness
  guard requires every advertised response to have a representative or a
  recorded reason it carries no canonical schema (API Conventions section
  19: "representative runtime responses validate in CI"). Every envelope the
  runtime serves is now advertised and validated through its representative:
  the `product_spine_store_not_configured` 503s on the work-unit, project,
  and events surfaces and the inspect endpoint's api-error 406/413/415
  bodies were the last served-but-unadvertised envelopes; `openapi.yaml` now
  declares all of them against `idkmesh-api-error-v0.1`, and the
  pinned-gap ledger retired when its last entries moved into the
  representatives. No public API object is served outside the catalog.

- Checked-in OpenAPI 3.1 catalog (issue #737): `openapi.yaml` at the repository
  root describes the shipped v1 surfaces (status, readiness, run-evidence
  inspection, runs/WorkUnits/projects reads, events and the resumable SSE
  stream) and references every public contract in `schemas/` — including
  `idkmesh-idempotency-v0.1` — by its canonical `$id`, so no public API object
  is defined only by prose or an inline Python dictionary. Discovery/transport
  contract only; domain truth stays in `schemas/` (API Conventions section 19).
  Guarded by reference-coverage and resolution tests.

- OpenAPI/schema reference resolution gate (issue #737):
  `tools/openapi_ref_check.py` resolves every `$ref` in `openapi.yaml` and
  `schemas/*.schema.json` — internal JSON pointers, `#/components/...`
  component references, and cross-file schema references (matched by `$id`
  basename, per `tests/test_schema_identity.py`) — and exits non-zero on any
  unresolved reference (API Conventions section 19: "unresolved refs fail
  CI"). Stdlib-only and executable like `tools/schema_compat_check.py`; wired
  into the PR Gate and `scripts/testkit.py integration` with negative-path
  regression tests in `tests/test_openapi_ref_check.py`.

- Idempotency/conflict metadata contract (issue #737):
  `idkmesh-idempotency-v0.1.schema.json` freezes the request-identity
  reservation vocabulary used by the Product Spine and GitHub delivery
  idempotency adapters (API Conventions section 12): exact-digest replay of
  the original logical result, a strict `created`/`replayed` complement, and
  the 409 `idempotency_conflict` record for a reused key under a different
  digest. Identity metadata only; no execution, acceptance or merge authority.

- Executor admission gate (issue #921): one operation derives the exact
  execution binding from the ready input snapshot and acquires the atomic
  claim, the external dispatch intent is retained only on still-current
  inputs, and the snapshot is rechecked at canonical candidate submission.
  Changed upstream inputs fail closed (`inputs_changed`) before any dispatch
  intent or submission digest is written; logical task identity stays
  separate from the execution binding. Local conformance composition only;
  live provider wiring and the GitHub ledger remain separate work. See
  [Executor Admission v0.1](docs/specifications/EXECUTOR_ADMISSION_V0_1.md).

- Read-only coordination preflight (issue #915): iterative WorkUnit prerequisite
  graph, exact integrated input pins, replay-safe readiness and transitive stale
  input detection. Declared-effort shadow recommendations reuse the existing
  connector resolver, preserve risk/authority floors and prohibit paid fallback.
  Includes a synthetic stdlib demo and critical-path estimates with review and
  integration time; live scheduling/routing is unchanged. See [Coordination Preflight v0.1](docs/specifications/COORDINATION_PREFLIGHT_V0_1.md).

- Local atomic task claims and occupancy-safe recovery (C10-D/E, issue #914):
  one implementation slot by default, explicit bounded competition, immutable
  lifetime/deadline budgets, scoped replay, per-slot fencing, fresh authority
  checks and retained unknown execution across lease expiry/restart.
  `LocalMetadataStore` migration v3 preserves v2 run/event rows. This is a
  local coordinator library; provider, GitHub-ledger and public mutation API
  integration remain separate work. See [Local Task Claims v0.1](docs/specifications/LOCAL_TASK_CLAIMS_V0_1.md).

- [`docs/community/AGENT_CONTRIBUTOR_GUIDE.md`](docs/community/AGENT_CONTRIBUTOR_GUIDE.md):
  how to contribute with your own AI coding agent (Claude Code, OpenAI Codex,
  Google Jules). It points each tool at `AGENTS.md`, gives a paste-ready brief,
  the commands that check your work, and the provenance note every
  agent-assisted change carries. It adds no new rules: `AGENTS.md` and
  `CONTRIBUTING.md` stay the source of truth. The project supplies no keys or
  compute; the guide says so and says which tool behaviours are unverified.
- Canonical append-only event source, event history API and resumable SSE
  stream (issue #741, API-6)
  ([ADR-0023](docs/decisions/ADR-0023-canonical-append-only-event-source.md)):
  a new `events` table in the Product Spine store, written in the same SQLite
  transaction as the run change it records (`admit_run` / `update_run` take an
  optional `event`), with a monotonic `sequence`, a unique `event_id`, a
  producer-supplied `occurred_at` (the store never reads a clock to invent
  one), a `principal`, a reserved `authority_class` vocabulary
  (`local_control`, `worker_observation`, `verifier_recommendation`,
  `human_decision`) and a `payload_digest`. New `GET /api/v1/events` (the
  `idkmesh-list-v0.1` envelope, ordered by sequence, opaque listing-scoped
  cursor, `limit` 1-200, exact-match filters `project_id`, `run_id`,
  `work_unit_id`, `event_type`; unknown parameters or an unknown `event_type`
  fail with 400) and `GET /api/v1/events/stream` (Server-Sent Events:
  `id` is the sequence, `Last-Event-ID` resumes with every later event, no
  header starts at the live tail, a `Last-Event-ID` beyond the newest event of
  the stream is `400 invalid_last_event_id` with `details.latest_sequence`
  rather than a silent skip, delivery is at-least-once so clients dedupe on
  `event_id`; browsers cannot use `EventSource` because the API token travels in
  a header it cannot set, so they must use `fetch` with a streaming reader).
  The `events` table is append-only by SQLite triggers (UPDATE and DELETE
  abort) and `event_id` is derived from `sequence`, not stored. The stream is
  bounded: `--max-sse-clients N` (1-64, default 8,
  its own limiter, beyond it `503 too_many_streams` + `Retry-After`), a 15 s
  heartbeat, a 300 s maximum lifetime after which the client reconnects with
  `Last-Event-ID`, and prompt end on drain; `operations.limits` on
  `GET /api/v1/status` reports `max_sse_clients`, `sse_heartbeat_seconds` and
  `sse_max_stream_seconds` (added as optional properties). New frozen schema
  `schemas/idkmesh-event-v0.1.schema.json` and `idkmesh events list --store
  PATH [--limit] [--cursor] [--project-id] [--run-id] [--work-unit-id]
  [--event-type] [--json]`. The store schema version is now 2: a version 1
  store gains the `events` table in place, and code that predates version 2
  refuses a version 2 store through the existing "newer than supported" check.
  Stated limits: only Product Spine `run create` and `run cancel` emit events
  (`run.created`, `run.cancelled`); the offline idempotent spine and the GitHub
  dispatch and status writers do not yet, so the history makes no completeness
  claim over every writer of the shared `runs` table; nothing prunes the table
  (a future pruner must answer `410 cursor_expired` rather than leave a silent
  gap); SSE is poll-based and bounded, one thread per stream, for the local
  development profile; WebSocket is deferred; the Control Tower UI timeline is
  not yet rebuilt on this source.
- Bounded service limits for the Control Tower development server (issue #742,
  API-7) ([ADR-0022](docs/decisions/ADR-0022-control-tower-bounded-service-limits.md)):
  a per-connection request timeout (default 10 s; a stalled request line or
  header drops the connection, a stalled body answers `408 request_timeout`);
  a concurrent-request cap (default 16) that answers `503 overloaded` with
  `Retry-After` and the standard error envelope instead of queueing;
  graceful drain (`503 shutting_down`, including `GET /readyz`, while
  `GET /healthz` still answers, and `serve_control_tower` waits up to 5 s for
  in-flight requests on shutdown); an explicit listen backlog of 16; and an
  optional `operations.limits` object on `GET /api/v1/status` reporting the
  limits actually in force (added in place to the frozen status schema as an
  optional property, which the ADR-0020 gate accepts). New flags
  `idkmesh control-tower --request-timeout SECONDS` (0.1-300) and
  `--max-concurrent-requests N` (1-1024). The reusable `RequestLimiter`
  and `limits_document()` live in `idkmesh/service_runtime.py`. The stdlib
  parser's existing bounds are adopted and pinned by tests: request line
  65536 bytes (414), header line 65536 bytes and 99 header fields (431;
  measured -- the stdlib counts the blank line ending the header block
  against its limit of 100), 2 MiB body, one request per connection.
  Not implemented, deliberately: `429` (a single local token gives no
  per-client identity to attribute a rate to) and a maximum SSE client count
  (no SSE stream exists yet, #741). The cap bounds request *handling*, not
  accepted connections, and `gate-audit-ui` and the steward UIs are not
  hardened by this change.

- `tools/schema_compat_check.py` (issue #737, API-2's sixth and last unmet
  CI requirement, "backwards-compatibility diff check for stable v1
  objects") ([ADR-0020](docs/decisions/ADR-0020-schema-backward-compatibility-gate.md)):
  a required PR Gate step that fails on a breaking in-place edit to an
  already-shipped `schemas/*.json` file -- a property removed, a `required`
  set changed in either direction, `additionalProperties` changed, or a
  leaf subschema changed outside two recognized widenings (`enum` gaining
  values, `type` gaining alternatives). Verified against this repository's
  own git history: it correctly flags the two real in-place breaking edits
  already on `main` (`work-unit-v0.2.schema.json`,
  `evaluator-plan-v0.2.schema.json`, both predating this gate) and raises
  nothing else across every schema file's full commit history.

- `tools/schema_migration_note_check.py` (issue #737, the "migration note"
  half of "breaking changes require explicit version bump/migration note";
  ADR-0020 enforces the version bump): a required PR Gate step that fails
  when a schema version successor ships without an explicit migration note
  in the `Schema migrations` section of `schemas/README.md` naming the exact
  file it supersedes. The ledger seeds all five successors already in the
  tree (`evaluator-plan` v0.2/v0.3/v0.4, `gate-audit-report` v0.2,
  `work-unit` v0.2) with mechanically derived notes, so a consumer of any
  older contract can always find what changed and how to move. Stdlib-only,
  wired into the PR Gate and `scripts/testkit.py integration`, with
  negative-path regression tests in `tests/test_schema_migration_notes.py`.

- `GET /api/v1/work-units`, `GET /api/v1/work-units/{work_unit_id}`, and
  `idkmesh work-unit list|status` (issue #739, `work-units` read surfaces)
  ([ADR-0021](docs/decisions/ADR-0021-derived-work-unit-and-project-read-models.md)):
  read-only WorkUnit views **derived on demand** from the WorkUnit reference
  (`id`, `version`, `digest`, `source_revision`) each stored Product Spine run
  already carries. One item per distinct id, ordered by id with an opaque
  keyset cursor scoped to this listing (a `run list` cursor is rejected with
  `invalid_cursor`) and an exact `project_id` filter that also scopes every
  `run_count`. Each item lists its distinct revisions with run counts, selects
  no latest revision, and returns no WorkUnit body -- none is stored; `digest`
  is the binding. An id no stored run references is `404 work_unit_not_found`,
  which says only that the retained runs do not mention it. Ids may contain
  `/`, so the whole path remainder is one literal id. Frozen by
  `schemas/idkmesh-work-unit-resource-v0.1.schema.json` and
  `schemas/idkmesh-control-tower-work-unit-response-v0.1.schema.json`; the
  list reuses `idkmesh-list-v0.1`. Adds `LocalMetadataStore.list_work_units()`
  / `get_work_unit()` and the matching `ProductSpineRunStore` methods. Not
  yet built: `/evidence` / `/decisions`, which wait on the content store of
  issue #740.

- `GET /api/v1/projects/{project_id}` and `idkmesh project status`
  (issue #739, `projects` read surface)
  ([ADR-0021](docs/decisions/ADR-0021-derived-work-unit-and-project-read-models.md)):
  a read-only project summary **derived on demand** from the stored Product
  Spine runs that name the project. No project record exists, so it is counts
  only: `run_count`, `runs_by_state` (every one of the 14 canonical run states
  present and zero-filled, so the shape is identical for every project), and
  the distinct `work_unit_count`. It computes no health or status rollup and
  selects nothing; list a project's WorkUnits with
  `GET /api/v1/work-units?project_id=`. A project no stored run names is
  `404 project_not_found`, which says only that the retained runs do not
  mention it. The whole path remainder is one literal `project_id` (it may
  contain `/`), and there is no project list endpoint. Frozen by
  `schemas/idkmesh-project-resource-v0.1.schema.json` and
  `schemas/idkmesh-control-tower-project-response-v0.1.schema.json`. Adds
  `LocalMetadataStore.get_project_counts()` and
  `ProductSpineRunStore.get_project()`. Not yet built: `/evidence` /
  `/decisions` (issue #740).

- `GET /api/v1/runs/{run_id}/attempts` (issue #739, `attempts` read
  surface): reads one run's worker/verifier attempts. `attempts` is now a
  reserved trailing path segment alongside `evidence` and `decisions`
  ([ADR-0019](docs/decisions/ADR-0019-run-subresource-suffix-reservation.md)):
  resolution is a pure function of the request path, never a lookup
  outcome, so a `run_id` ending in one of those three literal suffixes can
  no longer be read through the plain single-run `GET`. Frozen by
  `schemas/idkmesh-control-tower-run-attempts-response-v0.1.schema.json`.

- `GET /api/v1/runs/{run_id}/evidence` and `idkmesh run evidence RUN_ID --store
  PATH [--json]` (issue #739, API-4)
  ([ADR-0024](docs/decisions/ADR-0024-retained-evidence-read-and-mixed-store-run-reads.md)):
  serves the Run Evidence Report that the idempotent offline Product Spine
  already retains in the run row, so a Control Tower client can reconstruct a
  run and its evidence without repository files and without supplying the
  evidence document. It is digest-verified and fail-closed: the run projection
  must be a valid Product Spine run and `canonical_digest(report)` must equal
  `evidence_report_digest`, otherwise the response is `500
  evidence_integrity_error` and the report is never served. The report is
  returned as retained, never synthesised. `404 run_not_found` (no such run) is
  distinct from `404 evidence_not_available` (the run exists but retains no
  evidence, for example a run created by `idkmesh run create`). Frozen by
  `schemas/idkmesh-control-tower-run-evidence-response-v0.1.schema.json`.
  `GET /api/v1/runs/{run_id}/decisions` and the human-decision API (issue #740)
  remain unbuilt on purpose: no decision content is retained anywhere, and
  recording one needs an authenticated, accountable human or governance
  principal, which a local session token is not. That is a governance gate, not
  an implementation gap.
- Product Spine runs written by the idempotent offline spine
  (`product-spine-idempotency-result` rows) are now readable through
  `GET /api/v1/runs`, `GET /api/v1/runs/{run_id}` and `idkmesh run
  list/status` (the run-store restore accepts that kind and checks its
  `idempotency_request_digest` against the atomic record).

### Fixed

- Strict-JSON parsers are now total on pathologically nested input (issue #745,
  first fuzz slice; `tests/test_api_qualification_fuzz.py`). Deeply nested
  documents raised a raw `RecursionError` through the API client
  (`ProtocolError`), `idkmesh` CLI strict-JSON file loading (`ValueError`),
  Control Tower report parsing (`ControlTowerInputError`) and enterprise audit
  event replay (`invalid_event_json`); each now rejects with its documented
  controlled error.
- The IDKGraph Markdown index (`tools/idkgraph_markdown_index.py`) now skips a
  leading YAML front-matter block. Previously the last metadata line followed by
  the closing `---` parsed as a setext H2, so every page with front matter (all
  topic guides) got a metadata line such as `image: "/assets/idkmesh-social.png"`
  as its first heading and IDKGraph title. This unblocks adding search
  `description:` front matter to specifications and ADRs without corrupting
  their IDKGraph titles.
- Jekyll-rendered Markdown pages on the GitHub Pages site no longer share one
  meta description. At fca4e8c, 405 of 456 rendered pages fell back to `site.description`;
  `docs/_layouts/default.html` now derives a per-page description from the first
  real paragraph (front-matter `description` still wins and is untouched) and
  substitutes it into the `meta`/Open Graph tags. A local `github-pages` gem
  build went from 52 to 454 distinct descriptions across 456 pages. The same
  layout replaces the bare `WebPage` JSON-LD with a `TechArticle` + `WebSite` +
  `Person` + `BreadcrumbList` graph and adds a visible Home / Library breadcrumb.
  No `dateModified` is emitted: the legacy Pages build exposes no reliable
  per-page date. Documented in [`docs/PAGES_SETUP.md`](docs/PAGES_SETUP.md).
- Anchored `pattern`s in `schemas/` no longer accept a trailing newline
  (issue #963). Python's `re` matches `$` before a trailing newline, so every
  `^...$` pattern accepted `value + "\n"` — 180 patterns across 60 files,
  including SHA/digest/id identity fields where such values break exact-match
  equality downstream. Every end anchor now carries the `(?!\n)` guard
  ([ADR-0025](docs/decisions/ADR-0025-pattern-end-anchor-hardening.md)),
  which is a no-op under the ECMA-262 regex semantics JSON Schema specifies
  and makes Python validators agree with that contract;
  `tests/test_schema_pattern_anchors.py` proves the rejection for every
  pattern occurrence. `tools/schema_compat_check.py` recognizes exactly this
  transform as compatible and still reports every other pattern change as
  breaking.
- `GET /api/v1/runs` and `idkmesh run list` no longer fail for the whole page
  when the store also holds a row that is not a Product Spine run. The shared
  `runs` table also holds admission-only, execution-error and GitHub
  dispatch/status rows, and the old listing tried to restore every row. The
  listing now selects an explicit set of stored kinds
  (`product-spine-cli-run`, `product-spine-idempotency-result`)
  ([ADR-0024](docs/decisions/ADR-0024-retained-evidence-read-and-mixed-store-run-reads.md)),
  which also keeps keyset pagination consistent. The filter is by kind, not by
  exception: a row of a listed kind that fails to restore still fails loudly.
- Corrections to the still-unreleased event, evidence and service-limit code
  above, found by a read-only static review (no test has run against any of it
  yet), so they refine entries in this section instead of fixing a released
  behavior:
  - **`idkmesh run cancel` no longer destroys retained evidence.** Once
    offline-spine rows became readable, `cancel` could succeed on one and
    rewrite its row into the CLI shape, dropping the retained evidence report.
    `cancel` now refuses any run not created by `idkmesh run create` with
    `cancel_not_allowed`
    ([ADR-0024](docs/decisions/ADR-0024-retained-evidence-read-and-mixed-store-run-reads.md)).
  - **A concurrent double `run cancel` emits exactly one `run.cancelled`.**
    `LocalMetadataStore.update_run` gained `expected_state`, which makes the
    update conditional; the losing caller returns the already-cancelled run, or
    fails with `cancel_conflict` if the run changed to another state
    ([ADR-0023](docs/decisions/ADR-0023-canonical-append-only-event-source.md)).
  - **The store enforces the published event envelope**: `event_type`,
    `authority_class`, the UTC `occurred_at`, a 40/64-hex `source_revision`, and
    `event.run_id` equal to the run it is committed with are validated before
    anything is written. This also keeps the SSE `event:` line to the enumerated
    event types.
  - **Event history validation.** A blank `project_id`, `run_id` or
    `work_unit_id` is `400 invalid_filter` (it was reported as
    `invalid_limit`), and a cursor must be a bounded ASCII-decimal sequence
    (at most 18 digits) or it is `400 invalid_cursor` (a forged one used to
    raise an unhandled or mislabelled error, depending on its content).
  - **`GET /api/v1/runs/{run_id}/evidence` restores the row exactly as
    `status` does** before verifying the digest, so a foreign or swapped row
    answers `404 run_not_found` or `500 evidence_integrity_error`.
  - **Store faults are reported, not dropped.** A SQL error from the store (a
    locked, unreadable or corrupt database) is raised as `LocalStoreError`
    instead of a raw `sqlite3` error, so the service reports `store_error` and
    an open event stream ends with `: stream-ended reason=store-error`. Every
    store-backed read endpoint now answers a service `store_error` (and the
    evidence endpoint's `evidence_integrity_error`) with `500` through one
    shared status helper, instead of the earlier generic `400`; opening the
    database (including its migration) is guarded too, in the store's
    connection helper and in the events handlers, so an unopenable file gets a
    `500 store_error` body rather than a dropped connection.
  - **503 capacity responses are marked retryable.** `overloaded`,
    `too_many_streams` and `shutting_down` now carry `retryable: true`. On the
    stream path only `GET` uses the stream limiter, so `HEAD`, `POST` and the
    other write methods get `405` (not `503 too_many_streams`) when the stream
    cap is full, and `OPTIONS` advertises `Allow: GET`. The OpenAPI
    `Last-Event-ID` text now mentions the beyond-head `400`.

### Changed

- `tests/test_replay_run.py`'s five real-orchestration-replay tests (one
  spawning two real `replay_run.py` CLI subprocesses) moved from the `unit`
  tier to `slow`, per `docs/TESTING.md`'s "mark the worst offenders
  `sim`/`slow`, do not raise the budget" policy: together they cost about
  26 CPU-s of the unit tier's 90 CPU-s budget, which is exactly the margin
  `gate (3.13)` was failing into on a busier CI runner with zero test
  failures across three consecutive runs. They still run every night.
  `docs/TESTING.md`'s measured baseline re-measured and re-dated to match.

### Added

- `--state` and `--project-id` filters for `idkmesh run list` and
  `GET /api/v1/runs` (issue #739): bounded, exact-match, AND-combined
  filters per API Conventions v0.1 section 11. An unrecognized `state`
  fails closed with `invalid_state` rather than silently matching zero
  rows; any other/duplicate query parameter still fails with
  `unexpected_query_parameters`. `LocalMetadataStore.list_runs()` and
  `ProductSpineRunStore.list()` both gained matching keyword arguments.

- `idkmesh run list [--limit N] [--cursor TOKEN]` and `GET /api/v1/runs`
  (issue #739, second read-API slice): deterministic keyset-paginated
  Product Spine run listing, ordered by `run_id`. Adds
  `LocalMetadataStore.list_runs()` and `ProductSpineRunStore.list()`; the
  opaque cursor is a self-describing, service-issued token that fails
  closed (`invalid_cursor`) if forged or issued by anything else. Reuses
  the existing `idkmesh-list-v0.1` envelope and
  `idkmesh-product-spine-run-v0.1` item schema -- no new schema needed.
  The HTTP endpoint is the one Control Tower route that accepts query
  parameters (`limit`, `cursor`); every other endpoint still rejects any
  query string outright.

- `GET /api/v1/runs/{run_id}` on the Control Tower Local API (issue #739,
  the first slice of the API-4 read model): read-only Product Spine run
  state, served through the same `ProductSpineRunStore` application service
  `idkmesh run status` already uses, so the CLI and HTTP surfaces can never
  disagree. Opt-in: this server instance only exposes it when started with
  `idkmesh control-tower --product-spine-store PATH`; otherwise the endpoint
  returns 503. New schemas
  `schemas/idkmesh-product-spine-run-v0.1.schema.json` and
  `schemas/idkmesh-control-tower-run-response-v0.1.schema.json`, both
  validated in `tests/test_control_tower.py` against a real run created
  through the store, not a hand-written example. `run_id` may itself
  contain `/`; a future `/attempts`/`/evidence`/`/decisions` sub-resource
  will need to resolve that ambiguity explicitly rather than assume no real
  `run_id` ever contains one.

- `docs/architecture/API_CONTROL_PLANE_ARCHITECTURE.md` (issue #738): a
  checked-in dependency diagram grounding the domain/application-service/
  transport-adapter rule in the actual modules on `main`, a "resource/compute
  admission" row the resource ownership map was missing, and a dated,
  per-criterion verification pass against the document's own six-point
  "architecture completion evidence" bar. Not a full closure: criteria 1
  (connector HTTP endpoint) and 4 (event service) are blocked on work that
  does not exist yet.

- `schemas/idkmesh-readiness-v0.1.schema.json` (issue #737): freezes the
  shared `GET /readyz` readiness document built by
  `idkmesh/service_runtime.py:readiness_document()`. Validated against the
  function's real return value (with and without the optional
  `api_version` field) in `tests/test_service_runtime.py`.

- `schemas/idkmesh-control-tower-status-v0.1.schema.json` and
  `schemas/idkmesh-control-tower-inspection-response-v0.1.schema.json`
  (issue #737): the Control Tower Local API's `GET /api/v1/status` and
  `POST /api/v1/run-evidence/inspect` success responses now have canonical
  JSON Schemas, joining the already-schema'd `control-tower-snapshot-v0.1`.
  `tests/test_control_tower.py` validates the real `status_document()`,
  `success_document()`, and `error_document()` return values against their
  schemas directly, not only a hand-written example.

- `idkmesh local-loop <config>` (`idkmesh/local_loop.py`), the first CLI command
  wiring ROADMAP.md S4's R1 local product loop end to end: validates a
  two-attempt orchestration config and its WorkUnit, dispatches the two
  isolated attempts, routes each through independent verification, and
  captures the same replayable evidence bundle `experiments/replay_run.py`
  produces (run record, evidence report JSON + Markdown, raw per-attempt
  `VerificationResult` evidence, replay manifest), printing the two remaining
  human-gated next steps (record a decision, confirm replay) rather than
  performing them. Named `local-loop` rather than `run` because `idkmesh run`
  already names the unrelated Product Spine run-bookkeeping command, which
  explicitly never dispatches or verifies anything. Its heaviest test (three
  real subprocess spawns: the CLI, `experiments/replay_run.py`,
  `experiments/record_human_decision.py`) is marked `slow` and runs in the
  nightly tier rather than the unit tier, per `docs/TESTING.md`'s "mark the
  worst offenders `sim`/`slow`, do not raise the budget" policy.

### Changed

- `tests/test_cli_tools_help.py` runs each discovered tool's `--help` through
  `runpy` in the test process instead of spawning an interpreter per tool. The
  assertion is unchanged — every tool must still exit 0 and print help through
  its real `__main__` path with a real `argv` — but the tier no longer pays ~52
  process startups for a smoke test. `sys.argv`, `sys.path` and the working
  directory are restored afterwards, and modules loaded out of `tools/` are
  evicted so one tool cannot satisfy another's sibling import and mask a broken
  fallback. In-process execution does keep global state a subprocess discarded
  (`logging.basicConfig()`, `warnings` filters, `os.environ`, signal handlers,
  and `atexit` handlers now running at pytest exit); that is an accepted
  trade-off recorded in the test's own docstring.
- `docs/TESTING.md` re-measured and re-dated against `045f84d`. The published
  unit-tier row had drifted from 1643 to 3043 passed and from 3077 to 5790
  subtests, and the whole-suite count from 2027 to 3467. Nothing pins those
  figures — `tests/test_documented_tier_scopes.py` re-derives the marker
  expressions, not the counts — so they are re-measured by hand and carry a date.

### Added

- `idkmesh/enterprise_identity_github.py` (E3-B, issue #670): the first
  trusted authentication adapter for the E3 authorization kernel
  (`idkmesh/enterprise_authz.py`). Resolves already-authenticated GitHub
  actor claims (never issue/PR/comment text) against a maintainer-reviewed,
  versioned `enterprise-github-identity-binding-v0.1` table into an
  `ActorContext`, keyed primarily on the trusted numeric GitHub actor id.
  Fails closed on an unbound actor id, a login mismatch for a bound id, or
  a GitHub actor kind (human vs. bot) inconsistent with the bound
  `actor_type`. Revocation/expiry are left to `enterprise_authz.authorize`
  itself so the two do not drift.

- `idkmesh/enterprise_identity_oidc.py` (E3-C, issue #670): a trusted
  authentication adapter that normalizes already-verified enterprise IdP
  (OIDC/SAML/SSO) claims into the E3 authorization kernel's `ActorContext`
  (`idkmesh/enterprise_authz.py`). Keys a maintainer-reviewed, versioned
  `enterprise-oidc-identity-binding-v0.1` table on the composite
  `(issuer, subject)` pair, since a subject claim is only unique within its
  issuing IdP. Fails closed on claims already expired at evaluation
  time, claims not yet valid at it (a post-dated claim, or a caller whose clock
  precedes the claim's own `issued_at_epoch`), an unbound `(issuer, subject)`
  pair, or an `audience` mismatch against the binding's configured
  relying-party audience. `issuer`, `subject` and `audience` are opaque IdP
  strings compared byte for byte: a value carrying leading or trailing
  whitespace is refused rather than trimmed onto a bound identity. Revocation and the bound
  identity's own expiry are left to `enterprise_authz.authorize` itself, so
  the adapter and the kernel cannot disagree about what those mean. E3-D
  through E3-H remain open.

- `idkmesh control-tower [evidence-report.json]`, a dependency-free local
  Human Control Tower for Run Evidence Report v0.1. It shows human-attention
  conditions, claim/evidence/authority layers, attempt details, and a semantic
  background timeline through a versioned read-only `/api/v1/` surface.
  Summary/disagreement values are recomputed before display, reports that grant
  write/push/merge/automatic-selection authority fail closed, and both local
  browser UIs now share one loopback/security-header boundary. The API now
  also publishes OpenAPI 3.1 discovery and a frozen snapshot JSON Schema,
  supports generic/vendor JSON negotiation and headless token injection,
  emits deterministic content digests/ETags and read-only/version headers, and
  returns explicit method/version/query/media-type errors instead of relying on
  the base HTTP server's implicit behavior.
- `idkmesh/connector_routing.py` (issue #574, C1): a pure-stdlib, deterministic
  routing kernel that separates task requirements (`RoutingDecision`) from
  connector capabilities (`ConnectorProfile`) and resolves eligible connectors
  with non-compensating hard filters — human-required gate, capability tier,
  risk ceiling, external-processing policy, spend ceiling, secret
  availability, capacity — plus transparent lexicographic selection with
  stable tie-breaking. No live provider calls, GitHub mutation, secret
  materialization, persistence, or merge authority yet; this is the first
  bounded implementation slice of the Connector Control Plane
  (`docs/architecture/AGENT_MODEL_CONNECTOR_CONTROL_PLANE.md`).

- A dependency-free local browser GUI for the installable gate-audit diagnostic,
  launched with `idkmesh gate-audit-ui [input.json]`. It binds only to
  `127.0.0.1`, reuses the CLI audit engine, shows panel and verifier metrics,
  seeded-probe breaches and provenance, and exports both JSON evidence and a
  Markdown summary. The local API requires a per-session token and JSON content
  type and rejects non-loopback Host headers; verdict data is not uploaded to a
  hosted IDKMesh service.
- `idkmesh gate-audit --bootstrap` (issue #520): a deterministic candidate-level
  nonparametric bootstrap confidence interval for panel error, mean verifier
  accuracy, mean pairwise error correlation and effective votes. Resamples whole
  candidate rows, never verifier cells, so cross-verifier dependence survives
  resampling. Opt-in only — the default report stays byte-identical
  `gate-audit-report-v0.1`; `--bootstrap` switches the emitted schema to the new
  `gate-audit-report-v0.2` (`schemas/gate-audit-report-v0.2.schema.json`,
  `idkmesh/gate_audit_uncertainty.py`). Documented in
  `docs/specifications/GATE_AUDIT_V0_1.md` under "Finite-sample uncertainty",
  with a committed, test-regenerated example at
  `examples/gate-audit/gate-audit-report-v0.2.example.json`.
- `actions/gate-audit/action.yml` now exposes the `--bootstrap` CLI flag
  (issue #520) as opt-in `bootstrap`, `bootstrap-replicates`,
  `bootstrap-seed` and `bootstrap-confidence-level` inputs, defaulting to
  `bootstrap: "false"` so the action's default output is unchanged. Covered
  by a new self-test step in `gate-audit-action-selftest.yml` asserting the
  action's output matches the committed `gate-audit-report-v0.2.example.json`
  (float-tolerant, matching the existing cross-Python-version comparison in
  `tests/test_gate_audit_uncertainty.py`), plus a second step passing
  non-default numeric parameters and asserting the interval actually changes,
  so the three numeric inputs cannot become decorative. The action validates
  the group rather than discarding it silently: `bootstrap` must be exactly
  `true` or `false`, the three parameters require `bootstrap: "true"` (matching
  the CLI's own rejection of that combination), and `bootstrap-replicates` is
  capped, because the action is consumed by third-party workflows and the
  bootstrap's cost is linear in the replicate count while the CLI enforces only
  a floor. `tests/test_ci_trigger_scope.py` pins the four inputs, their CLI
  flags, the self-test's use of them and those three guards on the required PR
  Gate, since the action's own self-test is path-filtered and not required.

- `.github/workflows/nightly-full-suite.yml`, running the complete suite — the `nightly`
  tier, everything `unit` excludes included — on a daily schedule (plus `workflow_dispatch`),
  matrixed across Python 3.11/3.13 to match PR Gate. A failure here means the research
  content regressed, not that a specific pull request is unsafe to merge.

- `tests/test_resource_compute_bindings_live.py`, evaluating the checked-in compute
  authorization against the current date. `config/resource-compute-bindings.json` carries
  `reviewed_at` plus `max_age_days` so an unreviewed authorization stops authorizing, and
  `scripts/resource_compute_admission.py` enforces it — but the only surface that ran the
  real files, `.github/workflows/free-resource-plan.yml`, pins `--today` to keep its example
  assertion reproducible, and the existing unit tests use synthetic fixtures. A frozen clock
  never reaches an expiry date, so the project could have arrived at a day where admission
  admitted zero concrete offers with every check still green. Measured on this tree: the sole
  binding and its supporting evidence both age out on 2026-09-27, after which real admission
  returns `admitted=0` while the pinned workflow continues to pass. The test also pins the
  structural invariants — every binding resolves to a registry resource, no enabled binding
  points outside `DIRECT_COMPUTE_KINDS`, and none names a resource holding repository-write
  or merge authority. That last one guards a specific temptation: four of the five
  LLM-capable registry entries are agent-class, so widening that constant is the quickest
  way to make them routable, and it would hand an external data processor an execution path.

- `tests/test_documented_hook_snippets.py`, holding the copy-pasteable hook setup in
  `docs/TESTING.md` to what a reader can actually run: the settings block must parse as
  JSON and declare `hooks`, each shell block must parse under `bash -n`, each must go
  through `scripts/testkit.py` rather than calling pytest directly, and every script the
  settings block registers must be one the section shows the reader how to create. That
  last check is made against the section's prose with the fenced blocks stripped — run
  against the whole section it passed a renamed command happily, because the path it was
  looking for was still there, in the very block under test.

- `tests/test_documented_tier_scopes.py`, comparing the tier scopes `docs/TESTING.md`
  publishes against the marker expressions `scripts/testkit.py` actually passes to pytest.
  The expressions are read out of the script with `ast`, so a marker named only in one of
  that file's many comments cannot be mistaken for one that runs. The comparison is
  asymmetric on purpose: every expression a tier runs must appear somewhere in the
  document, and every expression the tier *table* publishes must be one a tier runs, while
  prose elsewhere stays free to show teaching examples. Absolute test counts are
  deliberately not pinned — those rot on a third of commits, the failure
  `tests/test_documented_test_counts.py` records at length; a marker expression changes
  only when someone moves a tier boundary on purpose.

- `tests/test_nightly_tier_has_something_to_run.py`, guarding the precondition that makes
  `scripts/testkit.py`'s nightly tier meaningful. That tier treats pytest's exit 5 — "no
  tests matched the marker" — as a pass, which is right for a repository with no simulation
  tests and wrong for this one, where `-m "sim or slow"` selects 369. If the tier markers
  were ever deleted or renamed, nightly would report success having run none of them. The
  scan reads `pytestmark` assignments with `ast`, so a marker named only inside a string
  literal is not mistaken for one that is applied.

- `scripts/free_resource_source_audit.py` and a scheduled workflow reporting freshness of
  every offer in the free-resource registry. `free_resource_planner.py` already drops an
  offer whose evidence has aged past its own `source.max_age_days`, but only when a planning
  run happens to ask; the audit makes the same arithmetic visible on a schedule, so an offer
  about to expire is seen before a planning run silently stops selecting it. It is read-only
  by construction — `permissions: contents: read`, and it never refreshes `checked_at`,
  edits the registry, opens a pull request, or selects an offer, because re-dating an offer
  without a human re-reading its terms is the failure `max_age_days` exists to prevent.
  `--fail-on {never,stale,expiring}` chooses whether freshness gates the run.

- `scripts/demo.py`, a narrated contract tour using the repository's real validators
  and committed synthetic fixtures: three positive checks and four rejection checks.
  It does not run an agent or prove live independence, accepted work, or merge authority.
- `tests/test_demo.py`, including regression checks that unexpected process/programming
  failures cannot count as expected contract rejections. Temporary fixtures keep the
  tests from modifying shared repository evidence.
- `.devcontainer/devcontainer.json`, including both `tests/` and `interop/tests/` in
  the editor's pytest discovery and an automatic fixture demo on attach. Hosted
  environment availability and cost are not guaranteed by this configuration.
- `CITATION.cff` and this changelog.
- `actions/gate-audit/`, the composite Action integrated through PR 395, with an
  exact-head self-test checking report-byte identity and the authority disclaimer.
- Ignore rules for the private files that agents and editors leave in a working
  tree: `CLAUDE.md`, `GEMINI.md`, `.note*`, `.env*`, `*.local`, `.vscode/` and
  `.DS_Store`. None of these were ignored before, so a single `git add -A` would
  have published local configuration or secrets from this public repository.
  `AGENTS.md` is deliberately excluded from the rule and stays tracked.
- `tests/test_private_file_ignore_rules.py`, which asks `git check-ignore` itself
  what `git add` would do rather than parsing `.gitignore`, and asserts the
  `AGENTS.md` exception so a later tidy-up cannot quietly hide the contributor
  contract every coding agent reads.
- `tests/test_patch_verifier_singularity.py`, holding two invariants in the
  unfiltered suite rather than in a path-gated workflow: every
  `experiments/*_patch_verifier.py` is imported by the runner (parsed with `ast`,
  so a name in a docstring cannot fake dispatch), and every workflow reference to
  such a module names one that exists and is dispatched, unless the line asserts
  the module's absence.
- `docs/audits/2026-09-05-orphaned-v04-patch-verifier.md`, recording the trace and
  its re-verification against a later base.

### Changed

- `.github/PULL_REQUEST_TEMPLATE.md`'s closing convention now actually closes an
  issue on merge. The old `Closes on merge (leave blank unless the merge should
  close it):` field never linked anything: GitHub only recognizes a closing
  keyword immediately beside the reference, and GitHub's own parse of the six
  pull requests recorded in issue 858 confirms it resolved no closing issue for
  any of them. The fillable line is now a bare `- Closes:` that takes references
  and nothing else, with the instructions moved into the surrounding prose.
  `CONTRIBUTING.md` and the Draft PR steward's generated body carry the same
  field, and a test pins the steward to it so the two cannot drift again.
  `tools/closing_keyword_guard.py` recognizes the new line as its one sanctioned
  opt-in, and the exemption is scoped to lines carrying nothing but references:
  the previous prefix match would have let an opt-in line shield an unrelated
  closing keyword written beside it, which GitHub would still have acted on.
- `.github/workflows/jules-dispatch.yml` also wakes its reconciliation path on a
  successful `PR Gate` completion (issue 834), so a verification slot freed when
  the gate's matrix jobs leave the active set is reclaimed within minutes instead
  of at the next half-hourly tick. The trigger is a trusted default-branch
  `workflow_run` that consumes nothing from the run that woke it; it fires only
  for pull-request-derived, same-repository gate runs, because `PR Gate` also
  triggers on pushes to `main` (an unconstrained trigger would become a second
  dispatcher control-plane push recovery path, which `AGENTS.md` reserves to the
  router) and on fork pull requests (which would let any unprivileged
  contributor wake this secret-bearing workflow at will); failed and cancelled gates do not start it; the 12/8 Actions backpressure ceilings,
  provider concurrency, review reservations, and the single `jules-dispatch`
  concurrency group are unchanged, so the wake-up can free a slot but never
  admit past a cap. `tools/check_jules_contract.py` pins the source workflow,
  the success-only conclusion, the pull-request-derived and same-repository
  constraints, the reuse of `--reconcile --dispatch`, and the single concurrency
  group. The contract checker and the equivalent test now strip YAML comments
  before matching, because every structural rule is a substring match and a
  commented-out trigger still contains the text the rule looks for -- a
  commented-out `workflows:` filter with `types: [completed, requested]` added
  passed both before this change. The `push` rule now inspects the parsed `on:`
  block for a `push` key in either YAML form, closing a flow-mapping evasion. `docs/operations/JULES_AUTOMATION.md` records the
  path and the cases where it is silently skipped, since it is a latency
  optimization over the 30-minute schedule and never a guarantee.

- `.github/workflows/pr-gate.yml` no longer runs the complete, unfiltered suite as its
  required check. It ran `python -m pytest -q` directly — every `sim`/`slow` simulation
  and sweep test included, synchronously, blocking every merge, on two Python versions —
  contradicting `docs/TESTING.md`'s own stated size-and-budget model (unit tests gate the
  commit; the long tail runs elsewhere) and the claim that "CI executes the same code
  path" as the local tiers, which was false: nothing in CI ever called
  `scripts/testkit.py`. It now runs `scripts/testkit.py unit`, the same fast tier a
  contributor runs locally with `make test`, plus the same explicit
  `scripts/check_links.py` step as before (`tests/test_ci_local_gate_parity.py` requires
  that step stay separate and stdlib-only, so it isn't folded into the tier call). The
  complete suite still runs, on a schedule, in the new `nightly-full-suite.yml` above.

- 27 workflows that install Python dependencies now cache pip's download cache via
  `actions/setup-python`'s built-in `cache: pip`, keyed on `requirements-phase0.txt`
  (`requirements-interoperability.txt` too, for the one workflow that installs it). None
  of the 53 workflows in this repository cached anything before; every run reinstalled
  every package from PyPI from cold.

- The unit tier's CPU budget is back under its 90 CPU-s ceiling with real headroom. The
  suite kept growing since the tier was last calibrated, and on 2026-09-19 it measured
  99.5 CPU-s — over budget, though the gate's own summary line printed `PASS` (a separate,
  pre-existing bug: see `fix: stop the local gate printing PASS on a run that exits 1`).
  20 tests across 8 files that were individually the most expensive in the tier — mostly
  simulation-adjacent evidence/parity/sweep checks in `tests/test_e020_quorum_frontier.py`,
  `tests/test_e027_defect_propagation.py`, `tests/test_e028_latent_defect_dimension.py`,
  `tests/test_e031_learned_goal_filter.py`, `tests/test_e036_adversarial_contributors.py`,
  `tests/test_r1_scaling_reference.py`, `tests/test_r2_factor_sweep.py`, and two
  meta-tests in `tests/test_documented_test_counts.py` that shell out to `unittest`
  discovery and pytest collection as subprocesses — are now marked `@pytest.mark.slow`
  and run in the `nightly` tier instead. Marked per test method, not per file or class:
  every one of these files carries dozens of other tests that were already fast and stay
  in the unit tier. Measured after the change: 32.3 CPU-s, 36% of the ceiling. Per
  `docs/TESTING.md`, the budget itself was not raised.

- `idkmesh gate-audit` now fails closed on malformed or ambiguous input and output
  boundaries instead of emitting tracebacks, unreadable JSON, or silently losing
  evidence. The hardening rejects duplicate JSON keys, non-finite JSON numbers,
  boolean quorums, malformed probe metadata, and unsafe input/output path collisions;
  tolerates a UTF-8 BOM; reports encoding/path failures as actionable CLI errors; and
  serializes reports with strict JSON semantics. The bundled happy-path example and
  its documented measured result remain unchanged.

- `docs/TESTING.md` stops presenting a local setup as repository content. Its automation
  section described `.claude/settings.json` and two hook scripts as though a contributor
  could open them; `.gitignore` excludes `.claude/`, deliberately, because it holds
  per-agent configuration and personal notes, so those files are in nobody's checkout and
  no `git pull` will bring them. The section now says so and reproduces all three files in
  full, which is the only way the page can hand them over. Its verification claim is scoped
  to match: the snippets were checked against a deliberately failing test — green tree exit
  0, red tree exit 2 with the failure on stderr, `"stop_hook_active":true` exit 0 so an
  unfixable failure blocks once instead of looping — in the checkout where they were
  authored, which the suite cannot re-check for a file it does not contain. The section's
  counts were re-measured too: 418 tracked `.md` files, not 398, and 1320 tracked files
  (~29 MB), not 1232.

- `scripts/testkit.py` no longer prints `PASS` on a run that exits 1. A tier fails for two
  independent reasons — red tests, or a blown CPU budget — and the previous fix routed the
  exit code and the result cache through `tier_passed` so they could not disagree. The
  status word on the summary line was a third consumer and kept reading `result.ok`, so a
  green suite that overran its ceiling printed
  `[testkit] unit: PASS in 100.0s wall / 100.0s cpu (budget 90 cpu-s)` and then exited 1.
  The `BUDGET EXCEEDED` explanation goes to stderr, which a hook capturing the streams
  separately, a CI log pane, or `--quiet` need not show beside stdout — so the one line a
  human was guaranteed to read was the wrong one. All three now derive from `tier_passed`,
  and `tests/test_testkit_budget_cache.py` asserts the printed word against the exit code
  across all four green/red x under/over-budget combinations.

- The unit tier's budget headroom is recorded honestly in `scripts/testkit.py`. The comment
  above `BUDGETS` still described a ~36 CPU-second suite with roughly 2.5x headroom; the
  suite has grown from 870 tests to 1865 and the tier measured 65.0 CPU-s on 2026-09-10,
  which is 72% of the 90 CPU-s ceiling. Recorded, deliberately not acted on: the documented
  response to a tight budget is to make the suite cheaper, never to raise the number.

- `docs/TESTING.md` no longer misstates what the gates run. Four claims had drifted, two
  of them wrong on the day the document landed. The unit tier's scope was published as
  `-m "not sim"` while the code it describes has always run `-m "not sim and not slow"`,
  so the column a contributor reads to learn what their pre-commit gate covers named a
  filter no tier uses. The prose asserted that `nightly` is equivalent to `integration`
  because no test carried `@pytest.mark.sim` — while the baseline table one section above
  it already recorded 369 deselected tests. 311 tests carry `sim` today and
  `-m "sim or slow"` selects 369, every one of which runs only in the scheduled tier. The
  measured baseline was re-taken on 2026-09-10: 1865 collected, 1494 passed / 2 skipped /
  369 deselected / 3000 subtests, 65.0 CPU-s against a 90 CPU-s budget, on 4 cores at load
  average 1.02 — recorded because the document's own argument for CPU-seconds is that a
  figure without its load is not comparable to one taken elsewhere.

- Seven more guards fail when they inspect nothing. An AST audit of `tests/` found every
  test that asserts inside a loop over a discovered set — a glob, a directory listing, a
  regex scan — with no check that the set was non-empty. Each now counts what it inspected
  and fails on zero: SHA-pinning of external actions (13 today), sitemap `lastmod` and
  `priority` (325 entries each), the sim-module test list (25), starter-task rendered links
  and blob-root targets, and catalogue path references. Without the counter, a pattern that
  stops matching turns the check into a silent pass.

- The workflow-hygiene guard's `cancel-in-progress` check fails when it inspects nothing.
  It iterated whatever its pattern matched, so a reformat as small as a space before the
  colon dropped it from 49 inspected values to 0 while the file still reported "4 passed" —
  only the subtest count moved, from 154 to 105, and nobody reads subtest counts. The
  sibling timeout check already counted its work; this one now does too.

- `scripts/testkit.py` caches the gate verdict rather than only whether the tests were
  green. A tier that passed its tests but blew its CPU budget exited non-zero while writing
  `"ok": true` to the result cache, so the next invocation on an unchanged tree
  short-circuited to "cached pass" and exited 0 — a failed gate turning green on the second
  run, which disarms the budget for as long as nothing changes. The exit code and the cache
  now both derive from one `tier_passed()` helper, so they cannot disagree.
- `tests/test_testkit_budget_cache.py` guards that: the tier verdict, the cache contents
  after a budget failure, the second-run short-circuit, the `auto` tier sharing it, and that
  a Markdown, YAML or Python edit each move the cache fingerprint.

- The scheduled-delay note on the free-resource audit is corrected. It quoted a 12-run
  sample min/max as a predicted window of "10:15–11:30 UTC"; the next scheduled run started
  at 11:31:34, 94 seconds outside it. A sample min/max is not a bound — the chance the next
  observation falls outside n prior ones is roughly 2/(n+1) — so the note now gives the mean
  (4.6 h over 21 runs of three workflows) as the expectation and says plainly that a run
  later than any yet seen is not a fault either.

- The free-resource audit's `schedule:` block records that its cron time is nominal.
  Measured over 12 scheduled runs of two unrelated workflows on 2026-09-10, GitHub started
  them 3.85–5.15 h after their cron expression (mean 4.49 h), so this job is expected around
  10:15–11:30 UTC rather than 06:23, and its absence at the nominal minute is not a fault.
  Re-tuning the expression cannot move the start; the delay is on GitHub's side.

- The free-resource freshness report is written to the GitHub job summary, not only to the
  step log. `--fail-on stale` turns the run red once evidence has *already* aged out, but
  the warning window — the state this audit exists to catch — lands on a run that is green,
  and nobody opens the log of a green run. The report now appears on the run page itself,
  with a note that a WARN line means our recorded reading is ageing, not that anything
  expires at the provider. The step captures the report before re-raising the tool's exit
  status, because the tool prints in full and then exits non-zero; summarising only on
  success would drop the report exactly when it matters most.

- The free-resource audit's per-offer date fields are named for whose clock they are on:
  `expires_on` and `days_until_expiry` become `evidence_stale_on` and
  `days_until_evidence_stale`. Both are `source.checked_at + source.max_age_days` — the day
  *our* recorded reading of an offer's terms ages out — and neither says anything about the
  provider; this registry holds no expiry date for any offer. The old name was read as a
  provider deadline within an hour of shipping, and a reviewer nearly reported a free tier
  as lapsing the next day. Renamed now because the only consumer is the tool's own tests
  and no schema pins the output, so the cost will never be lower.

- The open-model benchmark probe reports the model it actually ran, instead of naming one
  from constants in its own source. Identity is now resolved from the producer image's
  recorded digest: an unregistered digest is rejected rather than relabelled, a missing
  identity block is a harness failure, and an expected-digest mismatch aborts. The
  fingerprint covers file names as well as bytes, so swapping two weight files changes it.
- `tests/test_open_model_provenance_binding.py`, including a regression guard asserting the
  probe's source carries no `MODEL_NAME`, `MODEL_REVISION` or written-in manifest id — the
  host cannot observe those, so it may not assert them.

- `tests/test_example_contract_coverage.py` checks that every file named in a
  `NO_SCHEMA_CONTRACT` exemption reason still exists. Those reasons are prose —
  "validated in code by X", "consumed by X" — and prose is not checked, so renaming
  or deleting X silently turned the justification false and left the example with no
  coverage and no record of having lost it. The assertion stops at existence on
  purpose: `idkmesh/gate_audit.py` validates the panel-votes example without naming
  it, because the test is what loads the file and passes it in, so requiring the
  mention would fail a true claim.

- `tests/test_calibration_path_filter.py` reads a `paths:` filter written in any valid
  YAML spelling. Its first parser matched only double-quoted sequence entries, so a
  single-quoted or bare block parsed to nothing and every watched file was then reported
  as unwatched — a purely cosmetic reformat produced a failure that blamed the workflow.
  The same flaw in a one-off script over-counted a repository-wide survey threefold, so
  the parser now also fails loudly if a filter parses to zero entries rather than
  treating an empty result as a finding.

- The GitHub Pages build works again. `docs/architecture/REPOSITORY_MATHEMATICAL_PORTFOLIO_CONCURRENCY.md`
  documented a GitHub Actions concurrency expression inside a `yaml` code fence.
  Jekyll expands Liquid delimiters before Markdown runs, so the fence did not
  protect it: Liquid read the Actions interpolation as one of its own variables,
  found no terminator, and failed the deployment for the entire site. Six
  consecutive Pages builds failed from 2026-09-09T23:53Z, 7307b41 through
  c798726, while every repository test stayed green.
- `tests/test_pages_liquid_safety.py` fails on any unwrapped Liquid delimiter in
  published Markdown, on an unbalanced raw region, and on the scan finding almost
  no files — the last so the check cannot pass vacuously.

- The ACE growth controller no longer lets an unnamed event vote. Its dispatch chain
  seeded `q`/`d`/`r` at 0.05 before branching and had no terminal `else`, so any event
  it does not name — `workflow_dispatch` today, and any `schedule:` added later — fell
  through carrying those seeds. Since `credit` selects the controller's mode (EXPLORE
  at 2, GROW at 8), such an event both scored and opened its own row in the published
  counts table. Unnamed events are now typed `<event>:reconcile` and score zero;
  scoring for every named event is unchanged.
- `tests/test_ace_unnamed_event_credit.py`, which fails if the terminal `else` is
  removed, if it awards any credit, or if the pre-branch seed becomes zero and leaves
  the guard proving nothing.

- `Task 001 canonical v0.4 calibration` now watches the files it actually reads.
  The calibration runs against the checked-out pull-request head, but its `paths:`
  filter listed only the two calibration tools — so `requirements-phase0.txt`,
  `experiments/evaluator_plan_runner.py`, `experiments/transition_patch_verifier.py`
  and `tests/test_patch_evaluator_transition_v04.py` could all change without the
  calibration that certifies them ever running.
- `tests/test_calibration_path_filter.py` derives that dependency set from the
  workflow's own steps rather than from a second hand-maintained list, and also
  fails if the filter names a file that no longer exists.

- README introduces the synthetic contract demo with virtual-environment setup and
  links the existing contributor invitation. Installation time is environment-dependent.
- Support and issue-template entry points route open-ended questions to Discussions.
- The newer CONTRIBUTING.md instructions from PRs 405 and 408 are preserved rather
  than replaced by another setup sequence.

### Removed

- `experiments/transformation_patch_verifier.py`, the pre-#171 spelling of the v0.4
  patch verifier. It was imported by nothing after #171 rewired dispatch to
  `transition_patch_verifier.py`, but a later commit restored it, so
  `Task 001 canonical v0.4 calibration` failed its provenance guard on every pull
  request touching its paths — seven consecutive runs. No calibration result is
  retracted: dispatch always reached `transition_patch_verifier`. What was wrong was
  the evidence trail, since a `py_compile` step named the orphan as "the calibrated
  evaluator path" and the workflow's `paths:` filter watched it, so editing the
  module the run actually depends on did not trigger the run.

## [research-preview-2026-08-29] - 2026-08-29

First public research-preview snapshot, published as a prerelease. See the
[release notes](https://github.com/MSKazemi/idkmesh/releases/tag/research-preview-2026-08-29)
for the Work Unit, ResultManifest, EvaluatorPlan and VerificationResult foundations,
repository/branch observatories, bounded recommendation layers, synthetic experiments,
and CI security surfaces.

This is research software, not a production-ready distributed agent platform. The
release notes preserve its evidence and independent-review limitations.

[Unreleased]: https://github.com/MSKazemi/idkmesh/compare/research-preview-2026-08-29...main
[research-preview-2026-08-29]: https://github.com/MSKazemi/idkmesh/releases/tag/research-preview-2026-08-29
