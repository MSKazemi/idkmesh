---
description: "Source-backed documentation reconciliation of IDKMesh's installable code, CLI, local HTTP, run evidence, research/CI inventory and known evidence gaps across the Oct 10-11 2026 baseline."
---
# Code-to-documentation reconciliation — 2026-10-10/11

**Review type:** documentation stewardship, GitHub source inspection, static source-to-navigation inventory.  
**Initial pinned revision:** `main@58f5d9257d198e0030f7b4a3ed1c22ff239a8d53`.  
**Refreshed revision:** `main@bee77a6125dbccb58f166ec363e978cd960f43f3` (8 commits after initial snapshot).  
**Tracking issue:** [#471](https://github.com/MSKazemi/idkmesh/issues/471).  
**Provenance:** AI-assisted review through the connected GitHub repository interface; not a claim of independent external review.

## Scope and method

1. Enumerated the full recursive Git tree: **1,958 tracked blobs** on the initial revision; **1,970** on the refreshed revision. The refreshed tree has **85** direct `idkmesh/*.py` files and **489** documentation files under `docs/`. The tree response was complete (`truncated=false`). Counts are an inventory, not execution coverage.
2. Read repository instructions (`AGENTS.md`, `PROJECT_RULES.md`, `CONTRIBUTING.md`), README, root and subsystem architecture docs, CLI and install metadata, source of the main HTTP/API/client/run/evidence paths, and relevant versioned specs. Queried recent changes and the open PR queue to avoid documenting unmerged behavior.
3. Inspected the module-level contract and top-level declarations of **each of the 85 direct package Python modules**, grouped by source-owned responsibility in [the module map](../reference/MODULE_MAP.md). Read selected implementation bodies of `cli.py`, `control_tower_ui.py`, `api_client.py`, `local_loop.py`, `local_agent_sandbox.py` and others for route names, option constraints, and safety boundaries.
4. Created [an as-built architecture map](../architecture/AS_BUILT_IMPLEMENTATION_MAP.md) separate from proposal-level diagrams, [a CLI/HTTP quick reference](../reference/CLI_HTTP_QUICK_REFERENCE.md) and [troubleshooting](../help/TROUBLESHOOTING.md). These coexist with the [canonical capability truth matrix](../CAPABILITY_MATRIX.md) rather than replacing its evidence/status classifications.
5. Compared the changed paths across the eight later commits. They include API body/parser hardening, schema pattern handling, storage-profile docs, API qualification tools, `docs/TESTING.md`, and `Makefile`. The latest visible source contains `make qualify-api` and `tools/api_release_qualification.py`; there was **no** persistent test-command mismatch to 'fix' on the refreshed commit. New/merged behavior is not retroactively projected onto the initial pinned revision.

**Important limitation:** this pass was **not** a line-by-line audit of all ~2,000 tracked files. The 85 package modules were inventoried one-by-one at the contract/declaration level; the many `experiments/`, `sim/`, `tools/`, `scripts/`, workflow, fixture, schema and test files were indexed by path and sampled at subsystem boundaries, **not independently re-executed or semantically verified file-by-file**. Consequently the document does not certify complete test coverage, broad correctness, security, real-world reproducibility, or release fitness.

## Corrections and distinctions to retain in public docs

| Observed current source | Documented scope | Wrong inference to avoid |
| --- | --- | --- |
| `cli.py`, `github_bootstrap.py`, `github_bootstrap_render.py` | `init --github --dry-run` plans and renders metadata only | `init` can apply config to another repo |
| `cli.py`, `product_spine_run_store.py`, `connector_store.py` | Local SQLite run create/read/list/cancel/evidence | A run-record mutation dispatches/stops a provider |
| `local_loop.py`, `experiments/replay_run.py` | Checkout-only two-attempt fixture/reference execution, independent verification, evidence bundle | A standalone pip wheel is a finished autonomous runner |
| `control_tower_ui.py`, `control_tower_api.py`, `api_client.py` | Loopback-only, token-protected **read/inspection** `/api/v1`; computational inspection POST | Multi-user public API or authenticated human-decision mutation |
| `human_decision_service.py`, `enterprise_authz.py` | Domain authorization and immutable decision service with trusted identity input | Available `POST /api/v1/human-decisions` network endpoint |
| `local_agent_sandbox.py` | Linux bubblewrap backend with `network_policy=disabled`; fail-closed on unsupported capabilities | Generic secure execution of arbitrary model-connected coding agents |
| `github_candidate_reader.py`, `jules_candidates.py`, `verification_handoff.py` | Exact-source candidate discovery/identity and evidence handoff | Provider completion, PR URL, or verification alone grants merge |
| `api_observability.py`, `otel_metrics.py` | Fixed-cardinality local metrics and **offline** OTLP mapping | Built-in hosted telemetry collector or production SLO compliance |
| `docs/planning/API_V1_SURFACE_CATALOG_2026-09-23.md` | Historical **planning snapshot** using statuses as of Sep 23 | Its `planned` labels describe current merged HTTP routes |

## Remaining work (priority ordered)

1. **P0 — Test and review the exact PR head.** Run `python -m pytest -q` / `make gate` / `make integration` as appropriate, deterministic link validation, and required Python 3.11 + 3.13 checks in CI before merging. This audit itself does not report a green build.
2. **P1 — Extend one-to-one cross-reference beyond the installable package.** The broader code contains, at the refreshed snapshot, 26 `experiments/*.py`, 67 `tools/*.py`, 38 `scripts/*.py`, 42 `sim/*.py`, 23 `randomness_lab/*.py`, 5 `interop/*.py` (not counting tests), 318 Python files under `tests/`, and 61 GitHub workflows. Map each active non-package module, its CLI/Actions invocation, contract, tests, and status in bounded follow-up PRs rather than inflating one review to an unvalidated universal certification.
3. **P1 — Finish the professional API qualification gates.** Current `make qualify-api` exists, but passing static contract/fuzz/security/soak checks must not be presented as an externally validated multi-tenant production service. API-13 / [#745](https://github.com/MSKazemi/idkmesh/issues/745) tracks further qualification, with newer API hardening changes progressing independently.
4. **P1 — Connect documentation checks to changed code.** Extend CI where helpful to test that all `idkmesh/*.py` files are represented once in the module map, that listed CLI commands still appear in parser help, and that documented HTTP paths match `openapi_document()`. Reuse existing capability and link checks; avoid writing a redundant second status matrix.
5. **P1 — Run a newcomer golden path on a clean non-developer machine.** Confirm install, basic gate audit, local-loop optional setup, Control Tower token, and store/read flows; retain reproducible success/failure artifacts. This is a separate real-world validation from reading source.
6. **P2 — Complete release/paper/docs reconciliation after observed experiments.** Update scientific claim-to-evidence mappings only when frozen experiments or reproducible external runs justify stronger statements. No paper results or evidence levels were changed in this documentation-only pass.

## Validation record

| Check | Result and interpretation |
| --- | --- |
| GitHub repository visibility and write access | Passed: repository was read and a bounded branch created through the connected GitHub app |
| Initial + refreshed recursive source inventory | Passed: full Git trees returned; 85 direct package modules accounted for in generated module table |
| Package declarations / CLI parser / HTTP routes | Source inspection performed; **not** a live server exercise |
| Relative-link and source-path checks | **Passed static check:** all 423 parsed local Markdown links in the 14 modified/new files resolve against the refreshed Git tree plus proposed files (0 missing); all 85 package modules have exactly one row in the new source map (0 missing, extra, or duplicate). The full repository link/integration gate remains CI-owned. |
| Local unit/integration/API soak suites | **Not run during this review**: this runtime cannot clone the GitHub host (DNS unavailable) and cannot execute the repository's local test harness |
| Independent human review, external pilot or production run | **Not performed** |
| Merge or production deployment | **Not part of the stewardship pass**; maintainers must inspect exact-head checks and review the PR |

**Change policy:** preserve historical plans and studies as dated evidence; update current onboarding, architecture and navigation documents in a coherent PR. This record is not an external-security audit, a release certification, or a guarantee that every pre-existing document was read line-by-line.
