---
description: "As-built source inventory of repository tooling and scripts; operational side effects and research authority boundaries."
---
# Operations and automation Python module map

**Source baseline:** current `main` tree reviewed on 2026-10-13 (see [audit](../audits/2026-10-13-nonpackage-python-audit.md)). Covers **112** direct Python modules under `tools/` and `scripts/`. These are checkout tools, not installed `idkmesh` CLI subcommands. This is a source navigation inventory based on module descriptions and entry points, not an execution audit or independent security review.

**Caution:** not every script is read-only. `tools/jules_dispatcher.py`, `tools/openhands_pilot.py`, `tools/auto_draft_pr_steward.py`, `tools/publish_starter_tasks.py`, `tools/submit_indexnow.py`, and observation collectors interact with external systems under explicit arguments, credentials, or GitHub Actions. Never execute them merely to check documentation. Some frozen-node, model, and acceptance harnesses execute code in restricted controlled environments. Use [agent instructions](https://github.com/MSKazemi/idkmesh/blob/main/AGENTS.md), [testing](../TESTING.md), [Jules operations](../operations/JULES_AUTOMATION.md), and [safety policy](https://github.com/MSKazemi/idkmesh/blob/main/PROJECT_RULES.md).

## API and release (11)

API qualification, schema evolution, or declared release metadata; local checks are not certification.

| Source | Operator-facing purpose |
| --- | --- |
| [`tools/api_beta_readiness.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/api_beta_readiness.py) | API beta readiness gate |
| [`tools/api_clean_install_demo.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/api_clean_install_demo.py) | API clean install demo gate |
| [`tools/api_load_soak.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/api_load_soak.py) | API load soak gate |
| [`tools/api_release_qualification.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/api_release_qualification.py) | API release qualification gate |
| [`tools/build_release_supply_chain.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/build_release_supply_chain.py) | build release supply chain |
| [`tools/check_release_version.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/check_release_version.py) | check release version |
| [`tools/enterprise_profile.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/enterprise_profile.py) | enterprise profile |
| [`tools/openapi_catalog.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/openapi_catalog.py) | API opencatalog gate |
| [`tools/openapi_ref_check.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/openapi_ref_check.py) | API openref check gate |
| [`tools/schema_compat_check.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/schema_compat_check.py) | schema compat check |
| [`tools/schema_migration_note_check.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/schema_migration_note_check.py) | schema migration note check |

## GitHub and agent actuation (8)

May contact GitHub/providers or publish only through explicit trusted action; inspect policy before running.

| Source | Operator-facing purpose |
| --- | --- |
| [`scripts/checkpoint_manifest.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/checkpoint_manifest.py) | checkpoint manifest |
| [`scripts/issue_model_router.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/issue_model_router.py) | issue model router |
| [`tools/auto_draft_pr_steward.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/auto_draft_pr_steward.py) | auto draft pr steward |
| [`tools/check_jules_contract.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/check_jules_contract.py) | Jules check contract operation |
| [`tools/github_atomic_commit.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/github_atomic_commit.py) | github atomic commit |
| [`tools/jules_dispatcher.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/jules_dispatcher.py) | Jules dispatcher operation |
| [`tools/openhands_pilot.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/openhands_pilot.py) | openhands pilot |
| [`tools/publish_starter_tasks.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/publish_starter_tasks.py) | publish starter tasks |

## Frozen benchmark and real-node evidence (28)

Evidence or calibration for frozen tasks; some scripts execute trusted behavioral probes or local models.

| Source | Operator-facing purpose |
| --- | --- |
| [`tools/benchmark_cohort.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/benchmark_cohort.py) | benchmark cohort |
| [`tools/benchmark_publication.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/benchmark_publication.py) | benchmark publication |
| [`tools/node_runtime_acceptance.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/node_runtime_acceptance.py) | Controlled real-node node runtime acceptance evidence harness |
| [`tools/node_verifier_e2e.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/node_verifier_e2e.py) | Controlled real-node node verifier e2e evidence harness |
| [`tools/node_verifier_e2e_current.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/node_verifier_e2e_current.py) | Controlled real-node node verifier e2e current evidence harness |
| [`tools/open_model_benchmark_probe.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/open_model_benchmark_probe.py) | Local open-model benchmark probe harness |
| [`tools/open_model_probe_summary.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/open_model_probe_summary.py) | Local open-model probe summary harness |
| [`tools/open_model_text_generator.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/open_model_text_generator.py) | Local open-model text generator harness |
| [`tools/phase_b2_successor_task002_evidence.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/phase_b2_successor_task002_evidence.py) | Frozen task/benchmark phase b2 successor task002 evidence evidence or calibration |
| [`tools/phase_b2_successor_task003_evidence.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/phase_b2_successor_task003_evidence.py) | Frozen task/benchmark phase b2 successor task003 evidence evidence or calibration |
| [`tools/phase_b2_successor_task004_evidence.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/phase_b2_successor_task004_evidence.py) | Frozen task/benchmark phase b2 successor task004 evidence evidence or calibration |
| [`tools/phase_b2_successor_task005_evidence.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/phase_b2_successor_task005_evidence.py) | Frozen task/benchmark phase b2 successor task005 evidence evidence or calibration |
| [`tools/phase_b2_task001_burn_evidence.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/phase_b2_task001_burn_evidence.py) | Frozen task/benchmark phase b2 task001 burn evidence evidence or calibration |
| [`tools/phase_b2_task001_evaluator_probe.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/phase_b2_task001_evaluator_probe.py) | Frozen task/benchmark phase b2 task001 evaluator probe evidence or calibration |
| [`tools/phase_b2_task001_evidence.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/phase_b2_task001_evidence.py) | Frozen task/benchmark phase b2 task001 evidence evidence or calibration |
| [`tools/phase_b2_task001_v03_calibration.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/phase_b2_task001_v03_calibration.py) | Frozen task/benchmark phase b2 task001 v03 calibration evidence or calibration |
| [`tools/real_mixed_outcome_e2e.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/real_mixed_outcome_e2e.py) | Controlled real-node real mixed outcome e2e evidence harness |
| [`tools/real_node_verifier_e2e.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/real_node_verifier_e2e.py) | Controlled real-node real node verifier e2e evidence harness |
| [`tools/real_two_attempt_e2e.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/real_two_attempt_e2e.py) | Controlled real-node real two attempt e2e evidence harness |
| [`tools/real_two_attempt_evidence_e2e.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/real_two_attempt_evidence_e2e.py) | Controlled real-node real two attempt evidence e2e evidence harness |
| [`tools/task001_cohort_symlink_calibration.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/task001_cohort_symlink_calibration.py) | Frozen task/benchmark task001 cohort symlink calibration evidence or calibration |
| [`tools/task001_evaluator_calibration_v04.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/task001_evaluator_calibration_v04.py) | Frozen task/benchmark task001 evaluator calibration v04 evidence or calibration |
| [`tools/task001_evaluator_calibration_v04_ci.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/task001_evaluator_calibration_v04_ci.py) | Frozen task/benchmark task001 evaluator calibration v04 ci evidence or calibration |
| [`tools/task001_real_transition_calibration.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/task001_real_transition_calibration.py) | Controlled real-node Frozen task/benchmark task001 real transition calibration evidence or calibration evidence harness |
| [`tools/task002_router_nonfinite_calibration.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/task002_router_nonfinite_calibration.py) | Frozen task/benchmark task002 router nonfinite calibration evidence or calibration |
| [`tools/task003_branch_unobserved_head_calibration.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/task003_branch_unobserved_head_calibration.py) | Frozen task/benchmark task003 branch unobserved head calibration evidence or calibration |
| [`tools/task004_rwvb_nonfinite_calibration.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/task004_rwvb_nonfinite_calibration.py) | Frozen task/benchmark task004 rwvb nonfinite calibration evidence or calibration |
| [`tools/task005_local_offer_output_calibration.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/task005_local_offer_output_calibration.py) | Frozen task/benchmark task005 local offer output calibration evidence or calibration |

## IDKGraph and documentation (16)

Local structure, evidence, links, or documentation validation and rendering; source files may be generated.

| Source | Operator-facing purpose |
| --- | --- |
| [`scripts/check_capability_matrix.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/check_capability_matrix.py) | check capability matrix |
| [`scripts/check_links.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/check_links.py) | check links |
| [`scripts/idkgraph_check.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/idkgraph_check.py) | IDKGraph check tool |
| [`tools/build_question_index.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/build_question_index.py) | build question index |
| [`tools/build_sitemap.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/build_sitemap.py) | build sitemap |
| [`tools/closing_keyword_guard.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/closing_keyword_guard.py) | closing keyword guard |
| [`tools/contributor_command_guard.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/contributor_command_guard.py) | contributor command guard |
| [`tools/github_idkgraph_projection.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/github_idkgraph_projection.py) | IDKGraph github projection tool |
| [`tools/idkgraph_health_checks.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/idkgraph_health_checks.py) | IDKGraph health checks tool |
| [`tools/idkgraph_link_check.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/idkgraph_link_check.py) | IDKGraph link check tool |
| [`tools/idkgraph_markdown_index.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/idkgraph_markdown_index.py) | IDKGraph markdown index tool |
| [`tools/idkgraph_observatory.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/idkgraph_observatory.py) | IDKGraph observatory tool |
| [`tools/idkgraph_repository_mapping.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/idkgraph_repository_mapping.py) | IDKGraph repository mapping tool |
| [`tools/idkgraph_review_session.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/idkgraph_review_session.py) | IDKGraph review session tool |
| [`tools/idkgraph_warning_sample.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/idkgraph_warning_sample.py) | IDKGraph warning sample tool |
| [`tools/idkgraph_workunit_cycles.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/idkgraph_workunit_cycles.py) | IDKGraph workunit cycles tool |

## Research policy and evolution (30)

Research/evolution/admission observation, recommendation, or offline gate; no implicit integration authority.

| Source | Operator-facing purpose |
| --- | --- |
| [`scripts/ace_activation_gate.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/ace_activation_gate.py) | ace activation gate |
| [`scripts/ace_generation_controller.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/ace_generation_controller.py) | ace generation controller |
| [`scripts/ace_lineage.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/ace_lineage.py) | ace lineage |
| [`scripts/anytime_drift_guard.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/anytime_drift_guard.py) | anytime drift guard |
| [`scripts/collaboration_observables.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/collaboration_observables.py) | collaboration observables |
| [`scripts/collaboration_snapshot.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/collaboration_snapshot.py) | collaboration snapshot |
| [`scripts/conjunctive_evolution_control.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/conjunctive_evolution_control.py) | conjunctive evolution control |
| [`scripts/evidence_aggregation_fabric.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/evidence_aggregation_fabric.py) | evidence aggregation fabric |
| [`scripts/evolution_live_governor.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/evolution_live_governor.py) | evolution live governor |
| [`scripts/evolution_math.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/evolution_math.py) | evolution math |
| [`scripts/evolution_score.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/evolution_score.py) | evolution score |
| [`scripts/evolution_snapshot.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/evolution_snapshot.py) | evolution snapshot |
| [`scripts/free_resource_planner.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/free_resource_planner.py) | free resource planner |
| [`scripts/free_resource_source_audit.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/free_resource_source_audit.py) | free resource source audit |
| [`scripts/metric_uncertainty.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/metric_uncertainty.py) | metric uncertainty |
| [`scripts/prereg_first_review_latency.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/prereg_first_review_latency.py) | prereg first review latency |
| [`scripts/repository_evolution_score.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/repository_evolution_score.py) | repository evolution score |
| [`scripts/repository_portfolio.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/repository_portfolio.py) | repository portfolio |
| [`scripts/resource_compute_admission.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/resource_compute_admission.py) | resource compute admission |
| [`scripts/sequential_evidence.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/sequential_evidence.py) | sequential evidence |
| [`tools/adaptive_policy_cohort.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/adaptive_policy_cohort.py) | adaptive policy cohort |
| [`tools/adaptive_policy_evidence_cli.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/adaptive_policy_evidence_cli.py) | adaptive policy evidence cli |
| [`tools/adaptive_policy_outcome.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/adaptive_policy_outcome.py) | adaptive policy outcome |
| [`tools/adaptive_policy_shadow.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/adaptive_policy_shadow.py) | adaptive policy shadow |
| [`tools/ave_shadow_adapter.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/ave_shadow_adapter.py) | ave shadow adapter |
| [`tools/ave_shadow_adapter_cli.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/ave_shadow_adapter_cli.py) | ave shadow adapter cli |
| [`tools/branch_convergence_audit.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/branch_convergence_audit.py) | branch convergence audit |
| [`tools/branch_merge_planner.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/branch_merge_planner.py) | branch merge planner |
| [`tools/ci_shadow_evaluator.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/ci_shadow_evaluator.py) | ci shadow evaluator |
| [`tools/ci_shadow_planner.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/ci_shadow_planner.py) | ci shadow planner |

## Web discovery and visibility (10)

Web discovery collection, analysis or publication; some commands make authenticated/external requests.

| Source | Operator-facing purpose |
| --- | --- |
| [`scripts/bing_ai_performance_import.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/bing_ai_performance_import.py) | Search visibility bing ai performance import tool |
| [`scripts/discovery_query_portfolio.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/discovery_query_portfolio.py) | discovery query portfolio |
| [`scripts/search_console_snapshot.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/search_console_snapshot.py) | Search visibility search console snapshot tool |
| [`scripts/search_visibility_observation_import.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/search_visibility_observation_import.py) | Search visibility search visibility observation import tool |
| [`scripts/search_visibility_observation_plan.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/search_visibility_observation_plan.py) | Search visibility search visibility observation plan tool |
| [`scripts/visibility_growth_selector.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/visibility_growth_selector.py) | Search visibility visibility growth selector tool |
| [`scripts/visibility_observatory.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/visibility_observatory.py) | Search visibility visibility observatory tool |
| [`tools/check_public_discovery.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/check_public_discovery.py) | check public discovery |
| [`tools/search_visibility_report.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/search_visibility_report.py) | Search visibility search visibility report tool |
| [`tools/submit_indexnow.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/submit_indexnow.py) | Search visibility submit indexnow tool |

## Developer tools (9)

Developer validation or controlled acceptance; inspect execution and optional runtime requirements.

| Source | Operator-facing purpose |
| --- | --- |
| [`scripts/adversarial_evidence_guard.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/adversarial_evidence_guard.py) | adversarial evidence guard |
| [`scripts/authority_reference_ledger.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/authority_reference_ledger.py) | authority reference ledger |
| [`scripts/byo_agent_challenge.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/byo_agent_challenge.py) | byo agent challenge |
| [`scripts/demo.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/demo.py) | demo |
| [`scripts/github_traffic_snapshot.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/github_traffic_snapshot.py) | github traffic snapshot |
| [`scripts/pr91_acceptance.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/pr91_acceptance.py) | pr91 acceptance |
| [`scripts/smoke_openai_compatible.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/smoke_openai_compatible.py) | smoke openai compatible |
| [`scripts/testkit.py`](https://github.com/MSKazemi/idkmesh/blob/main/scripts/testkit.py) | testkit |
| [`tools/issue_evidence_gate.py`](https://github.com/MSKazemi/idkmesh/blob/main/tools/issue_evidence_gate.py) | issue evidence gate |

## How to validate without executing mutations

```bash
python -m pytest -q tests/test_nonpackage_module_maps.py
python scripts/testkit.py auto
python tools/openapi_ref_check.py
```

These are example local checks, not evidence they were executed in this review. Any use of real-provider, GitHub-publishing, model-execution, Docker, or external data tools must follow the owner-provided policy and relevant prerequisite instructions; no broad invocation is implied. The [research/interoperability map](RESEARCH_MODULE_MAP.md) and [installable module map](MODULE_MAP.md) cover the remaining runtime and experimental Python sources. The [drift test](https://github.com/MSKazemi/idkmesh/blob/main/tests/test_nonpackage_module_maps.py) enforces one source link per direct module.
