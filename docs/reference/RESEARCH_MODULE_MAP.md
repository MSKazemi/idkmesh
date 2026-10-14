---
description: "Source-by-source research, simulation and interoperability Python reference, with evidence classes and no-authority boundaries."
---
# Research and interoperability code map (as built)

**Code-review baseline:** current public `main` as inspected on 2026-10-13; see the [dated review record](../audits/2026-10-13-nonpackage-python-audit.md) for the pinned revision and validation limits. This map covers **98 direct Python files** in `experiments/`, `interop/`, `sim/`, and `randomness_lab/` (excluding `interop/tests/`). It is source/declaration navigation, **not** an independent line-by-line security review or a release qualification.

**Read this before interpreting results:** `sim/` and `randomness_lab/` primarily model synthetic agents/outcomes, while parts of `experiments/` and E016/E017 consume real observed verdicts or public execution-graded data. Neither synthetic mechanisms, exploratory analysis of already seen data, a passing schema fixture, nor a matched simulation budget automatically demonstrates general real-world agent value. A metadata-only verifier does not execute candidate code; explicit behavioral harnesses operate in separate controlled contexts. `interop/` is an in-process protocol binding, not a network service. All paths grant **no direct permission to approve, push, or merge**.

## How components fit together

```text
experiments/harness.py + project_contracts.py     -> contract/config validity
WorkUnit + bound source + worker candidate         -> ResultManifest
experiments/evaluator_plan_runner.py               -> evaluator-owned verification
experiments/run_evidence_report.py                 -> non-selecting evidence
experiments/replay_run.py                          -> reproducibility comparison
experiments/record_human_decision.py               -> explicit local decision record (no merge)

interop/bindings.py + adapters.py                   -> external agent protocol normalization
sim/ + randomness_lab/                            -> falsifiable research models/analyses
```

Use [source-derived architecture](../architecture/AS_BUILT_IMPLEMENTATION_MAP.md), [protocol specifications](../specifications/README.md), [research index](../research/README.md) and [test practice](../TESTING.md) to distinguish runnable components, tests, and evidence claims.

## `experiments/` (28 source files)

