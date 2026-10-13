# Non-package Python documentation reconciliation — 2026-10-13

**Baseline:** `main@19043860b8358e9e78484876001b19063d697eec` as observed through the connected GitHub API. **Scope:** direct Python sources in six non-package directories; this is a **source-interface/entrypoint review**, not a complete semantic, security or empirical-reproducibility audit.

## Completed review

Compared the complete recursive Git tree against the source-level module purpose and exposed definitions of:
- 27 `experiments/*.py` modules, including evaluator-plan verification, source-binding, two-attempt orchestration, evidence and human-decision separation, E045-E048 public-data work, and synthetic queue/backpressure studies;
- 42 `sim/*.py` modules, including E015-E020 verifier models, E024-E039 emergence/failure studies, ACO/Physarum, and review-capacity policies;
- 23 `randomness_lab/*.py` modules, including R1-R4, model families, replay readiness, uncertainty, and fixed-budget comparisons;
- 5 direct `interop/*.py` modules (excluding 8 test modules): A2A/MCP identity-preserving in-process bindings and optional official-SDK conformance;
- 72 `tools/*.py` and 40 `scripts/*.py` modules (112 total), covering release/API/schema tooling, GitHub agent operations, frozen benchmark calibration, IDKGraph, repository evolution, discovery, and developer gates.

Created [research module map](../reference/RESEARCH_MODULE_MAP.md) and [operational module map](../reference/OPERATIONS_MODULE_MAP.md); each table links to real source files. The maps deliberately classify code by what the source describes and whether outputs are observation, synthetic evidence, metadata validation, or possibly external action. **File inventory does not prove execution correctness.** The associated test checks that each direct source file appears once in its owning map; it does not certify behavior.

## Source-backed implementation boundaries

1. `experiments/local_verifier.py`, patch v0.2-v0.4 adapters and `experiments/local_validator.py` inspect metadata, diff/provenance and files; they do **not** execute arbitrary candidate code. Explicit frozen-source behavioral probes are separate.
2. `experiments/two_attempt_orchestrator.py` is a deterministic adapter/evidence control-plane kernel, not a live general swarm executor. `run_evidence_report.py` remains non-selecting. `record_human_decision.py` records a local human decision, not a GitHub merge.
3. E016/E017 run fixed executable oracle/candidate studies and analyze actual oracle votes; other simulations remain synthetic. Upstream public SWE-bench matrices are observed data, but E045 is exploratory and E046/E048 have preregistration and temporal-holdout boundaries.
4. `interop/` maps semantic envelopes in process; it implements no generic A2A/MCP network server. Optional SDK tests can skip.
5. `tools/` and `scripts/` have mixed risk: publication, GitHub, model and website tools can perform external I/O; a source link or dry-run helper never confers approval to execute them.

## Validation

- Connected GitHub tree enumeration and explicit path cross-check: 209 direct non-package Python modules in these six directories on the reviewed revision (97 research/interop + 112 operational).
- Current-source purpose and entrypoint inspection: completed at module boundaries.
- Runtime/pytest/CI: **not executed locally**; local git clone was blocked by unavailable GitHub DNS. The changed-head PR gate must run the new path-drift test and existing link/sitemap checks.
- Wider audit limitations: did not independently execute 300+ tests, inspect every executable line, audit the 61+ GitHub workflows, reproduce external experiments, or assert benchmark validity.

## Next bounded passes

1. Workflow-to-script invocation/permissions matrix with fail-closed checks, plus secret and action authority.
2. Test-to-module traceability for untested entrypoints and a clean installation/real model environment replay.
3. Review documented scientific claims and paper evidence against frozen results and registered revisions.
4. Reconcile changing main and open PRs before future status changes; do not rewrite historical findings as current truth.

**AI/tool provenance:** ChatGPT with connected GitHub source access. No independent human review performed. Related stewardship tracker: [#471](https://github.com/MSKazemi/idkmesh/issues/471).
