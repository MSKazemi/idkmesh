# Changelog

Notable changes are summarized here; this is not an exhaustive commit log.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). IDKMesh is
pre-1.0 research software and does not yet follow semantic versioning: contracts under
`schemas/` carry their own explicit versions (for example `work-unit-v0.2`), and those
versions, not the release tag, are what downstream code should depend on.

This file starts at the first public release. Earlier changes remain in git history
and the release notes for that tag.

## [Unreleased]

- Test suite CPU (refs #745): `tests/test_cli_help_examples.py` built the full argparse
  parser ~100 times (now twice, in `setUpClass`, with help text cached per parser), and
  `tests/test_two_attempt_adapter_registration.py` / `tests/test_local_loop_tutorial.py`
  re-ran `Draft202012Validator.check_schema` on the same unchanged repository schemas on
  every verification (now once per schema file state, through a test-scoped wrapper around
  `local_verifier.load_schema`, restored after the class). Process CPU for the three files
  drops from about 6.3 + 3.3 + 3.7 to 0.3 + 0.4 + 0.6 CPU-seconds. No test, subtest or
  assertion was removed (27 tests and 139 subtests before and after); instance validation
  still runs in full on every call, and no production code changed.
- github: `idkmesh github-authority-audit` runs the C10 authority-alignment audit on local files (refs #598). `--bindings` takes an `enterprise-github-identity-binding` table (parsed by the real `parse_identity_binding_table`), `--trusted-actors` a new `idkmesh-github-dispatch-trusted-actors` document (parsed by `parse_dispatch_trusted_actors_document`, which delegates every semantic check to `GitHubDispatchAuthorizationPolicy`); optional `--scope TENANT/PROJECT`, `--now-epoch N` and `--json`. Strictly read-only (no network, secret, clock read or write) and never prints login text, including in input errors. Exit 0 with no `error` finding, 1 with at least one, 2 with empty stdout for an unreadable or invalid input; JSON is compact with sorted keys. No workflow or CI step is added: wiring the audit into CI is a separate reviewed change. See the [alignment spec](docs/specifications/GITHUB_AUTHORITY_ALIGNMENT_V0_1.md). Tests: `tests/test_github_authority_audit_cli.py`, `tests/test_cli_help_examples.py`.
- API storage CLI (refs #750): new `idkmesh api-storage` verb group over `idkmesh/api_storage_ops.py`:
  `plan-migrations`, `apply-migrations`, `plan-retention`, `backup`, `verify-backup` and `restore`.
  Anything that could write is a dry run unless `--apply` is given. `restore` never overwrites an
  existing target and refuses symlinks; `plan-retention` only plans (it needs `--decisions-store` or an
  explicit `--assume-no-decisions`, so a typo cannot make decided evidence look unreferenced).
  Exit codes: 0 ok, 1 integrity finding (digest, manifest, edited migration history), 2 refused or
  unusable request; failures are one `error: CODE: message` line (or a JSON object with `--json`),
  never a traceback. Library additions: `load_migration_steps()` (`NNNN_name.sql` directories),
  `plan_backup()` and `plan_restore()` dry runs that share the real path checks.
  `tests/test_api_storage_cli.py` drives the real CLI against temp dirs. No existing store is moved
  onto the runner, nothing applies or schedules retention, and there is no HTTP route or
  network-profile adapter; issue stays open. See
  [API Storage Profiles](docs/specifications/API_STORAGE_PROFILES_V0_1.md#command-line).
- github: offline Pages-disabled fallback bundle (C14-H, refs #609). New `idkmesh/github_pages_fallback_bundle.py` and `idkmesh pages-fallback` render the same validated public-safe projections that `pages-site` renders as HTML into a self-contained directory of escaped Markdown, the byte-identical public JSON, per-run outage locators and a SHA-256 `MANIFEST.json`. Output is deterministic and fails closed; untrusted identifiers are entity-escaped against Markdown/HTML/autolink/mention/Liquid injection; the writer refuses traversal, symlinks and non-empty targets and never replaces anything; `--verify DIR` checks the file set, digests and a byte-for-byte re-render. No upload, network, GitHub call or workflow change, and the bundle is a view, not canonical evidence. Wiring an Actions-artifact upload and an outage drill remain open. See [the fallback procedure](docs/operations/GITHUB_PAGES_FALLBACK_V0_1.md).
- API observability: served Prometheus scrape route (refs #744). Control Tower now serves
  `GET /api/v1/metrics/prometheus`, the existing `render_prometheus_text()` exposition
  (`text/plain; version=0.0.4; charset=utf-8`), behind the same session-token, loopback-Host,
  stray-query (400), method (405) and `Accept` (406 unless text is allowed) gates as its sibling
  reads. The label set stays closed, the body is capped at 16 KiB and refused rather than truncated
  (`otel_metrics.render_prometheus_bytes()`), and a render failure such as an unsafe service label is
  a constant `500 metrics_unavailable`. Wired into `openapi.yaml`, the generated OpenAPI document, the
  status `endpoints` map, the access-log route vocabulary and the API docs. No OTLP push, rate-limit
  or Human Decision telemetry (those wait on #743/#740); there is no `ControlTowerClient` method
  because the client is JSON-only.
- Static connector driver listing over the Control Tower API (refs #580, slice C7-F remainder): add
  `GET /api/v1/connector-drivers` and `ControlTowerClient.list_connector_drivers()`. It serves only the
  static, secret-free registry descriptors (`kind`, `driver`, `version`), ordered by kind then driver id,
  through `connector_control_read.list_connector_drivers()` in the new
  `idkmesh-control-tower-connector-drivers-response-v0.1` envelope (schema, example, OpenAPI entry,
  error catalog row `driver_record_invalid`, authority-matrix row). The only registry constructible
  without live adapters is the offline fake-driver registry, so the envelope states
  `registry: "offline-fake"` and `live_adapters: false` rather than letting test doubles pass for live
  drivers. No store, probe, secret resolution, dispatch or provider call; GET/HEAD only, no query
  parameters, session token required; access logs record the static route. Not done (see
  `docs/planning/C7_CONNECTOR_CONTROL_FOLLOW_UPS_2026-10-14.md`): per-driver capabilities, latest
  probe state, mutating endpoints and the network auth boundary.
- API: generated TypeScript type declarations for the web client (refs #746). New stdlib-only
  `tools/generate_api_types.py` turns `openapi.yaml` and the JSON Schemas it catalogs into the
  checked-in `clients/typescript/idkmesh-api.d.ts` (one type per catalog schema and `$defs`
  entry, plus `IdkmeshApiOperations` keyed `"METHOD /path"`). Declarations only: no runtime code,
  no `package.json`, no publishing, no network. The output is a sound over-approximation (value
  constraints such as `pattern` and `if`/`then` are not encoded; the JSON Schema stays the
  authority); unsupported keywords make the generator exit 2 naming the schema, and it never
  emits `any`. `tests/test_generate_api_types.py` requires byte equality with a fresh
  regeneration, so the file cannot drift. Not type-checked with `tsc` (no toolchain in CI);
  `record_human_decision` and a runtime web client remain open. See the
  [API overview](docs/reference/API_OVERVIEW.md#web-client-types-typescript-declarations).

- Bootstrap into another checkout (refs #596): `idkmesh init --github --check|--apply` gains
  `--target DIR` (default: current directory). The target must be an existing, non-symlink directory
  with a `.git` marker; `--dry-run` rejects it; no `--force` exists, so conflicting files are
  reported and never overwritten. Regression tests cover cwd isolation, symlink/missing/non-Git/empty
  targets and a pre-existing user file. Live `dispatch`/`verify` remain fail-closed (#578, #597).
- github: offline C13-F/G Projects field planning and guarded apply (refs #608). New `idkmesh/github_project_sync.py` derives the run-state / verification / human-decision Project field values from a trusted canonical run snapshot (same mapping as the C13-E labels, so the two views cannot disagree), and applies a field plan through an injected writer idempotently: strict plan re-validation, trusted destination item ids, a canonical-digest re-read before every write that aborts on change, and permission/transport/store failures returned as results (messages never copied) rather than raised into WorkUnit execution. Manual Project edits are overwritten, never honoured. No GitHub transport, token handling, or workflow is added and no authority is granted; the live adapter and concurrency recovery remain open. See [Projects sync](docs/specifications/GITHUB_PROJECTS_SYNC_V0_1.md).
- github: `idkmesh release-provenance --statement` and `idkmesh/github_release_statement.py`
  (C14-G, refs #609): render a C14-F release record as an unsigned in-toto Statement v1 whose
  subjects are the release's artifact digests and whose predicate embeds the record, with fixed
  all-false signed/registered/SLSA/subjects-verified/correctness claims, strict validation, and
  no timestamps. Nothing is signed, registered, or verified; signing needs a CI workflow
  identity and is not done here.
- Enterprise conformance: release provenance is now exercised (refs #676, #674, #609).
  The last UNKNOWN scenario of `idkmesh doctor --enterprise-conformance` runs the real C14-F
  release-record builder and validator offline: an untouched record validates, while a swapped
  artifact digest, target commit or added artifact, a forged attestation / published-release /
  verified-artifact claim, a forged merge-authority grant (each with the record digest recomputed
  by the forger), an unlisted provider field, a malformed digest, a replayed run and a
  non-revision commit are all refused. The scenario is **WARN**, never PASS: tag, commit and
  artifact digests are caller-asserted and no signature, attestation, SBOM or build-provenance
  verifier exists to check real artifact bytes (#674). Negative controls turn it red for a
  validator that accepts tampering, one that rejects a genuine record, and a record that claims
  attestation. With no UNKNOWN or FAIL scenario left, the overall report is now **WARN** and the
  command exits 0; UNKNOWN or FAIL still exits 1. Not a SOC 2 / ISO 27001 / FedRAMP claim.
- API storage operations library (refs #750): add `idkmesh/api_storage_ops.py` with a
  checksummed forward-only SQLite migration runner (dry-run plan; one-transaction apply, so an
  error or a killed process leaves the previous schema; refuses edited history, ledger gaps,
  newer databases and unadopted legacy schemas), a pure retention planner that never expires a
  record tied to a Human Decision and never deletes anything, and a digest-bound
  backup/verify/restore procedure (atomic restore, no symlink following, stale WAL removal).
  `tests/test_api_storage_ops.py` covers these including a real `os._exit` crash mid-migration
  and tamper cases. Library only: no CLI/HTTP surface, no existing store migrated onto it, no
  network-profile adapter, claim/lease pruning or scheduled retention job; issue stays open.
  See [API Storage Profiles](docs/specifications/API_STORAGE_PROFILES_V0_1.md#storage-operations-library).
- Machine-readable API SLO contract and Prometheus text renderer (refs #744):
  `idkmesh/api_slo.py` pins the documented local-profile targets as data
  (`default_slo_contract()`, `schemas/idkmesh-api-slo-contract-v0.1.schema.json`,
  `examples/api/api-slo-contract.example.json`) with a fail-closed validator and
  pure evaluators for one measured interval, a consecutive-interval overload
  alert, and point-in-time saturation conditions. Malformed, restarted or
  too-short intervals are `unknown`, never "met"; sustained duration is reported
  as not evaluated. `otel_metrics.render_prometheus_text()` renders the validated
  metrics document as Prometheus exposition 0.0.4 with a closed label set, base-unit
  latency, rejection of unsafe service-identity labels, and the not-implemented
  rate-limit/Human Decision counters omitted. Both are library-only: no served
  `/metrics` route, network I/O, alert delivery or new dependency. #744 stays open
  for per-client rate limiting (#743) and Human Decision ingestion telemetry (#740).

- Opt-in bounded retry, lazy run pagination and an API overview for the Python client
  (refs #746): `ControlTowerClient` accepts an explicit `RetryPolicy` (2-5 attempts,
  deterministic exponential backoff capped at 30 s, server `Retry-After` honoured only up to
  the cap, injectable `sleep`) that retries only idempotent `GET` reads on transport failures
  and server-declared retryable 429/502/503/504 errors; the `POST` inspection, event
  streams, integrity/protocol failures and non-retryable API errors are never retried, and
  the default stays exactly one exchange per call. Errors now carry `attempts` and
  `retry_after_seconds`, results carry `metadata.attempts`, and `repr(client)` omits the
  session token. `iter_run_pages()` / `iter_runs()` add lazy page-capped walks (and
  `collect_run_pages()` is now a tuple over them). New `docs/reference/API_OVERVIEW.md`
  maps authentication (a local token, no scopes), every route, the schema catalog, the
  OpenAPI download and the Python client, and is drift-tested against the OpenAPI document
  and `schemas/`. Not built, and now stated as such: `record_human_decision` (blocked on
  #740), a typed TypeScript client, and package-index publication. Tests:
  `tests/test_api_client_retry.py`, `tests/test_api_reference_docs.py`.
- Single-connection read over the Control Tower API (refs #580, slice C7-F): add
  `GET /api/v1/connections/{connection_id}` and `ControlTowerClient.get_connection()`. It serves the
  same secret-free `idkmesh-connection-resource` projection as the list endpoint through
  `ConnectorControlReadService.get_connection()`, wrapped in the new
  `idkmesh-control-tower-connection-response-v0.1` envelope (schema, example, OpenAPI entry, error
  catalog rows `connection_not_found` / `invalid_connection_id`, authority-matrix row). Read-only by
  construction: no probe, no secret resolution, no dispatch or provider call, and reading a connection
  enables, admits or authorises nothing. The id must match the connector identifier grammar, which
  excludes `/` and `:` so the reserved `/connections/{id}:probe|enable|disable` verbs cannot be
  mistaken for ids; malformed ids fail with 400 without being echoed, legacy or id-mismatched rows
  fail closed with 500 `connection_record_invalid`, the session token is checked before any lookup, and
  access logs record the route as `/api/v1/connections/{connection_id}`. Not done (see
  `docs/planning/C7_CONNECTOR_CONTROL_FOLLOW_UPS_2026-10-14.md`): mutating HTTP endpoints, the network auth
  boundary, registry/driver listing over HTTP, and preview/evidence CLI convergence.
- GitHub authority alignment audit (C10, refs #598): add
  `idkmesh/github_authority_alignment.py`, a pure read-only audit that compares the GitHub
  identity binding table with the C5 dispatch trusted-actor list and reports unbound,
  login-mismatched, kind-mismatched, revoked, expired, out-of-scope and kernel-unbacked dispatch
  actors (plus a fail-closed drift warning). It grants no authority, is not yet run by any
  workflow, and does not cover CODEOWNERS/rulesets or cross-IdP principal linking. Specified in
  [GitHub authority alignment audit](docs/specifications/GITHUB_AUTHORITY_ALIGNMENT_V0_1.md).
  Tests: `tests/test_github_authority_alignment.py`.
- E3-E audited break-glass grant (refs #670): `idkmesh/enterprise_break_glass.py`,
  `schemas/enterprise-break-glass-grant-v0.1.schema.json` and
  `examples/enterprise/break-glass-grant.example.json`. A grant is a temporary role elevation for one
  human in one tenant/project: explicit incident id and written reason, a closed action set, risk and
  data-class ceilings (never `critical`, never `restricted`, never `manage_policy`/`audit_export`), a
  60 s to 4 h window capped by both parties' identity expiry, and a distinct human owner/admin approver.
  It can only change a `role_denied` outcome; the unmodified kernel still enforces scope, revocation,
  clearance, executor separation and high-risk distinct approval on the elevated actor, and grants are
  bound to the beneficiary's identity revision and the policy revision. Outcomes carry the grant digest
  for the audit ledger and the ALLOW code is `authorized_by_break_glass`. Offline contract and evaluator
  only: no grant store, approval workflow or revocation feed, and not yet called from dispatch/API paths
  (E3-F). 22 tests incl. adversarial cases and a ledger round trip.
- Authorized and audited Human Decision gateway for issue #740 (refs #740): the baseline
  authorization policy gains a distinct `decide` action (human actors only; roles `integrator`,
  `admin`, `owner`; effective risk `high` or above needs a distinct eligible human approver), mirrored
  in the authorization-decision and audit-event schemas, and
  `idkmesh/human_decision_gateway.py` puts it in front of the immutable decision service. For every
  attempt it validates the request shape, evaluates `decide` for the trusted `ActorContext` against the
  retained evidence digest (tenant isolation, role, actor type, clearance, revoked/expired identity,
  distinct approver), persists only on `allow`, and appends exactly one enterprise audit event
  (`denied`, `not_executed`, `failed` or `succeeded`; an idempotent replay is `not_executed`). It refuses
  before persisting when the audit writer identity cannot record the attempt. Known gap, documented: the
  decision store and audit ledger are separate SQLite files, so an audit failure after a persist surfaces
  `audit_unavailable` and the `succeeded` event is not retroactively written. Not built and still owned by
  #740: no HTTP route, CLI verb or OpenAPI path calls the gateway, because the live identity/policy
  enforcement (#670) and network security boundary (#743) it needs do not exist yet and the local
  session token is not a human principal. Tests: `tests/test_human_decision_gateway.py`.
- Network/multi-user API security profile, library only (refs #743): add
  `idkmesh/network_api_profile.py` and
  [`docs/specifications/NETWORK_API_SECURITY_PROFILE_V0_1.md`](docs/specifications/NETWORK_API_SECURITY_PROFILE_V0_1.md).
  `parse_network_profile` refuses a non-loopback bind unless TLS is declared as terminated by a trusted
  proxy, a real authentication adapter is named (the local session token is refused by name), the Host
  allowlist is explicit and limits are bounded; wildcard CORS, `null`/`http` origins, literal secrets and
  enabling break-glass are refused. `NetworkRequestGuard` adds peer/`X-Forwarded-For` trust, Host, Origin
  and request-framing (smuggling) checks; `ServiceTokenVerifier` is a digest-only, constant-time bearer
  registry with expiry, rotation and revocation; `RateLimiter` fails closed when its key table is
  saturated; `authorize_scope`/`append_authorization_audit` route endpoint scopes through the enterprise
  kernel and retain denials. Not wired into any listener: no network-facing endpoint is enabled, and no
  `ActorContext` adapter, TLS, cross-process revocation or `decisions:write`/`integration:*` action
  exists, so #743 stays open. Regression tests in `tests/test_network_api_profile.py`.

- Budget-split predictor for H4, synthetic evidence only (refs #981): add `sim/x8_budget_split.py` and
  record `experiments/X8-budget-split-predictor.md`. A deterministic stdlib predictor (A6) fits worker and
  verifier difficulty and a cross-dependence term from a pilot of `TaskObservation` records and chooses the
  `(attempts, reads per attempt)` split with the highest predicted verified value; it is scored on held-out
  simulated tasks against all-workers, 50/50 and all-verifiers, an oracle, a random allocation and a
  deliberately broken predictor, under a preregistered win/tie/loss rule. Over 32 scenarios it won in 16
  (every cheap-read scenario), tied in 14 and lost marginally in 2 (0.001 of verified value), so the
  issue's falsifier fires in half the grid; the cross term changed nothing measurable, the surface is
  biased low by about 0.007, and a pilot one fifth the size roughly doubles the error. The real-data test
  stays blocked on X6/X7; blind-spot routing (A7) is not built. Machine-readable result
  `experiments/results/X8-budget-split.json`; tests in `tests/test_x8_budget_split.py`.
- Marginal-evidence selector validated against a known synthetic truth (refs #693): add
  `sim/e051_marginal_selector_sweep.py` and record `experiments/E051-marginal-selector-sweep.md`. Seeded
  verdict matrices from a stated generative model are run through the repository's unmodified
  `idkmesh.marginal_evidence_benchmark.build_selection_plan`, and the marginal-effective-vote selector and
  its four baselines are scored against a 40,000-task population oracle (16 regimes, 7 design sizes up to
  1,280 rows, 100 replicates each; eight regimes were added post hoc and are flagged). Negative result for
  the shipped selector on this model: of 11,200 frozen selections it made 1,548 and one was a helpful
  candidate, it chose only the two least accurate candidates (its effective-vote criterion rises as
  candidate accuracy falls), and its abstentions did not track redundancy (79% when nothing helps, 88% when
  something does), while the accuracy, family and correlation baselines chose a helpful candidate in 65% to
  73% of cases; the minimum-correlation rule beat highest-accuracy where an accurate candidate is largely
  redundant. Duplicate and panel-mimic controls are pinned by tests. Synthetic only: symmetric errors, one
  dependence shape, no significance test; the observed-cohort gate for issue 693 is unchanged and no
  shipped selector, schema, CLI verb or routing behaviour is modified. Machine-readable result
  `experiments/results/E051-marginal-selector-sweep.json`; fast tests plus a nightly `sim` re-derivation.
- Agent churn at a matched budget, synthetic mechanism evidence only (refs #22): add
  `sim/e050_churn.py` and record `experiments/E050-churn.md`. Each generation a fraction of agents
  (`0, 0.1, 0.25, 0.5, 1.0`) is replaced by fresh ones in E024's five arms at the same proposal budget,
  under a memory-loss model and a cold-start model, with the archive, elite pool, incumbent and
  consensus kept as shared state that survives every departure (so the comparison is about state
  placement, not people). E024's code and artifacts are unchanged; `f = 0` equals E024 row for row and
  the rebuilt aggregate matches the committed artifact by digest. Findings that undercut the archive:
  under memory loss the majority swarm's catastrophic seeds fall from 44 to 0, which removes the
  archive's reliability lead over it, and under cold start the archive loses 1.27 AUC at full churn
  while the scalar arm gains 2.42; no arm's mean-AUC lead changes sign, and four arms are unchanged by
  construction under memory loss. 152 p-values reported. State that leaves with its authors and
  correlated departures are listed as not measured. Machine-readable result
  `experiments/results/E050-churn.json`; fast tests plus a nightly `sim` check.
- Supported CLI verbs for replay and the human decision (refs #16): add
  `idkmesh local-loop-replay BUNDLE` and
  `idkmesh local-loop-record-decision EVIDENCE_REPORT --output PATH ...`, so a newcomer can
  replay a saved `local-loop` run and record an explicit decision without leaving the
  `idkmesh` command. Both delegate to the unchanged scripts `experiments/replay_run.py replay`
  and `experiments/record_human_decision.py record` by running their own `main`, so the report,
  exit codes (replay: 0 PASS, 1 diverged, 2 unusable input) and `ERROR:` text are the scripts',
  with the same path rules as `local-loop` (repository-relative, outputs under `results/`).
  Two script gaps are covered at the wrapper only: a mistyped file name inside a real bundle no
  longer replays that bundle's manifest, and an `--output` outside `results/` exits 2 instead of
  escaping as a traceback. Authority is unchanged: replay writes nothing, and the decision
  record is bound to the evidence-report digest with `canonical_state_write`, `git_push` and
  `merge` all `false`. `local-loop`'s printed next steps, `NEXT_STEPS.md`, the tutorial
  (`docs/LOCAL_LOOP_TUTORIAL.md`), the CLI reference, the capability reference and the module and
  as-built maps now name the verbs; `experiments/*.py` gained only an optional `argv` parameter on
  `main`. New in-process tests (`tests/test_local_loop_replay_decision_cli.py`), a tutorial test
  that runs the documented verbs, and `--help` Examples blocks for the three `local-loop` commands.
- Structural communication accounting for the R1 topology arms, synthetic mechanism evidence only
  (refs #13): add `randomness_lab/r1_communication_burden.py`, a downstream analyzer over the
  frozen R1 topology artifact that leaves the generator and every committed R1 artifact
  byte-identical, plus `docs/research/R1_COMMUNICATION_BURDEN.md` and a seeds 42 to 51 result. It
  counts messages per task from an explicit edge rule (flat 3N, role-specialized 2N+1, task-DAG
  3N; labelled structural, not measured bytes), reports structural replication and unproductive
  attempts, and fits success-per-message curves with seed-bootstrap intervals. Findings are
  mixed: success per message falls with N in all 27 groups, role-specialized wins per message
  mostly because its count is lower while succeeding less, and task-DAG is not better per
  message. Content-level duplicated work is not definable on the R1 traces (no candidate
  identity) and is reported as null; a communication budget and shared memory are still never
  varied, and the issue stays open.
- R1 per-signature marginal success post-processor (refs #30, #70): add
  `randomness_lab/r1_signature_marginals.py`, a read-only command that reads a saved
  `randomness_lab.r1_replay` report and emits, per structural signature, candidates
  analysed, independently verified successes, success rate and a Wilson 95% interval,
  which the preregistration requires and the replay never summarized. Pairwise failure
  correlations are copied unchanged, the input file's SHA-256 digest is recorded, and
  inconclusive candidates are reported as a count and never scored. It fails closed on
  malformed input and refuses synthetic-flagged input unless
  `--allow-synthetic-fixture` marks the output `evidence_class: synthetic_fixture`.
  `r1_replay.py` is untouched. No real corpus exists (readiness: 0 of 20 eligible work
  units), so there is no real R1 outcome. Documented in `docs/research/R1_REAL_RESULT_REPLAY.md`.
- Derived emergence measurements, synthetic mechanism evidence only (refs #22): add
  `sim/e049_derived_measurements.py` and record `experiments/E049-derived-measurements.md`
  (E048 stays reserved for the preregistered temporal holdout). It replays E024's `run_seed`
  with the same seeds, so no E024 output changes and the rebuilt aggregate matches the committed
  artifact by digest, and reports for the five arms: recovery time to an absolute utility bar
  (right-censored, first-passage and sustained), viable-niche coverage computed by one function
  over every arm's accepted trace, and proposals per verified improvement, with exact and
  bootstrap intervals and paired seed-level tests against the archive. Findings that undercut
  the archive: random search is close on first-passage recovery (86/100 against 100/100) but not
  sustained (12/100), raw viable coverage differs by 2.5 of 64 niches, and the cost-per-improvement
  lead holds under carry-over accounting only. Human attention, novelty, information gain and
  churn are listed as not measured. Machine-readable result
  `experiments/results/E049-derived-measurements.json`; fast tests plus a nightly `sim` replay.
- R1 real-corpus preregistration committed (refs #30, #70): add
  `docs/research/R1_REAL_CORPUS_PREREGISTRATION.md`, a copy of the preregistration
  that existed only as issue 70 comments (hypothesis H1, the paired-bootstrap
  `helps` / `hurts` / `uncertain` rule, the structural-quality-versus-diversity
  confounder, the 20-work-unit target and the 3 to 5 worker scale-up rule), with
  comment URLs and timestamps, the points the text leaves ambiguous, and the
  readiness gate's current blocked state (0 of 20 eligible work units). Linked
  from the R1 readiness page and the research index. It is a copy, not a new
  registration, changes no rule, and reports no result; the per-signature
  marginal-success reporting the comment asks for still has no producer.
- Research results ledger (refs #2, #13, #22, #30): add
  `docs/research/RESULTS_LEDGER.md`, one row per record indexed in
  `experiments/README.md`, each with an evidence class (`synthetic`,
  `public-observed`, `real-run` or `analytic`), a one-sentence headline that
  includes negative and falsifying verdicts, and the record's own verdict, all
  written from the record's own text. It states what it is not: no claim that
  many small agents beat one strong model, which has no real arm here (E029's
  0.5B model produced 0 of 60 judgeable candidates). A class-based
  `tests/test_results_ledger.py` fails when an indexed record has no row or two,
  a row uses a class or verdict outside the published sets, or a row names an
  unindexed record. Structure only; it cannot check a headline's faithfulness.
- Per-metric contract page (refs #86): added
  `docs/research/METRIC_CONTRACTS_V0_1.md`, one entry for each of the 22 production
  metrics and mechanisms (the repository-evolution signals, the live governor's
  `branch_health` and `homeostatic_potential`, the control-energy, replicator and priority
  composites, and the collaboration observables), each with assumptions, observables,
  uncertainty, prediction, baseline, failure modes and Goodhart risks, and human/security
  constraints. The page is read from the code, states where uncertainty is not modelled
  and that hand-authored uniform priors remain an open item, and is guarded both ways by
  `tests/test_metric_contracts.py`, which reads the metric keys by AST. The two existing
  metric pages gain a pointer to it; issue #86 stays open.
- Test suite CPU (refs #1128): the unit tier had crept over its 90 CPU-second
  budget on `main` (91.9 measured at near-idle load, 90.1 to 93.8 on the last three
  merges) and was failing `gate (3.13)`. Reclaim about 6 CPU-seconds without
  moving any guard out of the PR gate or raising the budget: the two tests that
  each parsed every file under `tests/` now share one scan per process
  (`test_nightly_tier_has_something_to_run`,
  `test_full_suite_jobs_install_requirements`), and the local-loop tutorial and
  adapter-registration tests run each documented command or orchestration once
  instead of per assertion. Mutation checks confirm each refactored guard still
  fails on the drift it exists to catch. Measured warm with `scripts/testkit.py
  unit --no-cache`: 88.6 CPU-seconds at load 3.6.

- Two-attempt orchestrator adapter registration seam (refs #4, #16): add
  `register_adapter`, `unregister_adapter`, `reset_registered_adapters` and a
  declarative `ADAPTER_CONTRACT`, so a result-only worker adapter defined
  outside `experiments/two_attempt_orchestrator.py` can be named by a config
  with no coordinator edit (v0.1 acceptance criterion 12). Built-in and
  duplicate names raise `ValueError`; names are validated; adapters receive a
  copy of their attempt spec and a non-`CollectedCandidate` return is an
  isolated `worker_error`. Replay fails closed when the adapter is not
  registered. No execution, network or authority is added (sandbox work stays
  with #804); existing run records for all example configs are byte-identical.
- Newcomer path: local-loop tutorial and stale starter links (refs #9, #16): add
  `docs/LOCAL_LOOP_TUTORIAL.md`, a walkthrough of `idkmesh local-loop` on two
  committed examples (supported beside rejected; failed worker beside a healthy
  peer), the evidence bundle, replay with `experiments/replay_run.py`, and a
  human decision with `experiments/record_human_decision.py`, linked from the
  README, `docs/README.md` and `docs/GETTING_STARTED.md`, with a sitemap entry
  and a drift guard (`tests/test_local_loop_tutorial.py`) that runs the
  documented commands in-process. The tutorial states that the attempts are
  precollected fixtures, not live workers or hostile-code isolation (sandbox
  tracking issue #804 is open), and that no selection, write, push or merge
  authority exists. Replace #540 and #541 (no longer open) in the README and
  Contributor Quickstart with the currently open newcomer issues and the
  starter task catalog, and annotate the dated contributor pilot table.
- ACE controller tests (refs #57): pin the issue's formulas, which earlier tests
  left unguarded. Mutation testing showed six controller mutations survived
  (flipped selection sign, dropped `mu/n` mutation floor, ignored latency, noise
  and attention costs, no public-write-budget check, duplicate strategy outcomes
  accepted). New tests derive fitness by hand for each cost term, check the
  selection direction and an independent replicator-mutator computation, hold the
  `mu/n` floor under extreme selection, and pin that overload lowers the published
  floor to `0.1 * mu/n` without removing it. `ACE_GENERATION_EVIDENCE_INTERFACE.md`
  now states both floors. No controller code changed.
- Metric uncertainty (refs #86): the evolution scorer and the live governor now
  attach Beta-Binomial `review_coverage_evidence` / `approval_coverage_evidence`
  blocks beside the review and approval coverage point values, so a default `1.0`
  with no ready PR is reported as `prior_only_no_observations` rather than read as
  observed full coverage and `1/1` is distinguishable from `100/100`. Point values
  and every policy output are unchanged. Corrected the stale normal-approximation
  paragraph in `METRIC_UNCERTAINTY_V0_1.md`, which still described the interval
  that `beta-binomial-v3` replaced with the exact equal-tail credible interval.

- API-9 observability privacy hardening (refs #744): opt-in local access logs
  now use a fixed route vocabulary, replacing run/WorkUnit/project identifiers
  with placeholders and unknown URL paths with `<unmatched>`; unrecognized HTTP
  methods become `OTHER`. Added formatter and live HTTP regression tests and
  synchronized the API/architecture documentation. The authenticated aggregate
  metrics and OTLP export contracts are unchanged.

- E9 enterprise provider-fault scenario (refs #676): replace one UNKNOWN
  placeholder with a deterministic offline WARN diagnostic over the actual
  connector probe, inspection, route and error kernels. Inject healthy,
  outage, rate-limit, quota and secret-bearing exception conditions; require
  refusal to route failed probes and redaction of credential-shaped error
  details. Add falsifying negative tests and synchronize the enterprise
  profile, testing and executable-capability documentation. No live provider
  attempt, retry-scheduler qualification, dispatch or certification claim.

### Added
- Unit-tier CPU headroom (refs #693, #981, #976): the three research-artifact test files from the
  E051, X8 and X4 slices (`tests/test_e051_marginal_selector_sweep.py`, `tests/test_x8_budget_split.py`,
  `tests/test_x4_forecast_interval_calibration.py`, 80 tests) now carry the `sim` marker like the other
  experiment tests, so they leave the per-PR unit tier (about 7.1 CPU-s of a 90 CPU-s budget measured at
  100.5 CPU-s on an idle machine) and run in the emergence-sim workflow and nightly. The workflow's path
  filters, its pytest list and the `sim/README.md` list now include them. No assertion changed.

- [GitHub Ledger Retention and Reference Policy v0.1](docs/specifications/GITHUB_LEDGER_RETENTION_V0_1.md)
  and `idkmesh/github_ledger_retention.py` (issue #597, slice C9-H): a pure advisory
  policy for the durable ledger. `check_run_retention` reports which compact
  candidate / ResultManifest / VerificationResult / Human Decision references a
  recovered run must carry and which are not interpretable after raw artifacts
  expire (malformed digest, no repository-relative path, unsafe or transient path);
  `plan_artifact_expiry` says whether a raw Actions artifact, log or cache *may*
  expire and retains young, active-run, unclassified and sole-copy artifacts;
  `assess_ledger_size` bounds growth with an operator-sharding remedy only, never
  compaction or rewrite. Strict policy parsing, no hidden clock, deletes nothing,
  grants no authority. Wiring it into a scheduled workflow and sharding itself are
  not implemented.
- E5 classified egress policy and secret-reference contract (refs #672): a
  strict `enterprise-egress-policy-v0.1` document (exact hostnames, trust zone,
  explicit per-class allow list) with a deny-by-default
  `decide_classified_egress` evaluator that composes the control profile, the
  external-processing flag for the exact class and an approved-provider list,
  and binds each decision to the policy digest; plus a closed-scheme
  secret-reference grammar, trusted alias resolution (a task can name an alias,
  never a source) and identifiers-only secret-access audit details. Offline
  policy evidence only: nothing enforces an egress decision at a socket, and no
  workload-identity deployment is qualified. See
  [the data policy specification](docs/specifications/ENTERPRISE_DATA_POLICY_V0_1.md).

- E5 secret non-disclosure at canonical WorkUnit/source binding and E4 audit
  output (refs #672): reject recognized raw credentials and incomplete scans
  before creating or revalidating a WorkUnit binding, before inserting an E4
  SQLite audit row and before direct NDJSON audit export. The public error
  classes remain stable, messages include no matched secret, rejected audit
  writes leave the append-only chain unchanged, and regression tests cover
  replay/rollback/stream denial. Other runtime write paths remain unguarded.

- github: pure C13-E canonical Product Spine run-state label planning, with three narrowly owned namespaces, idempotent add/remove diffs, stale-digest/invalid-input refusal, and complete run-state regression tests (refs #608). Routing label projection now preserves the independent lifecycle namespace. No GitHub write or grant of dispatch, verification, human decision, integration, or merge authority. See [run label projection](docs/specifications/GITHUB_RUN_LABEL_PROJECTION_V0_1.md).

- tests: five scenarios move from UNKNOWN to exercised in the E9 enterprise
  conformance harness: stale-claim fencing, data-class egress, the local HTTP
  boundary, public-evidence publication, and provider outage and quota (refs
  #670, #672, #673, #676, #609). Each has a negative control that turns it red
  (disabled fencing, disabled Host check, unrestricted external processing, a
  publication renderer without the whitelist, wrongly retryable errors), and a
  scenario with no explicit assertion cannot report PASS. Provider coverage is
  pre-dispatch only: injected outage, rate-limit and quota probes are refused by
  the real router and normalized errors, including the non-retryable
  `authentication_error`, stay credential-redacted. Live attempt, quota
  reconciliation and retry boundaries remain an explicit WARN gap. The
  ten-issue evidence matrix is in
  [Enterprise Control Plane](docs/architecture/ENTERPRISE_CONTROL_PLANE.md).
- tests: fresh-repository bootstrap-to-preview fixture (C8-G, refs #596). On a
  bare directory with only a `.git` marker, it runs `idkmesh init --github
  --apply`, shows `github-workflow preview` refusing with
  `preview_scope_unconfigured` until the owner sets a write scope, then
  previews deterministically using the environment declared by the
  *installed* wrapper file, with every socket connection blocked. It also
  pins re-run safety (an owner-edited seed is preserved, a hand-edited
  managed workflow is refused and left untouched), read-only `status`, and
  fail-closed `dispatch` and `verify`. No production code changed; no GitHub
  mutation, dispatch or secret access. Described in
  [GitHub Workflow Runner v0.1](docs/specifications/GITHUB_WORKFLOW_RUNNER_V0_1.md#tests).
- github: `idkmesh init --github --check` and `--apply` (C8-F, refs #596) install
  the eight generated bootstrap files into the current Git repository. `--check`
  is read-only. `--apply` writes only those files, through no-follow
  directory-relative operations, and records generated digests in
  `.idkmesh/bootstrap-state.json`; it refuses symlinks, a missing or invalid
  state record, and managed files edited since the last install, and it never
  overwrites the user-owned seeds. POSIX only; multi-file writes are not
  transactional (state is written last, so an interrupted run fails closed). No
  GitHub mutation. Specified in
  [GitHub Bootstrap Safe Apply v0.1](docs/specifications/GITHUB_BOOTSTRAP_SAFE_APPLY_V0_1.md).
- api: `ControlTowerClient.collect_run_pages(max_pages=..., limit=..., state=...,
  project_id=...)` reads a bounded series of run pages with opaque cursors,
  keeps each page's request ID and digest, validates the page budget before any
  I/O and raises on a repeated cursor or an exhausted cap instead of returning
  silent partial success. Not a transactional snapshot; no retries or writes
  (refs #746). Specified in
  [Python API Client Compatibility Checks v0.1](docs/specifications/API_PYTHON_CLIENT_COMPATIBILITY_CHECKS_V0_1.md).
- steward: `evaluate_steward_history_sli()` evaluates a validated Auto Draft
  steward history against operator-supplied thresholds (report volume, blocked
  and head-moved fractions, consecutive blocks), binds the result to the history
  input-set digest and lists what it cannot observe; it has no dispatch,
  verification or integration authority (refs #752). Operations and retention
  decision guide: `docs/operations/AUTO_DRAFT_STEWARD_SLI_RETENTION_V0_1.md`.
- research: `analyze_heldout_verifier_addition()` selects a verifier on
  calibration rows only and reads the holdout solely for the frozen candidate;
  it abstains on ties or non-positive contributions and refuses overlapping
  candidate IDs or mismatched gate, quorum or verifier identities. Exploratory
  point estimates only, no group-level uncertainty (refs #693). Protocol:
  [Marginal Verifier Holdout Protocol v0.1](docs/research/MARGINAL_VERIFIER_HOLDOUT_PROTOCOL_V0_1.md).
- research: [Physarum synthetic-to-field decision gate](docs/research/PHYSARUM_SYNTHETIC_TO_FIELD_GATE_V0_1.md)
  freezes the falsification rule, the reproduction commands (each checked
  against the simulator's argument parser) and the decision-ledger fields for
  the synthetic stress simulator. No new simulation result is claimed (refs #630).
- docs: [Comparing Control Tower API metrics snapshots](docs/reference/API_METRICS_INTERVAL_GUIDE.md)
  explains `evaluate_api_metrics_interval()`, with a runnable example and a
  drift test that executes it and compares the UNKNOWN reason vocabulary with
  the source (refs #744, #471).
- docs: [no-JSON WorkUnit walkthrough](docs/help/GITHUB_WORKUNIT_FORM.md) with
  three committed synthetic issue snapshots (parsed, fallback, refused) run
  through the real `idkmesh work preview`; the test fails when a fixture is
  broken (refs #608).
- tests: E3-G enterprise two-principal acceptance fixture (refs #670). Nine
  in-process tests drive `authorize` behind the decision cache with every
  outcome appended to the audit ledger under `TenantScope`. Four
  separation-of-duties and audit gaps are documented in the spec, not fixed.
- github: `preview_github_issue_work_unit(..., use_intake_form=True)` composes a
  parsed WorkUnit Issue Form with `GitHubIssueWorkPolicy` (refs #608). The form
  can only restrict: requested paths are intersected with policy scope,
  forbidden paths are appended, risk and data classification can only rise, and
  other hints are advisory. A fallback parse leaves the generic preview digest
  unchanged.
- github: `idkmesh pages-site` validates C14-D public-safe projections and
  writes the C14-E Pages file map to a local directory all-or-nothing, refusing
  unsafe paths, symlinks and unrecognised non-empty directories; no publication
  or network (refs #609).
- docs: API error catalog, limits and quickstart under `docs/reference/`, each
  drift-tested against the code (refs #746). Corrects a stale statement that
  the client omits `openapi.json` and `metrics`.
- github: `idkmesh github-workflow {preview,status,dispatch,verify}`, the
  stdlib-only runner the generated `init --github` wrappers call (refs #596).
  `preview` and `status` are read-only; `dispatch` and `verify` fail closed
  (`dispatch_unavailable`, `verify_unavailable`). Specified in
  [GitHub Workflow Runner v0.1](docs/specifications/GITHUB_WORKFLOW_RUNNER_V0_1.md).
- github: `idkmesh release-provenance` and `idkmesh/github_release_provenance.py`
  (C14-F, refs #609): an offline record binding a proposed tag, target commit
  and artifact digests (caller-supplied, unverified) to C14-D run evidence, with
  fixed all-false claims and authority and no timestamps. Creates no tag,
  release or attestation.
- api: `ControlTowerClient.stream_events()` reads `GET /api/v1/events/stream` as
  one bounded, strictly parsed, digest-checked `EventStream` with a mandatory
  idle timeout and no reconnect; resuming with `Last-Event-ID` is the caller's
  job (refs #746).
- cli: offline `idkmesh work preview --issue-json` (C7-C, refs #580): an issue
  snapshot file plus `.idkmesh/project.json` policy to the WorkUnit preview with
  the Issue Form composition; read-only, no network, no dispatch. Policy
  derivation is shared with `github-workflow preview`.
- ci: 16 heavy replay, bootstrap, soak and process-spawning tests are marked
  `slow` (nightly tier) because the unit tier had reached 90.7 CPU-s of test
  time against its 90 CPU-s budget (refs #752). No test was deleted and the
  budget is unchanged; the unit tier is now about 75 CPU-s.
- E3-D authorization freshness cache (refs #670): `idkmesh/enterprise_authz_cache.py`
  adds `AuthorizationDecisionCache`, keyed on the full normalized actor/approver,
  policy content digest and request shape, with a validity window capped by
  max age and actor/approver expiry, so a revoked, changed or expired identity
  or an edited policy cannot reuse a cached ALLOW. Adds focused unit tests.
- E5 issue-preview credential refusal (issue #672, partial):
  `preview_github_issue_work_unit` now scans the issue title, body and metadata
  with the raw-secret scanner and refuses with `policy_denied` when a credential
  is found or the text cannot be fully scanned. This covers `idkmesh work
  preview`, the `github-workflow preview` runner and the Issue Form path. The
  refusal names rule ids and fields only, never the text, and tells the author
  to rotate the credential. Scanner refinements from a measured false-positive
  check on this repository's 1,117 issues and PRs: explicit URL templates and
  synthetic `scheme://user:password@host` are ignored, but weak literal URL
  passwords and lowercase Bearer tokens remain detectable. The exact phrase
  `bearer token-based-authentication` is exempt, not arbitrary lowercase
  credentials. Result and audit write paths are not covered yet.
- E6 recovery-drill evaluator (issue #673, partial):
  `idkmesh/enterprise_recovery_drill.py` judges one recorded recovery drill against
  the enterprise profile's declared `rpo_minutes` and `rto_minutes`, returning PASS,
  FAIL or UNKNOWN with value-free reason codes. Measured data loss and recovery time
  are compared inclusively; an unverified restore fails; a missing, malformed,
  mismatched, future-dated or (when a maximum age is given) stale drill is UNKNOWN,
  never a pass. The record is strict and credential-free. It runs no drill and
  restores nothing, and no real drill has been recorded. Also corrects the control-plane
  note that claimed a restore-test interval and a backpressure field the profile does
  not have. Described in
  [Storage restore and integrity drill](docs/operations/API_STORAGE_RESTORE_DRILL_V0_1.md#judging-a-drill-against-the-profile-e6-673).
- Separation of duties for verification (issue #598, C10-G): the authorization
  kernel now refuses `verify` when the actor is among the principals that executed
  the work under review. `PolicyRule.executor_distinct_at_risk` is a risk
  threshold (baseline `verify`: `low`, i.e. every risk; `medium` permits
  low-risk self-verification explicitly; `None` disables it) and
  `AuthorizationRequest.executor_principal_ids` carries the executors. The result is
  `deny / self_verification_forbidden`, or `deny / executor_identity_required`
  when no executor is supplied (fail-closed, since a rule the caller could skip
  by omission is not a control). The decision cache key and policy digest cover
  both new inputs. Behaviour change: baseline `verify` requests must now carry
  `executor_principal_ids`; no production code issues them yet. The principals
  must come from the retained run record, and principal linking across IdPs
  remains out of scope. Specified in
  [Enterprise Authorization](docs/specifications/ENTERPRISE_AUTHORIZATION_V0_1.md#verifier-is-not-the-executor).
- E5 raw-secret scanner (issue #672, partial): `idkmesh/enterprise_secret_scan.py`
  detects credential-shaped values (GitHub, AWS, Slack, Google, `sk-` keys, JWTs,
  PEM private-key headers, `Bearer` credentials, URL userinfo) and literal values
  under exact credential-named keys in JSON-shaped documents, including strings
  in a list under such a key (an object under one is judged by its own keys).
  Findings carry a rule id and a sanitized JSON Pointer only, never the matched
  text; a secret used as a mapping key is replaced by `<key:N>` in locations.
  The scan is fail-closed: depth, node and string-size limits and non-JSON values
  make the report incomplete, which is never clean. References such as `env:NAME` are accepted.
  The initial scanner did not enforce admission or persistence. A subsequent
  E5 slice now guards canonical WorkUnit/source binding and E4 audit event and
  NDJSON sink writes, but does not cover results or every runtime path and is
  not a guarantee of secret absence. See
  [Enterprise Data Policy Kernel v0.1](docs/specifications/ENTERPRISE_DATA_POLICY_V0_1.md#executable-enforcement-boundaries-partial-e5).
- E5 data/egress/credential decision kernel (issue #672, partial):
  `idkmesh/enterprise_data_policy.py` turns a validated enterprise control
  profile into pure fail-closed decisions. External processing is checked per
  exact data class (non-compensating, restricted denied unless its own flag is
  true) against an explicit approved-provider list; egress is deny-by-default
  with exact-hostname allowlisting and no wildcard or suffix matching;
  long-lived cloud keys are refused by the profile switch and under an OIDC
  backend; secret access requires a prior `allow` authorization decision and
  the source comes from the profile, never from request text. Decisions carry
  identifiers and reason codes only, read no secret value and grant no
  authority. Not yet wired into any runtime path, and the profile still has no
  egress-allowlist field, so #672 stays open.
- Thread-safe authorization decision cache (refs #670): every operation of
  `AuthorizationDecisionCache` is serialised by one lock, so concurrent request
  threads cannot corrupt LRU order or the hit/miss counters; a threaded test
  fails without the lock.
- Data-policy hardening (refs #672): `authorize_secret_access` now unlocks a
  secret only for an allowed `dispatch` or `execute` decision (an allow for
  `read`, `claim`, `verify` or `audit_export` does not), production
  `assert` statements are replaced with explicit checks, and
  [Enterprise Data Policy Kernel v0.1](docs/specifications/ENTERPRISE_DATA_POLICY_V0_1.md)
  specifies the kernel.
- spine: pin the evidence-to-human-decision seam end to end (refs #682). A new
  integration test drives the offline spine, run store, `idkmesh run evidence`,
  the Control Tower client and `HumanDecisionService`, proving the shown digest
  is the bound digest, stale or swapped digests fail closed, and recording a
  decision changes no run state or evidence.
- tests: pin required marginal-evidence fixture cases 1, 3, 4 and 10 by name and
  map all ten in the spec (refs #693).
- research: PHY-1 burden-matched failover frontier for Physarum routing
  (synthetic). Physarum beats the frontier in 3/16 cells, discounted Thompson in
  10/16; promotion stays rejected (refs #630).
- `idkmesh init --github --dry-run` now renders the four pinned C8-D workflow
  wrappers (`idkmesh-preview`, `-dispatch`, `-verify`, `-status`) as
  `rendered_workflow_files`, with Actions pinned to full SHAs, least-privilege
  permissions, an environment-gated dispatch secret and a fail-closed runner
  probe. Rendering only; apply stays disabled and the runner is still owed
  (refs #596).
- API-11 discovery reads for issue #746: `ControlTowerClient.get_openapi()`
  downloads the OpenAPI 3.x definition of the running Control Tower
  (`GET /api/v1/openapi.json`) and `get_metrics()` reads the fixed-cardinality
  operational metrics (`GET /api/v1/metrics`). Both reuse the single-request,
  no-retry, request-ID and whole-response content-digest verification; the
  OpenAPI document is additionally checked for a `3.x` version marker, `info`
  and `paths`, and metrics for the expected `kind`, failing closed with
  `ProtocolError`. The typed web client, error catalog and remaining API
  documentation, and the authenticated human-decision mutation, remain open.
- C13-C/C13-D GitHub WorkUnit intake parser (refs #608): the new pure
  `idkmesh.github_workunit_intake.parse_workunit_intake` turns an
  `IDKMesh WorkUnit request` Issue Form body into the frozen intake object
  or a safe `fallback` result for incomplete, duplicated, hand-edited,
  unsafe-path or out-of-vocabulary content; it never grants authority.
  Composition with `GitHubIssueWorkPolicy` and `work preview` is still open.
- AVE-core shadow adapter regression pins (refs #644):
  `tests/test_ave_shadow_adapter_gates.py` isolates each of the nine hard gates
  (WorkUnit id/version, pool binding, sovereignty, zero project spend,
  independent-verification policy, required-validator coverage, schema version),
  the critical risk target, and each step of the eight-step lexicographic order,
  so a refactor cannot silently drop one. Tests only; no adapter behaviour
  changed, and the real N3 cohort remains open pending actual pre-outcome
  captures.
- AVE-core shadow chain compatibility pins (refs #644):
  `tests/test_ave_shadow_adapter_cohort_chain.py` runs synthetic AVE plans
  through the generic outcome join and cohort summary and pins agreement and
  disagreement counting, abstention retention, rejection of outcomes that
  predate the plan or name an unfrozen choice, digest binding after plan
  edits, and the descriptive-only cohort summary. Tests and a doc note only;
  no adapter behaviour changed, and the real 20-30 plan N3 cohort remains
  open and time-gated. Synthetic fixtures are not N3 evidence.
- Enterprise conformance doctor, first slice (refs #676):
  `idkmesh doctor --enterprise-conformance [--json]` runs nine in-process
  destructive scenarios against the real tenant-scope, authorization, audit
  ledger, run-idempotency and secret-boundary primitives (temp dirs and fakes
  only) and reports PASS/WARN/FAIL/UNKNOWN per scenario with expected safe
  state, observed result and evidence links. Stale claim/retry, provider
  outage/quota and release provenance report UNKNOWN until they are built;
  the overall status is therefore UNKNOWN (exit 1). Not a certification claim.
  `idkmesh/enterprise_conformance.py`, `tests/test_enterprise_conformance.py`.
- Read-only GitHub Pages site projection for issue #609 (C14-E):
  `idkmesh/github_pages_site.py` renders a deterministic in-memory static file
  map (health, active work, verification debt, per-run provenance pages,
  public JSON, `.nojekyll`) from C14-D public-safe projections only,
  re-validating every value, escaping HTML and Liquid delimiters, and emitting
  no scripts, external assets, or mutation controls. See
  [GitHub Pages Site Projection v0.1](docs/specifications/GITHUB_PAGES_SITE_V0_1.md).
  No publishing workflow, GitHub call, or outage fallback is included.
- C10-H two-GitHub-user acceptance fixture (refs #598): `tests/test_c10_two_user_acceptance.py`
  composes the reviewed binding table, `authorize`, `LocalTaskClaims` and the C5
  label lane over synthetic actors to demonstrate propose / dispatch / concurrent
  claim / verify / protected-integration / unauthorized-label behavior. Tests only;
  no runtime behavior changed.

- X4 synthetic calibration (refs #976): `experiments/forecast_interval_calibration.py` runs the
  forecasters and bootstrap intervals of `forecast_intervals.py` against seeded simulated
  populations whose population coverage and blind-spot floor are known exactly (4 scenarios x 6
  populations x 30 pilots x k in {3, 5, 10, 20}). Recorded verdict at k = 10 under a rule declared
  before the run: **mixed**. The beta-binomial point forecast meets the 0.03 tolerance in 3 of 4
  scenarios, but no forecaster is both within tolerance and calibrated (the only interval at or
  above the declared 0.90 bar at k = 10, 0.939, belongs to a biased forecast). Synthetic evidence only; real-data interval coverage waits on E048.
  Output `experiments/results/X4-synthetic-interval-calibration.json`, write-up
  `docs/research/X4_SYNTHETIC_INTERVAL_CALIBRATION.md`, covered by
  `tests/test_x4_forecast_interval_calibration.py` (includes oracle and broken-estimator controls).
- X4 forecast-interval instrument (refs #976): `experiments/forecast_intervals.py` adds the
  piece of the X4 report E046 did not compute, the **interval coverage** of the intervals a
  pilot forecaster reports, with bias, MAE and the 0.03 hit-rate, as a function of pilot size k.
  It bootstraps beta-binomial, incidence (Chao et al. 2014), independence and pilot-only
  forecasts by resampling tasks or pilot agents, scores them against the exact population
  coverage (the blind-spot floor is its complement), and imports the frozen E046 analysis
  unchanged. It is exploratory: on splits E046 already opened its output is post-hoc, and
  no result has been run or claimed. Covered by `tests/test_x4_forecast_intervals.py`.
- Cross-origin delta matrix for the local UI servers (issue #745, Security
  CORS/CSRF item; `tests/test_api_cors_csrf_matrix.py`). Complements
  `tests/test_api_security_matrix.py` with the coverage it does not have:
  the read-only steward dashboards refuse every write verb and preflight
  under a hostile `Origin`, the gate-audit mutation's CORS posture is pinned,
  the Control Tower's JSON-only mutation gate refuses simple content types
  even with a valid session token, `Origin: null` is not a credential, no
  response reflects the `Origin` value, and refusals keep the
  browser-isolation headers. The no-grant check matches any
  `Access-Control-*` header, not just the `-Allow` family. The suite runs
  in the `security` group of `make qualify-api`, keeping the release
  qualification report in line with `docs/TESTING.md`.
- The backward-compatibility diff gate (issue #737, ADR-0020) now covers
  the `openapi.yaml` API surface, not just `schemas/*.json` (issue #745,
  Contract-tests compatibility diff gate). Removing a path, operation,
  response status, media type, or declared parameter -- making a
  parameter required, renaming an `operationId`, changing a response
  shape or schema target, or removing a shared `components` entry -- is
  now a gate failure; additions remain widenings. Parameters are read via
  the new stdlib-only `tools/openapi_catalog.py` block-mapping parser,
  which also becomes the single source for the parsing helper the API
  conformance tests use. Documented in the ADR's amendment note.
- Exhaustive permission matrix for the enterprise authorization baseline
  (issue #745, Security permission-matrix item;
  `tests/test_enterprise_authz_permission_matrix.py`). Pins the complete
  role x action x actor-type decision table of
  `AuthorizationPolicy.enterprise_baseline()` as a change-detector (136
  subtests; ENTERPRISE_AUTHORIZATION_V0_1 states the matrix only in part, so
  this table is a transcription of the current baseline, not a spec oracle): which roles and actor types may take each action, that
  `manage_policy` is the only action already at its approval threshold at its
  own risk floor, and that multi-role actors get exactly the union of their
  cells. Any baseline widening or narrowing now forces a deliberate table
  update. Complements the pairwise scenarios in
  `tests/test_enterprise_authz.py` and the #743 authority-matrix guards.

- C12 GitHub governance preflight (issue #607): `idkmesh doctor --github`
  now evaluates the canonical C12-A governance policy from bounded normalized
  observations, reports PASS/WARN/FAIL/UNKNOWN/NOT_APPLICABLE, and treats
  missing required evidence as blocking. `idkmesh/github_governance_preflight.py`
  also provides conservative workflow-source checks for least privilege,
  immutable action references, checkout credential persistence, untrusted-PR
  secret isolation, protected-environment binding, optional OIDC shape, and an
  explicit-owner CODEOWNERS recommendation. The implementation is read-only:
  it never changes GitHub administration, reads secret values, dispatches work,
  or treats ruleset metadata as proof of independent review. See
  [GitHub Governance Preflight v0.1](docs/specifications/GITHUB_GOVERNANCE_PREFLIGHT_V0_1.md).

- [API Authority Matrix v0.1](docs/specifications/API_AUTHORITY_MATRIX_V0_1.md)
  (issues #743, #670): which principal may call which Control Tower endpoint,
  expressed in the enterprise authorization kernel's roles and actions as a
  **proposal** for the network profile, with an explicit "enforced today" column
  (a local session token, not a principal). `tests/test_api_authority_matrix.py`
  keeps it complete against the running server's discovery document, checks every
  action and role exists in the kernel, that no served route needs a mutating
  authority, and that the "enforced today" claim is true. The beta gate counts the
  authority-matrix item as satisfied; the security-profile item stays partial.
- [GitHub Ledger Recovery Planning and Killed-Workflow Proof v0.1](docs/specifications/GITHUB_LEDGER_RECOVERY_PLAN_V0_1.md),
  `idkmesh/github_ledger_recovery_plan.py` and
  `tests/test_github_ledger_killed_workflow.py` (issue #597, slice C9-F): a pure
  advisory `plan_recovery(state)` that names the safe next step for a recovered
  run and reconciles, never blindly resubmits, an unconfirmed provider
  submission; and an exhaustive kill matrix that kills a coordinating workflow at
  every side-effect point (and in pairs), starts a fresh coordinator with only
  the ledger and the provider, and requires a recorded decision with exactly one
  provider submission. Intent is recorded before effect. Grants no authority.
- [GitHub Ledger Recovery Reader v0.1](docs/specifications/GITHUB_LEDGER_RECOVERY_V0_1.md)
  and `idkmesh/github_ledger_recovery.py` (issue #597, slice C9-E): derive a run's
  current state from its immutable ledger records. It verifies the chain, then
  replays it checking legal lifecycle transitions, attempt identity and the human
  decision, keeps every failure observation, reports ambiguous provider
  submissions as a reconciliation hazard, and refuses histories no real run could
  have produced. Works from any prefix, so a crash after any record is
  recoverable. Read-only; no authority.
- [GitHub Ledger Idempotent Admission v0.1](docs/specifications/GITHUB_LEDGER_ADMISSION_V0_1.md)
  and `idkmesh/github_ledger_admission.py` (issue #597, slice C9-D): a duplicate
  dispatch resolves to the run admitted first. One immutable admission ref per
  dispatch key is created by Git compare-and-set (`update-ref` against the
  all-zero id), so concurrent duplicates admit exactly one run; an exact replay
  returns it and writes nothing, a replay with a different request digest fails
  closed, and a crash between admission and the first ledger record is completed
  by the next replay for that run. Proven against real Git, with a deterministic
  race test per PR and concurrent-writer tests in the nightly tier. Local plumbing
  only: no push, no GitHub call.
- [GitHub Ledger Optimistic Append v0.1](docs/specifications/GITHUB_LEDGER_APPEND_V0_1.md)
  and `idkmesh/github_ledger_append.py` (issue #597, slice C9-C): a compare-and-set
  append to the GitHub-native durable ledger. Records land on one Git ref per run
  through `git update-ref <ref> <new> <old>`, so a writer that read a stale head
  loses with a `LedgerConflict` carrying the actual head instead of overwriting
  the winner; `append_with_retry` re-reads and rebuilds, bounded. History is
  linear and never rewritten, every append re-verifies the whole chain, and a
  failed append leaves the ref where it was. Proven against real Git, including
  concurrent writers (nightly tier). Local plumbing only: no push, no GitHub call.
- Source-backed implementation reference (PR #1004): an as-built architecture
  map, a one-row-per-module map of `idkmesh/`, a CLI/HTTP quick reference, a
  troubleshooting guide and a dated reconciliation audit, linked from the
  README, getting-started, architecture and contributor guides. The module map
  is kept complete by `tests/test_module_map_docs.py`, which fails when a
  top-level `idkmesh/*.py` module has no row or a row names a missing module.
- [API v1 beta compatibility, deprecation and migration guide](docs/API_V1_BETA_MIGRATION_GUIDE.md)
  (issue #747): what an API consumer can rely on and what is not yet stable, how
  change and deprecation are announced (no deprecation is in force), the nine
  behaviour clarifications found while qualifying the API with the test that
  covers each, and how to check a revision with `make qualify-api` and
  `make beta-readiness`. The beta gate now counts the migration/deprecation item
  as satisfied.
- `tools/api_clean_install_demo.py` (issue #747): the beta gate's "clean install
  and reproducible demo". Builds a wheel from a staged copy, installs only that
  wheel into a fresh venv, checks the import comes from the new environment and
  the entry point answers `--help`, runs the installed `idkmesh control-tower`
  with the installed Python client, and requires a stable transcript identical
  to the one from the source tree. Part of `make qualify-api` (group `install`);
  the beta readiness gate now counts that item as satisfied only from a current
  green report.
- [API v1 Beta Release Gate v0.1](docs/specifications/API_V1_BETA_RELEASE_GATE_V0_1.md)
  and `make beta-readiness` / `tools/api_beta_readiness.py` (issue #747): the
  fourteen required-evidence items for a first API beta, each with a declared
  status, a recorded gap and verified evidence files. Items the qualification
  run measures are satisfied only by a current, clean, green
  `make qualify-api` report; the tag item needs an `api-v1-beta*` tag on a clean
  HEAD. It currently reports **not ready**, with the real gaps named (Human
  Decision API, multi-user security profile, authority matrix, unpublished
  clients, migration guide, clean-install demo). It tags and publishes nothing.
- API-3 control-plane convergence (#738): the checked-in API architecture now
  names one canonical application/domain owner for projects, connectors,
  WorkUnit preview, routing, runs, candidates, verification/evidence, human
  decisions, integration handoff, resource admission, and events. CLI and
  Control Tower connector/Product-Spine reads are regression-guarded against
  splitting into parallel service models; the still-gated authenticated Human
  Decision HTTP mutation remains owned by #740 rather than being approximated.

- `docs/EXECUTABLE_CAPABILITIES.md` adds a CI-checked code-surface inventory covering the recursive `idkmesh` CLI tree, Control Tower endpoints, dependency-free Python client methods, connector/provider/GitHub/enterprise/runtime capability groups, and every top-level `idkmesh/*.py` module. README, beginner/getting-started help, and architecture indexes now link to it, and stale connector API/CLI status text has been reconciled with current code.
- `tools/api_load_soak.py` (issue #745): a bounded load and soak check for the
  Control Tower. Two rounds of concurrent mixed traffic (every read route plus
  hostile requests) must all return the expected status, stay under a p99
  ceiling, leave no extra threads or file descriptors after drain, and grow the
  heap by no more than a ceiling across a separate traced round, and every
  response body that is byte-stable on an idle server must be identical under
  load. It runs as part
  of `make qualify-api`; the qualification report now lists capacity
  benchmarking, not load/soak, as uncovered. See
  [`docs/TESTING.md`](docs/TESTING.md#load-and-soak).
- [API Storage Profiles v0.1](docs/specifications/API_STORAGE_PROFILES_V0_1.md)
  (issue #750): profile ownership (GitHub ledger, local SQLite, network
  interface requirement), the storage-port operations, required semantics with
  the test that verifies each, migration strategy, retention matrix, and an
  acceptance table that states what is still open. New
  `tests/test_api_storage_integrity.py` covers event integrity, migration
  replay, restart reconstruction and backup.
- `ControlTowerReadAuthBeforeLookupTests` (issue #739): pins, across every
  Product Spine read route, that a missing or wrong session token gets the same
  403 whether or not the id exists (no 404-vs-403 existence probe), and that
  an unknown id with the token is an explicit 404. Test-only; no behaviour
  change.
- End-to-end telemetry privacy test (issue #744): pushes a sentinel through the
  path, query string, request body, wrong session token, `Authorization`,
  invalid `traceparent` and `tracestate` channels and asserts it is absent from
  the metrics document, its OTLP export and the status document. Test-only; no
  behaviour change.
- `LocalMetadataStore.prune_probe_history()` (issue #750): removes superseded
  probe rows and keeps the latest per connection, the one expendable class in
  the API storage retention matrix. Runs, idempotency records, events and
  claims are never touched; claim/lease pruning remains open.
- `make qualify-api` / `tools/api_release_qualification.py` (issue #745): one
  repeatable API release-qualification run. It executes the OpenAPI reference
  gate, the schema compatibility gate (`--base`), and the contract, fuzz,
  security, reliability and client suites, and writes a JSON report (command,
  exit code, duration, counts, output tail, git revision) to
  `results/api-qualification/report.json`. `--strict` fails on a skipped check,
  and a listed suite that no longer exists fails the run. The report names what
  is not yet covered (capacity benchmarking, permission matrix,
  production-adapter smuggling tests). See
  [`docs/TESTING.md`](docs/TESTING.md#api-release-qualification).
- State-transition and idempotency properties for the API release
  qualification suite (issue #745, property/fuzz slice;
  `tests/test_api_state_idempotency_properties.py`). The documented v0.1 run
  and attempt lifecycle graphs are pinned as independent oracles with an
  exhaustive pair test, seeded random legal/illegal walks assert immutability,
  identity preservation and determinism, and seeded create/replay/status/list/
  cancel sequences assert the idempotency laws (exact replay returns the run
  untouched, any mutated replay is `idempotency_conflict`, run identity is
  unique across keys) with total, controlled failures throughout.

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

- Control Tower request path (issue #745; found by an independent bot derivation
  of the security matrix, #1002, and adopted here). Stray query parameters on a
  token-protected endpoint were answered `400 unexpected_query_parameters`
  *before* the token gate, so an unauthenticated caller could probe endpoint
  input shapes; the query check now runs after authentication, and an
  unauthenticated `OPTIONS` preflight is refused identically whatever its query.
  `PUT`/`PATCH`/`DELETE`/`TRACE` on `/readyz` returned `404 not_found` while
  `POST` returned `405`; they now return `405` with `Allow: GET, HEAD`.
- Event reads now verify what the store wrote (issue #750). `payload_digest`
  was written with every event but never checked, so an event whose payload was
  altered in the database file was served as the original. Every read of the
  event log (`GET /api/v1/events`, the event stream, `idkmesh` readers) now
  recomputes the payload digest and checks that the indexed columns
  (`run_id`, `event_type`, ...) agree with the envelope; a mismatch is a
  controlled `store_error` (HTTP 500) and the altered content is not returned.
  Reads that do not touch the damaged row keep working.
- Control Tower and gate-audit session-token checks are now total (issue #745,
  third qualification slice; `tests/test_api_security_matrix.py`). A token
  header holding a non-ASCII byte made `secrets.compare_digest` raise
  `TypeError` inside the request handler, so the Control Tower dropped the
  connection with no response instead of answering `403
  invalid_session_token` (the request was still never served). Both local UIs
  now share `local_ui_security.token_matches`, a constant-time comparison over
  UTF-8 bytes; the gate-audit UI previously used a plain `!=`. The new matrix
  also pins the Host allow-list, the token-bypass cases (missing, empty,
  padded, truncated, extended, re-cased, query-string, cookie), method
  confusion and override headers, and the absence of any CORS grant.
- Strict-JSON parsers are now total on pathologically nested input (issue #745,
  first fuzz slice; `tests/test_api_qualification_fuzz.py`). Deeply nested
  documents raised a raw `RecursionError` through the API client
  (`ProtocolError`), `idkmesh` CLI strict-JSON file loading (`ValueError`),
  Control Tower report parsing (`ControlTowerInputError`) and enterprise audit
  event replay (`invalid_event_json`); each now rejects with its documented
  controlled error.
- Control Tower header/media-type boundary qualification (issue #745, second
  fuzz slice; `tests/test_api_header_boundary_fuzz.py`) found and fixed three
  boundary defects. Explicit `q=0` Accept entries were served anyway: a
  request whose Accept entries are all explicitly zero quality now gets `406
  not_acceptable`, `q=0` on the vendor media type falls back to
  `application/json`, and malformed quality values stay lenient (RFC 9110
  section 12.4.2). The Python API client rejected case/whitespace variants of
  valid response media types (`Application/JSON`, `application/json
  ;charset=utf-8`) with `ProtocolError`; it now normalizes exactly like the
  server while still failing closed on genuinely wrong types. `Content-Length`
  accepted any spelling `int()` parses (`+2`, `-0`) in both request handlers;
  it is now strict RFC 9110 `1*DIGIT`, so those spellings are `400
  invalid_content_length` instead of a framing disagreement with strict
  fronting proxies.
- Lifecycle transitions could rewrite identity and authority
  (`ProductSpineRun.transition("previewed", run_id=...)` silently changed the
  run identity that feeds the create request digest, and
  `transition(..., authority_mode="agent_candidate")` downgraded
  `human_required` work past the admission gate; `attempts` could be smuggled
  past `append_attempt`/`replace_attempt`). Run and attempt transitions now
  reject every field except state plus the state-gated evidence fields and the
  admitted connector set with `invalid_update`, closing the authority bypass
  found by the #745 property suite.
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

### Fixed

- tools: the clean-install demo's wheel-build failure message is now evidence
  instead of an empty string (refs #745). It used to read `wheel build failed: `
  with no output because the build ran under `pip wheel -q`; it now reports the
  build's exit code and its own output, and distinguishes a failed build from a
  build that exits 0 while producing the wrong wheel (an old pip can silently
  emit `UNKNOWN-0.0.0` from a valid `pyproject.toml`), naming the wheel that
  actually appeared. The verdict and exit codes are unchanged.

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