Executable contracts, calibration and bounded two-attempt/reference experiments. Main [experiments guide](https://github.com/MSKazemi/idkmesh/blob/main/experiments/README.md); see [run evidence](../specifications/RUN_EVIDENCE_REPORT_V0_1.md), [EvaluatorPlan](../specifications/EVALUATOR_PLAN_V0_3_SEMANTIC_MATCHING.md) and [research design](../research/SCIENTIFIC_PROGRAM.md).

| Source module | Actual responsibility | Evidence / authority boundary |
| --- | --- | --- |
| [`ace_population_sim.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/ace_population_sim.py) | Seeded ACE open-work capacity simulation | Synthetic only; not live community actuation |
| [`agent_value_forecast.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/agent_value_forecast.py) | Preregistered next-agent value forecasts on pinned public solve matrices | Public-data analysis; changes after the registered code freeze require amendments |
| [`criticality_susceptibility.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/criticality_susceptibility.py) | Matched-seed synthetic queue-stress and recovery study | Engineering queue model, not a physical criticality claim |
| [`evaluator_plan_runner.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/evaluator_plan_runner.py) | Bind WorkUnit/source/validator coverage and dispatch verifier adapters | Evaluator-owned metadata checks; not merge or worker authority |
| [`evaluator_plan_v03.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/evaluator_plan_v03.py) | Additive v0.3 patch-substring evaluator compatibility layer | Binds original plan digest; candidate code stays unexecuted |
| [`forecast_intervals.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/forecast_intervals.py) | Exploratory task/agent bootstrap intervals for next-agent forecast coverage | Post-hoc study of opened splits; frozen E046 forecaster unchanged |
| [`free_compute_router.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/free_compute_router.py) | Select one admitted, policy-compatible compute offer | Selection only; does not allocate resources or run tasks |
| [`harness.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/harness.py) | Phase 0 manifest/schema preflight and deterministic smoke | Smoke executes built-in fixtures only, not manifest-supplied commands |
| [`local_compute_offer.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/local_compute_offer.py) | Conservative local capacity discovery to a compute-offer pool | Discovery only; no remote registration or workload execution |
| [`local_validator.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/local_validator.py) | Path, provenance, artifact and request validation | Metadata-only verifier; does not execute candidate code |
| [`local_verifier.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/local_verifier.py) | Versioned JSON and unified-diff independent checks | Requires jsonschema; no candidate execution or integration |
| [`patch_verifier_v020.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/patch_verifier_v020.py) | Add strict added-line substring semantics to legacy patch checks | Preserves original scope, provenance and integrity constraints |
| [`project_contracts.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/project_contracts.py) | Validate ProjectManifest and DomainPack composition | Configuration only; never loads named adapters |
| [`provenance_integrity.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/provenance_integrity.py) | Cross-object WorkUnit, result and verification digest checks | Detects binding inconsistencies, not semantic correctness |
| [`public_agent_dependence.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/public_agent_dependence.py) | E045 exploratory analysis of public execution-graded agent outcomes | Observed upstream data; not confirmatory due to earlier data exposure |
| [`record_human_decision.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/record_human_decision.py) | Emit and verify an evidence-bound local decision record | Separate explicit human action; no Git push or merge |
| [`replay_run.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/replay_run.py) | Capture and replay bounded two-attempt evidence bundles | Checks reproducibility; does not decide integration |
| [`run_evidence_report.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/run_evidence_report.py) | Validate and render non-selecting run evidence and replay comparisons | Presentation/recommendation, never acceptance authority |
| [`s3_verifier_freeze.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/s3_verifier_freeze.py) | Build calibration-only S3 power plans and content-addressed pre-confirmatory freeze manifests | Preparation only; rejects confirmatory outcome material and never executes patches or verifier models |
| [`submission_provenance.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/submission_provenance.py) | Reanalyze pinned submission results using model/scaffold metadata | No inferred independent-agent identity from shared submissions |
| [`substring_patch_verifier.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/substring_patch_verifier.py) | Metadata-only added-line substring verifier | Never executes candidate code; no path/intent oracle |
| [`temporal_holdout.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/temporal_holdout.py) | E048 preregistered new-submission cohort and frozen analysis replay | Uses only post-pin submissions; not a new statistical method |
| [`transition_patch_verifier.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/transition_patch_verifier.py) | v0.4 added/removed-line transition verifier | Metadata-only semantics; behavioral test is separate |
| [`two_attempt_orchestrator.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/two_attempt_orchestrator.py) | Deterministic isolated attempts via fixtures/result-bundle adapters; further result-only adapters via `register_adapter` | Not a general worker runtime; no candidate code, command execution or merge |
| [`verification_backpressure.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/verification_backpressure.py) | Risk-weighted verifier scheduling and generation throttling | Research reference policy, no actual verification authority |
| [`verification_backpressure_benchmark.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/verification_backpressure_benchmark.py) | Temporal seeded backpressure comparison across schedules | Synthetic hidden truth, not real defect prevalence |
| [`verification_scaling_matrix.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/verification_scaling_matrix.py) | Seven-mode matched synthetic generation/verification benchmark | Simulated acceptance never changes repository state |
| [`work_unit_decomposition.py`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/work_unit_decomposition.py) | Validate and aggregate five-arm WorkUnit decomposition cohorts | Committed examples are infrastructure, not observed efficacy |

## `interop/` (5 source files)

Transport-free A2A/MCP adapter boundary. Main [interop guide](https://github.com/MSKazemi/idkmesh/blob/main/interop/README.md) and [mapping spec](../interoperability/A2A_MCP_MAPPING_V0_1.md). Optional official SDK tests are conditional; skipped tests confer no conformance.

| Source module | Actual responsibility | Evidence / authority boundary |
| --- | --- | --- |
| [`__init__.py`](https://github.com/MSKazemi/idkmesh/blob/main/interop/__init__.py) | Export semantic protocol binding package | No transport or authority |
| [`adapters.py`](https://github.com/MSKazemi/idkmesh/blob/main/interop/adapters.py) | Common worker-adapter interface, local/mock A2A normalization | Worker completion distinct from independent verification |
| [`bindings.py`](https://github.com/MSKazemi/idkmesh/blob/main/interop/bindings.py) | Round-trip WorkUnits through A2A and MCP wire envelopes | Pure in-process mapping, not a network server |
| [`identity.py`](https://github.com/MSKazemi/idkmesh/blob/main/interop/identity.py) | Optional namespaced identity evidence on ResultManifest | Identity never authorizes verification or merge |
| [`sdk_conformance.py`](https://github.com/MSKazemi/idkmesh/blob/main/interop/sdk_conformance.py) | Optional round trips through official pinned protocol SDK types | Unavailable SDKs skip; a skip is not conformance |

## `sim/` (42 source files)

Verifier-error models, coordination, search, and congestion experiments. Main [simulation guide](https://github.com/MSKazemi/idkmesh/blob/main/sim/README.md) and [published experiment records](https://github.com/MSKazemi/idkmesh/blob/main/experiments/README.md). E016/E017 use fixed executable/oracle evidence in addition to synthetic studies.

| Source module | Actual responsibility | Evidence / authority boundary |
| --- | --- | --- |
| [`aco_stigmergy_sim.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/aco_stigmergy_sim.py) | Seeded ACO task-routing ecology compared with simple baselines | Synthetic workers/tasks; no live task assignment |
| [`adaptive_verification_ecology_ablation.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/adaptive_verification_ecology_ablation.py) | Cumulative AVE component ablations | Budget-matched model, not live reviewer evidence |
| [`adaptive_verification_ecology_sim.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/adaptive_verification_ecology_sim.py) | Adaptive Verification Ecology task/worker/verifier toy simulator | Deterministic synthetic mechanism test |
| [`adaptive_verification_ecology_stress.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/adaptive_verification_ecology_stress.py) | AVE-3 parameter and environment stress cases | Synthetic stress grid, no deployment claim |
| [`adaptive_verification_ecology_targeted.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/adaptive_verification_ecology_targeted.py) | Targeted verifier-diversity/risk/backpressure policy comparison | Seeded study; probes remain diagnostic |
| [`e015_analyze.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e015_analyze.py) | Effective-independent-panel-size analysis of E015 grids | Model-derived quantities depend on error assumptions |
| [`e015_quorum_frontier.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e015_quorum_frontier.py) | Cost-weighted quorum optimization over E015 grids | Assumption-bound optimum, not universal acceptance rule |
| [`e015_worker.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e015_worker.py) | Verifier-size, accuracy, correlation and quorum sweep | Synthetic error-dependence grid |
| [`e016_agent.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e016_agent.py) | Run one local open-weight LLM verifier against a fixed corpus | Node-local model call; output is an untrusted verdict |
| [`e016_analyze.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e016_analyze.py) | Analyze observed verifier decisions and shared-error models | Corpus-specific observational analysis, not broad competence |
| [`e016_corpus.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e016_corpus.py) | Build candidate corpus with executable hidden-test ground truth | Executes fixed corpus code; not an untrusted sandbox service |
| [`e017_analyze.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e017_analyze.py) | Fit/compare dependence shapes against measured oracle panels | Panel findings tied to frozen corpus and instrument |
| [`e017_oracles.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e017_oracles.py) | Generate region-scoped executable partial test oracles | Region labels do not prove independence |
| [`e017_verify.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e017_verify.py) | Evaluate partial-oracle panel against executable corpus | Executes controlled candidates; not arbitrary worker integration |
| [`e018_dependence_models.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e018_dependence_models.py) | Recompute quorum/error models under shared-shock versus item difficulty | Closed-form model comparison |
| [`e020_quorum_frontier.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e020_quorum_frontier.py) | Empirical E017 quorum frontier with explicit base rate/costs | Corpus- and cost-dependent optimality only |
| [`e025_learned_verifiers.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e025_learned_verifiers.py) | Learn synthetic reliability and dependence, evaluate held-out streams | Synthetic calibration, not production reputation |
| [`e026_archive_contamination.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e026_archive_contamination.py) | Count false accepts retained in Quality-Diversity archives | Replays synthetic archive with an imperfect panel |
| [`e027_defect_propagation.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e027_defect_propagation.py) | Test cost of downstream accepted-defect propagation | Synthetic catastrophe/quality proxies |
| [`e028_latent_defect_dimension.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e028_latent_defect_dimension.py) | Hide integrity truth from observable candidate quality | Synthetic confound-removal experiment |
| [`e030_supplied_goal_membership.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e030_supplied_goal_membership.py) | Test whether supplied plausible goals contain future target | Goal-set intervention on synthetic search |
| [`e031_learned_goal_filter.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e031_learned_goal_filter.py) | Replace supplied goal hypotheses with learned beliefs | Synthetic learned-goal counterfactual |
| [`e032_population_scaling.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e032_population_scaling.py) | Compare agent count at fixed and growing evaluation budgets | Separates compute budget from population size |
| [`e033_goal_distance.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e033_goal_distance.py) | Sweep distance from plausible-goal set | Synthetic extrapolation over goal geometry |
| [`e034_goal_direction.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e034_goal_direction.py) | Match distance while varying direction of goal change | Controlled directional sensitivity study |
| [`e035_direction_across_shells.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e035_direction_across_shells.py) | Replicate goal-direction effects across multiple distances | Synthetic robustness extension |
| [`e036_adversarial_contributors.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e036_adversarial_contributors.py) | Model contributors optimizing against verification gates | Synthetic adversary, not a live red team |
| [`e037_ladder_under_panels.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e037_ladder_under_panels.py) | Repeat goal-distance/direction effects with imperfect panels | Panel settings are modeled, not field measurements |
| [`e038_symmetric_gate_asymmetric_burden.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e038_symmetric_gate_asymmetric_burden.py) | Study unequal consequences of symmetric gate errors | Synthetic selection-burden mechanism |
| [`e039_content_addressed_blind_spot.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e039_content_addressed_blind_spot.py) | Inspect whether verifier blind spots depend on artifacts | Identifies structural limits of the modeled threat |
| [`e049_derived_measurements.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/e049_derived_measurements.py) | Replay the E024 arms for recovery time, viable-niche coverage and cost per improvement | Post-hoc reader; changes no E024 result; synthetic mechanism evidence only |
| [`emergence_sim.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/emergence_sim.py) | Minimal random/scalar/Quality-Diversity goal-change search | Falsifiable synthetic landscape only |
| [`homeostatic_stigmergy_sim.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/homeostatic_stigmergy_sim.py) | Congestion-governed stigmergic routing controller | Synthetic capacity regulation |
| [`matched_budget_emergence.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/matched_budget_emergence.py) | Five-arm emergence comparison at matched evaluation budgets | Controlled model, not real software productivity |
| [`physarum_compute_routing_sim.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/physarum_compute_routing_sim.py) | Physarum-inspired path choice after hard resource admission | Graph assumes all offers already admitted |
| [`physarum_compute_routing_stress.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/physarum_compute_routing_stress.py) | Compute-path routing under shocks, outages and burden | Synthetic topology; no unreviewed live resource use |
| [`replay_task_routing.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/replay_task_routing.py) | Historical/shadow task-routing replay without look-ahead | Read-only; never assigns GitHub work |
| [`review_capacity_governor.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/review_capacity_governor.py) | E044 bounded logistic review-capacity feedback model | Synthetic queue, no ACE policy mutation |
| [`run_aco_parameter_sweep.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/run_aco_parameter_sweep.py) | ACO parameter grid and Pareto-nondominated policy report | Research tuning on synthetic data |
| [`run_aco_sweep.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/run_aco_sweep.py) | Repeated-seed ACO comparisons across routing baselines | Simulator comparison, not measured contributors |
| [`run_emergence_sweep.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/run_emergence_sweep.py) | Multiseed vague-goal landscape outcomes | Aggregate synthetic seeds and assumptions |
| [`run_verifier_correlation_sweep.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/run_verifier_correlation_sweep.py) | Sensitivity of emergence outcomes to verifier correlation | Correlation modeled, not measured |
| [`verification_aggregation_sim.py`](https://github.com/MSKazemi/idkmesh/blob/main/sim/verification_aggregation_sim.py) | Independence-group-aware versus naive vote aggregation | Synthetic correlated-panel counterfactual |

## `randomness_lab/` (23 source files)

Dependency-free stochastic outcome and policy models, R1-R4. Main [lab guide](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/README.md), [R1 readiness](../research/R1_HELP_HURT_SWEEP.md), and [research program](../research/SCIENTIFIC_PROGRAM.md).

| Source module | Actual responsibility | Evidence / authority boundary |
| --- | --- | --- |
| [`__init__.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/__init__.py) | Public exports for lightweight coordination simulation | Pure research API |
| [`__main__.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/__main__.py) | CLI for single or repeated simulated worker selection | Does not dispatch actual workers |
| [`experiments.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/experiments.py) | Repeated seeded simulation trials and descriptive intervals | Normal-approximation summaries are not external validity |
| [`model.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/model.py) | Worker, Bernoulli and item-difficulty outcome environments | Synthetic success distributions |
| [`policies.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/policies.py) | Greedy, exploration, UCB and Thompson-style selection policy objects | No real provider execution |
| [`r1.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r1.py) | R1 worker-diversity and verifier-panel experiment core | Assumptions must be stated before empirical inference |
| [`r1_communication_burden.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r1_communication_burden.py) | Structural message counts and success-per-message curves over the R1 topology result | Structural, not measured bytes; no content-level duplication |
| [`r1_correlation_threshold.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r1_correlation_threshold.py) | Dependence-threshold sweep for diversity benefit | Parameterized synthetic correlation |
| [`r1_dependence_shape.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r1_dependence_shape.py) | Reassess R1 advantage under an alternative joint-failure shape | Model-shape sensitivity, not measured new panel |
| [`r1_low_diversity_threshold.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r1_low_diversity_threshold.py) | Descriptive low-diversity marginal-gain thresholds | Synthetic sample, not real scaling law |
| [`r1_panel_frontier.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r1_panel_frontier.py) | Full quorum/dependence/billing tradeoff sweep | Cost assumptions change answers |
| [`r1_readiness.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r1_readiness.py) | Fail-closed preflight for real replay benchmark cohort | Readiness checks do not create observations |
| [`r1_replay.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r1_replay.py) | Analyze observed candidate/result bundles as a real R1 cohort | Requires independent evidence; no outcome fabrication |
| [`r1_signature_marginals.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r1_signature_marginals.py) | Read-only per-signature marginal success with Wilson intervals from a saved replay report | Digest-bound summary; refuses synthetic input unless marked; no outcome, no classification |
| [`r1_scaling.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r1_scaling.py) | Matched-attempt R1 population and diversity scaling | Synthetic benchmark family |
| [`r1_sweep.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r1_sweep.py) | Worker/verifier correlation and quality-penalty parameter sweep | Synthetic sensitivity evidence |
| [`r1_threshold_robustness.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r1_threshold_robustness.py) | Bootstrap/sign-test robustness of synthetic thresholds | Diagnostic intervals, not population guarantees |
| [`r1_verifier_dependence.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r1_verifier_dependence.py) | Inspect what verifier-correlation parameter actually couples | Corrects panel-versus-single-verifier interpretation |
| [`r2.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r2.py) | R2 load/capability-aware task-routing model and traces | Synthetic queues and outages |
| [`r2_capability_rarity.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r2_capability_rarity.py) | Rare-capability assignment stress study | Modeled rarity, not live HPC capacity |
| [`r2_factor_sweep.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r2_factor_sweep.py) | Staleness, outage and other R2 factor studies with instrumentation | Controlled model/runtime costs |
| [`r2_scale.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r2_scale.py) | Multi-scale R2 routing regime sweep | Synthetic worker counts, not production scale |
| [`r3.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r3.py) | R3 evolutionary search over orchestration genomes | Simulated task families, not a production optimizer |
| [`r4.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r4.py) | R4 stigmergy and nonstationarity policy comparison | Synthetic shifts and worker outcomes |
| [`simulator.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/simulator.py) | Seeded worker/outcome execution kernel | Outputs simulated booleans, not code test verdicts |

## Reproduce only what the code can show

```bash
# From a checked-out repository with Python 3.11+:
python -m pip install -e '.[verify]'
python scripts/demo.py                         # synthetic contract fixtures
python experiments/two_attempt_orchestrator.py --help
python experiments/replay_run.py --help
python -m randomness_lab --help
python sim/aco_stigmergy_sim.py --help
python -m pytest -q tests/test_nonpackage_module_maps.py
```

Some simulators, behavioral harnesses and real-data studies require additional local artifacts, pinned upstream datasets, controlled runtimes or optional SDKs. Consult their owning guides **before** invoking them; this map is not blanket approval to download data, execute candidate code, or dispatch agents. The [CLI quick reference](CLI_HTTP_QUICK_REFERENCE.md) lists installable-package commands separately.

## Maintenance

The matching [drift test](https://github.com/MSKazemi/idkmesh/blob/main/tests/test_nonpackage_module_maps.py) compares file paths in this table with current direct `*.py` sources. New/moved/removed modules should update this page and the owning guide within the **same PR**; changing historical scientific results still needs the appropriate preregistration/amendment process. The [operational utility map](OPERATIONS_MODULE_MAP.md) covers `tools/` and `scripts/` separately.
