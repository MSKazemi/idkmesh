// GENERATED FILE - DO NOT EDIT.
// Generator: tools/generate_api_types.py (issue #746). Regenerate with:
//   python tools/generate_api_types.py
// Source: openapi.yaml and the JSON Schemas in schemas/ it catalogs.
// OpenAPI: IDKMesh API v1 (version 0.1).
//
// Declarations only: no runtime code, no network access, nothing to publish.
// Mapping: integer and number -> number; const/enum -> literal unions; nullable
// types -> `| null`; allOf -> `&`; anyOf/oneOf -> `|`. Value constraints (pattern,
// minimum, uniqueItems, if/then/else, ...) are NOT encoded: every document that
// validates against a schema is assignable to its type, but assignable values
// are not guaranteed valid. The JSON Schema in schemas/ remains the authority.

/** Any JSON value: the explicit type for schemas that constrain nothing. */
export type IdkmeshJsonValue =
  | string
  | number
  | boolean
  | null
  | IdkmeshJsonValue[]
  | { [key: string]: IdkmeshJsonValue };

/** Header carrying the `LocalSessionToken` credential. */
export type LocalSessionTokenHeaderName = "X-IDKMesh-UI-Token";

/** A minimal evidence edge linking a verified parent, a Growth Seed, and a candidate or verified descendant. */
export type AceLineageV01 = {
  version: "0.1";
  lineage_id?: string;
  parent: AceLineageV01_ArtifactRef;
  seed: AceLineageV01_ArtifactRef;
  descendant: AceLineageV01_ArtifactRef;
  descendant_type: "reproduce" | "extend" | "challenge" | "explain" | "translate" | "secure" | "measure" | "connect" | "review" | "onboard" | "other";
  status: "candidate" | "merged" | "verified" | "rejected";
  recorded_at: string;
  actor?: string;
  reviewer_minutes?: number;
  verification?: AceLineageV01_Verification;
  metadata?: { [key: string]: string | number | boolean | null };
};

export type AceLineageV01_ArtifactRef = {
  repo: string;
  kind: "issue" | "pr" | "commit";
  number?: number;
  sha?: string;
};

export type AceLineageV01_Verification = {
  method: "label" | "tests" | "review" | "reproduction" | "manual";
  evidence_refs: string[];
  verified_at: string;
  verifier?: string;
};

/** A descriptive evaluation of immutable adaptive-policy shadow plans joined to observed real-process outcomes. It does not estimate an unobserved counterfactual policy effect. */
export type AdaptivePolicyCohortSummaryV01 = {
  schema_version: "0.1";
  kind: "idkmesh-adaptive-policy-cohort-summary";
  evaluator_version: "0.1";
  summary_id: string;
  policy_ids: string[];
  counts: {
    plans: number;
    outcomes: number;
    joined: number;
    missing_outcomes: number;
    duplicate_outcomes_rejected: 0;
  };
  disagreement: {
    shadow_vs_baseline_comparable: number;
    shadow_vs_baseline_disagree: number;
    shadow_vs_baseline_disagreement_rate: number | null;
    shadow_matches_actual: number;
    baseline_matches_actual: number;
    neither_matches_actual: number;
  };
  observed_outcomes: {
    known_outcomes: number;
    successful: number;
    success_rate: number | null;
    escaped_defects: number;
    escaped_defect_rate: number | null;
    high_risk_escapes: number;
    high_risk_escape_rate: number | null;
    mean_verified_utility: number | null;
  };
  measurement_coverage: {
    verified_utility: AdaptivePolicyCohortSummaryV01_Coverage;
    escaped_defect: AdaptivePolicyCohortSummaryV01_Coverage;
    high_risk_escape: AdaptivePolicyCohortSummaryV01_Coverage;
    project_spend_usd: AdaptivePolicyCohortSummaryV01_Coverage;
    compute_units: AdaptivePolicyCohortSummaryV01_Coverage;
    review_units: AdaptivePolicyCohortSummaryV01_Coverage;
    human_attention_units: AdaptivePolicyCohortSummaryV01_Coverage;
  };
  identifiability: {
    descriptive_only: true;
    shadow_counterfactual_observed: false;
    causal_effect_estimate: null;
    promotion_decision_automatic: false;
  };
  limitations: string[];
  authority: {
    evidence_only: true;
    dispatch: false;
    execute: false;
    approve: false;
    merge: false;
    repository_write: false;
  };
};

export type AdaptivePolicyCohortSummaryV01_Coverage = {
  observed: number;
  total: number;
  rate: number | null;
};

/** A retrospective outcome record joined to an immutable adaptive-policy shadow plan. It records observed real-process outcomes without pretending an unexecuted shadow recommendation has an observed counterfactual outcome. */
export type AdaptivePolicyOutcomeV01 = {
  schema_version: "0.1";
  kind: "idkmesh-adaptive-policy-outcome";
  evaluator_version: "0.1";
  record_id: string;
  plan_id: string;
  plan_digest: AdaptivePolicyOutcomeV01_Digest;
  binding: {
    repository: string;
    source_revision_sha: AdaptivePolicyOutcomeV01_Sha;
    input_digest: AdaptivePolicyOutcomeV01_Digest;
  };
  observed_process: {
    actual_choice_id: string | null;
    observed_at: string;
    outcome: "succeeded" | "failed" | "rejected" | "abstained" | "unknown";
    verified_utility: number | null;
    escaped_defect: boolean | null;
    high_risk_escape: boolean | null;
    actual_cost: {
      project_spend_usd: number | null;
      compute_units: number | null;
      review_units: number | null;
      human_attention_units: number | null;
    };
  };
  comparison: {
    shadow_choice_id: string | null;
    baseline_choice_id: string | null;
    shadow_matches_actual: boolean | null;
    baseline_matches_actual: boolean | null;
    shadow_counterfactual_observed: false;
    causal_claim_allowed: false;
  };
  evidence_refs: string[];
  limitations: string[];
  authority: {
    evidence_only: true;
    dispatch: false;
    execute: false;
    approve: false;
    merge: false;
    repository_write: false;
  };
};

export type AdaptivePolicyOutcomeV01_Digest = string;

export type AdaptivePolicyOutcomeV01_Sha = string;

/** A non-authoritative exact-revision recommendation emitted by an adaptive policy operating only inside a hard-gated eligible set. */
export type AdaptivePolicyPlanV01 = {
  schema_version: "0.1";
  kind: "idkmesh-adaptive-policy-plan";
  planner_version: "0.1";
  mode: "shadow";
  plan_id: string;
  subsystem: "task-routing" | "verification-allocation" | "compute-path-routing" | "community-policy" | "other";
  binding: {
    repository: string;
    source_revision_sha: AdaptivePolicyPlanV01_Sha;
    captured_at: string;
    input_digest: AdaptivePolicyPlanV01_Digest;
    input_refs: string[];
  };
  policy: {
    id: string;
    version: string;
    maturity: "N1" | "N2" | "N3";
  };
  hard_gates: AdaptivePolicyPlanV01_Gate[];
  eligible_choices: AdaptivePolicyPlanV01_Choice[];
  recommendation: {
    selected_choice_id: string | null;
    baseline_choice_id: string | null;
    exploration: boolean;
    reasons: string[];
    uncertainty: number | null;
    expected_cost: {
      project_spend_usd: 0;
      compute_units: number | null;
      review_units: number | null;
      human_attention_units: number | null;
    };
  };
  evidence_refs: string[];
  limitations: string[];
  authority: {
    advisory_only: true;
    dispatch: false;
    execute: false;
    approve: false;
    merge: false;
    repository_write: false;
    relax_hard_gates: false;
    modify_required_verification: false;
    authorize_project_spend: false;
  };
};

export type AdaptivePolicyPlanV01_Choice = {
  id: string;
  class: string;
  reasons: string[];
  metrics: { [key: string]: number | string | boolean | null };
};

export type AdaptivePolicyPlanV01_Digest = string;

export type AdaptivePolicyPlanV01_Gate = {
  id: string;
  status: "pass" | "fail";
  reason: string;
};

export type AdaptivePolicyPlanV01_Sha = string;

/** Offline aggregation of validated Auto Draft PR Steward reports. It is evidence only and grants no repository mutation authority. */
export type AutoDraftPrStewardHistoryV01 = {
  schema: "auto-draft-pr-steward-history-v0.1";
  repository: string;
  report_count: number;
  first_generated_at: string;
  last_generated_at: string;
  status_counts: {
    completed: number;
    blocked: number;
    disabled: number;
  };
  outcome_totals: {
    planned: number;
    created: number;
    skipped: number;
    head_moved: number;
    pr_already_exists: number;
  };
  api_budget: {
    observed_runs: number;
    min_remaining: number | null;
    max_remaining: number | null;
  };
  policy: {
    distinct_digests: number;
    changes: number;
    latest_sha256: string;
  };
  integrity: {
    algorithm: "sha256";
    semantic_normalization: "validated-canonical-json-v0.1";
    input_set_sha256: string;
  };
  runs: AutoDraftPrStewardHistoryV01_Run[];
};

export type AutoDraftPrStewardHistoryV01_Run = {
  source: string;
  generated_at: string;
  status: "completed" | "blocked" | "disabled";
  candidate_count: number | null;
  planned: number;
  created: number;
  skipped: number;
  head_moved: number;
  pr_already_exists: number;
  rate_limit_remaining: number | null;
  blocked_reason: string | null;
  policy_sha256: string;
  report_sha256: string;
  run_id: string | null;
  run_attempt: string | null;
  trusted_head_sha: string | null;
};

/** Durable evidence for one Auto Draft PR Steward run. The report records observations and bounded Draft-PR creation outcomes; it never grants review, merge, branch-deletion, issue-closing, or repository-settings authority. */
export type AutoDraftPrStewardReportV01 = {
  schema: "auto-draft-pr-steward-report-v0.1";
  repository: string;
  generated_at: string;
  status: "completed" | "blocked" | "disabled";
  dry_run: boolean;
  policy: {
    path: string;
    sha256: string;
  };
  provenance: {
    workflow: string | null;
    run_id: string | null;
    run_attempt: string | null;
    trusted_head_sha: string | null;
  };
  authority: {
    draft_pr_create: true;
    ready_for_review: false;
    approve: false;
    merge: false;
    auto_merge: false;
    delete_branch: false;
    close_issue: false;
    label_write: false;
    contents_write: false;
    repository_settings: false;
  };
  candidate_count: number | null;
  rate_limit_remaining: number | null;
  blocked_reason: string | null;
  summary: {
    planned: number;
    created: number;
    skipped: number;
  };
  planned: AutoDraftPrStewardReportV01_PlannedCandidate[];
  created: AutoDraftPrStewardReportV01_CreatedCandidate[];
  skipped: AutoDraftPrStewardReportV01_SkippedCandidate[];
};

export type AutoDraftPrStewardReportV01_CandidateCore = {
  branch: string;
  base: string;
  head_sha: string;
  ahead_by: number;
  behind_by: number;
};

export type AutoDraftPrStewardReportV01_CreatedCandidate = AutoDraftPrStewardReportV01_CandidateCore & {
  number: number;
  url: string;
};

export type AutoDraftPrStewardReportV01_PlannedCandidate = AutoDraftPrStewardReportV01_CandidateCore;

export type AutoDraftPrStewardReportV01_SkippedCandidate = AutoDraftPrStewardReportV01_CandidateCore & ({
  reason: "head_moved" | "pr_already_exists";
  current_head_sha?: string;
});

/** A thin, non-executing index that freezes task taxonomy and binds existing WorkUnit, EvaluatorPlan, ResultManifest, and VerificationResult evidence without replacing those canonical contracts. */
export type BenchmarkCohortV01 = {
  schema_version: "0.1";
  id: string;
  title: string;
  description?: string;
  stage: "scaffold" | "collecting" | "frozen" | "burned";
  minimum_final_tasks: number;
  required_families: ("bug_fix" | "test_failure" | "bounded_feature" | "refactor" | "documentation_contract" | "other")[];
  taxonomy_frozen_before_outcomes: true;
  definition_digest?: string;
  authority: {
    canonical_state_write: false;
    git_push: false;
    merge: false;
    automatic_candidate_selection: false;
  };
  tasks: BenchmarkCohortV01_Task[];
  extensions?: { [key: string]: IdkmeshJsonValue };
};

export type BenchmarkCohortV01_Attempt = {
  attempt_id: string;
  structural_signature: string;
  result_manifest: BenchmarkCohortV01_Object_ref;
  verification_result: BenchmarkCohortV01_Object_ref;
  outcome: "support" | "reject" | "escalate" | "insufficient_evidence";
};

export type BenchmarkCohortV01_Digest = string;

export type BenchmarkCohortV01_Object_ref = {
  path: BenchmarkCohortV01_Path;
  digest: BenchmarkCohortV01_Digest;
  id: string;
};

export type BenchmarkCohortV01_Path = string;

export type BenchmarkCohortV01_Task = {
  id: string;
  family: "bug_fix" | "test_failure" | "bounded_feature" | "refactor" | "documentation_contract" | "other";
  difficulty: "trivial" | "small" | "medium" | "large";
  split: "pilot" | "train" | "development" | "held_out";
  source: {
    repository: string;
    revision: string;
  };
  work_unit: {
    path: BenchmarkCohortV01_Path;
    digest: BenchmarkCohortV01_Digest;
    id: string;
    version: number;
  };
  evaluator: {
    visibility: "public" | "hidden";
    plan_id: string;
    plan_digest: BenchmarkCohortV01_Digest;
    backend: string;
    plan_path?: BenchmarkCohortV01_Path;
  };
  declared_structural_signatures: string[];
  negative_case: {
    description: string;
    expected_category: "correctness" | "scope" | "provenance" | "security" | "regression" | "worker_error" | "verifier_error" | "other";
    evidence_status: "pending" | "verified";
    evidence_type?: "verification_result" | "run_record" | "other";
    evidence_path?: BenchmarkCohortV01_Path;
    evidence_digest?: BenchmarkCohortV01_Digest;
  };
  accounting: {
    required_metrics: ("wall_seconds" | "compute_units" | "human_minutes" | "tokens")[];
  };
  evidence: {
    status: "pending" | "verified" | "excluded";
    exclusion_reason?: string;
    attempts: BenchmarkCohortV01_Attempt[];
  };
};

/** Provider-neutral immutable identity for a candidate artifact. A CandidateReference is not a verification result, acceptance verdict, or integration authority. */
export type CandidateReferenceV01 = {
  schema_version: "0.1";
  type: "github_pull_request";
  repository: string;
  number: number;
  head_sha: string;
} | {
  schema_version: "0.1";
  type: "artifact_bundle";
  locator: string;
  digest: string;
  media_type?: string;
};

/** An exact-revision comparison of a shadow CI plan with observed checks. It cannot promote selective CI or authorize integration. */
export type CiEvaluationV01 = {
  schema_version: "0.1";
  kind: "idkmesh-ci-evaluation";
  evaluator_version: "0.1";
  mode: "shadow";
  head_sha: CiEvaluationV01_Sha;
  plan_id: string;
  plan_digest: CiEvaluationV01_Digest;
  observation_digest: CiEvaluationV01_Digest;
  policy_digest: CiEvaluationV01_Digest;
  status: "complete" | "provisional";
  selected_logical_checks: string[];
  failed_checks: CiEvaluationV01_Failure[];
  missed_mapped_failures: CiEvaluationV01_Failure[];
  unattributed_failures: CiEvaluationV01_Failure[];
  metrics: {
    observed_check_count: number;
    observed_failure_count: number;
    mapped_failure_count: number;
    covered_mapped_failure_count: number;
    missed_mapped_failure_count: number;
    unattributed_failure_count: number;
    mapped_failure_recall: number | null;
    modeled_full_portfolio_seconds: number;
    modeled_selected_seconds: number;
    modeled_avoided_seconds: number;
    modeled_savings_ratio: number;
  };
  promotion: {
    eligible: false;
    reasons: string[];
  };
  authority: CiEvaluationV01_Authority;
  evaluation_id: string;
};

export type CiEvaluationV01_Authority = {
  evidence_only: true;
  execute: false;
  skip_required_checks: false;
  approve: false;
  merge: false;
  repository_write: false;
};

export type CiEvaluationV01_Digest = string;

export type CiEvaluationV01_Failure = {
  check_run_id: number;
  workflow_name: string | null;
  name: string;
  conclusion: string;
  mapped_logical_check_ids: string[];
  covered_by_selected: string[];
};

export type CiEvaluationV01_Sha = string;

/** A normalized exact-revision snapshot of GitHub check runs. It is evidence only and grants no CI or integration authority. */
export type CiObservationV01 = {
  schema_version: "0.1";
  kind: "idkmesh-ci-observation";
  evaluator_version: "0.1";
  source: "github-check-runs";
  head_sha: CiObservationV01_Sha;
  policy_digest: CiObservationV01_Digest;
  checks: CiObservationV01_Check[];
  completeness: {
    baseline_complete: boolean;
    baseline_successful: boolean;
    pending_observed_checks: number;
    required_contexts: {
      workflow_name: string;
      check_name: string;
      present: boolean;
      terminal: boolean;
      successful: boolean;
    }[];
  };
  authority: CiObservationV01_Authority;
};

export type CiObservationV01_Authority = {
  evidence_only: true;
  execute: false;
  skip_required_checks: false;
  approve: false;
  merge: false;
  repository_write: false;
};

export type CiObservationV01_Check = {
  check_run_id: number;
  workflow_name: string | null;
  name: string;
  app_slug: string;
  status: string;
  conclusion: string | null;
  started_at: string | null;
  completed_at: string | null;
  details_url: string | null;
};

export type CiObservationV01_Digest = string;

export type CiObservationV01_Sha = string;

/** A deterministic shadow-mode recommendation for exact-revision CI coverage. It cannot skip required checks or authorize integration. */
export type CiPlanV01 = {
  schema_version: "0.1";
  kind: "idkmesh-ci-plan";
  planner_version: "0.1";
  mode: "shadow";
  plan_id: string;
  repository: string;
  base_sha: CiPlanV01_Sha;
  head_sha: CiPlanV01_Sha;
  policy_digest: CiPlanV01_Digest;
  changed_files: string[];
  risk: {
    class: "R0" | "R1" | "R2" | "R3";
    matched_rules: string[];
    unmatched_files: string[];
  };
  budget: {
    optional_seconds: number;
    selected_optional_seconds: number;
    project_spend_usd_max: 0;
  };
  checks: CiPlanV01_Check[];
  summary: {
    mandatory: string[];
    selected_optional: string[];
    exploration: string[];
    not_selected: string[];
    full_suite_baseline_required: true;
  };
  authority: {
    advisory_only: true;
    execute: false;
    skip_required_checks: false;
    approve: false;
    merge: false;
    repository_write: false;
  };
};

export type CiPlanV01_Check = {
  id: string;
  lane: "mandatory" | "optional" | "not-impacted";
  selected: boolean;
  exploration: boolean;
  reasons: string[];
  matched_files: string[];
  dependencies: string[];
  estimated_seconds: number;
  score: number | null;
};

export type CiPlanV01_Digest = string;

export type CiPlanV01_Sha = string;

/** An exact-revision receipt proving that a shadow CI plan was emitted. It is not an execution result or integration verdict. */
export type CiReceiptV01 = {
  schema_version: "0.1";
  kind: "idkmesh-ci-receipt";
  planner_version: "0.1";
  receipt_id: string;
  stage: "planning";
  outcome: "shadow_plan_emitted";
  plan_id: string;
  plan_digest: CiReceiptV01_Digest;
  base_sha: CiReceiptV01_Sha;
  head_sha: CiReceiptV01_Sha;
  executed_checks: [];
  actual_cost: {
    project_spend_usd: 0;
    check_execution_seconds: 0;
    planner_execution_seconds: null;
    planner_resource_use_measured: false;
    external_resource_cost_zero_claim: false;
  };
  authority: {
    evidence_only: true;
    execute: false;
    skip_required_checks: false;
    approve: false;
    merge: false;
    repository_write: false;
  };
};

export type CiReceiptV01_Digest = string;

export type CiReceiptV01_Sha = string;

/** Provider-neutral execution offers used by the free-first compute router. Monetary cost is cost charged to the IDKMesh project, not hidden donor electricity or hardware cost. */
export type ComputeOfferPoolV01 = {
  schema_version: "0.1";
  offers: ComputeOfferPoolV01_Offer[];
};

export type ComputeOfferPoolV01_Offer = {
  id: string;
  provider: string;
  cost_class: "local_owned" | "donated" | "public_project_ci" | "grant" | "free_tier" | "paid";
  project_cost_usd: number;
  available: boolean;
  trust: "untrusted" | "identified" | "trusted" | "attested";
  capabilities: string[];
  resources: {
    cpu_cores: number;
    memory_mb: number;
    disk_mb: number;
    gpu: boolean;
    accelerator_capabilities?: string[];
  };
  expected_wait_seconds: number;
  success_probability: number;
  independence_group: string;
  notes?: string;
};

/** Repository-level hard constraints applied before any Work Unit-specific budget. Work Units may tighten these constraints but may not relax them. */
export type ComputePolicyV01 = {
  schema_version: "0.1";
  project_spend_usd_max: number;
  paid_providers_enabled: boolean;
  allowed_cost_classes: ("local_owned" | "donated" | "public_project_ci" | "grant" | "free_tier" | "paid")[];
  donor_costs_must_be_opt_in: boolean;
  notes?: string;
};

/** A deterministic, read-only human-facing projection of one validated Run Evidence Report v0.1. It separates worker claims, independent evidence/recommendations, attention conditions, and pending human authority without selecting or integrating a candidate. */
export type ControlTowerSnapshotV01 = {
  api_version: "v1";
  schema_version: "0.1";
  kind: "idkmesh-control-tower-snapshot";
  source: {
    kind: "idkmesh-run-evidence-report";
    evidence_report_digest: ControlTowerSnapshotV01_Digest;
    schema_version: "0.1";
    run_id: string;
    source_run_digest: ControlTowerSnapshotV01_Digest;
    source_config_digest: ControlTowerSnapshotV01_Digest;
    verifier_policy_digest: ControlTowerSnapshotV01_Digest;
  };
  work_unit: {
    id: string;
    version: number;
    digest: ControlTowerSnapshotV01_Digest;
  };
  summary: {
    attempt_count: number;
    supported: number;
    rejected: number;
    inconclusive: number;
    control_errors: number;
    verification_disagreement: boolean;
    control_failure_present: boolean;
  };
  attention: ControlTowerSnapshotV01_Attention[];
  attempts: ControlTowerSnapshotV01_Attempt[];
  timeline: ControlTowerSnapshotV01_Event[];
  warnings: string[];
  human_decision: {
    status: "pending";
    selected_attempt_id: null;
    integration_authority: "external_human_or_governance";
  };
  authority: {
    canonical_state_write: false;
    git_push: false;
    merge: false;
    automatic_candidate_selection: false;
  };
  interpretation_rules: string[];
  provenance: ControlTowerSnapshotV01_Provenance;
};

export type ControlTowerSnapshotV01_Attempt = {
  attempt_id: string;
  order: number;
  state: "verified" | "worker_error" | "result_manifest_error" | "verification_error";
  evidence_state: "supported" | "rejected" | "inconclusive" | "worker_error" | "result_manifest_error" | "verification_error";
  worker_adapter: string;
  claim: ControlTowerSnapshotV01_Claim;
  evidence: ControlTowerSnapshotV01_Evidence;
  error: string | null;
};

export type ControlTowerSnapshotV01_Attention = {
  severity: "high" | "medium" | "action";
  code: string;
  title: string;
  why: string;
};

export type ControlTowerSnapshotV01_Check = {
  id: string;
  status: string;
  required: boolean;
};

export type ControlTowerSnapshotV01_Claim = {
  worker_id: string;
  worker_status: string;
  result_manifest_id: string;
  result_manifest_digest: ControlTowerSnapshotV01_Digest;
} | null;

export type ControlTowerSnapshotV01_Digest = string;

export type ControlTowerSnapshotV01_Event = {
  sequence: number;
  type: "observation" | "claim" | "evidence" | "recommendation" | "control_error" | "attention" | "authority";
  title: string;
  detail: string;
  actor: string | null;
  attempt_id: string | null;
  evidence_ref: ControlTowerSnapshotV01_Digest | null;
};

export type ControlTowerSnapshotV01_Evidence = {
  verifier_id: string;
  verifier_status: string;
  recommendation: "accept_candidate" | "reject_candidate" | "escalate" | "insufficient_evidence";
  verification_digest: ControlTowerSnapshotV01_Digest;
  checks: ControlTowerSnapshotV01_Check[];
} | null;

export type ControlTowerSnapshotV01_Provenance = {
  work_unit: {
    id: string;
    version: number;
    digest: ControlTowerSnapshotV01_Digest;
  };
  run: {
    run_id: string;
    source_run_digest: ControlTowerSnapshotV01_Digest;
    source_config_digest: ControlTowerSnapshotV01_Digest;
    verifier_policy_digest: ControlTowerSnapshotV01_Digest;
    orchestrator_version: string;
  };
  attempts: ControlTowerSnapshotV01_ProvenanceAttempt[];
  authority: {
    canonical_state_write: false;
    git_push: false;
    merge: false;
    automatic_candidate_selection: false;
    human_decision_status: "pending";
    integration_authority: "external_human_or_governance";
  };
};

export type ControlTowerSnapshotV01_ProvenanceAttempt = {
  attempt_id: string;
  order: number;
  worker_adapter: string;
  result_manifest: ControlTowerSnapshotV01_ProvenanceResultManifest;
  verification: ControlTowerSnapshotV01_ProvenanceVerification;
  evidence_state: "supported" | "rejected" | "inconclusive" | "worker_error" | "result_manifest_error" | "verification_error";
  error: string | null;
};

export type ControlTowerSnapshotV01_ProvenanceRequiredCheck = {
  id: string;
  status: string;
};

export type ControlTowerSnapshotV01_ProvenanceResultManifest = {
  worker_id: string;
  worker_status: string;
  result_manifest_id: string;
  result_manifest_digest: ControlTowerSnapshotV01_Digest;
} | null;

export type ControlTowerSnapshotV01_ProvenanceVerification = {
  verifier_id: string;
  verifier_status: string;
  recommendation: "accept_candidate" | "reject_candidate" | "escalate" | "insufficient_evidence";
  verification_semantic_digest: ControlTowerSnapshotV01_Digest;
  required_checks: ControlTowerSnapshotV01_ProvenanceRequiredCheck[];
  identity_distinct_from_worker: boolean;
  independence_claim: string;
} | null;

export type ControlTowerSnapshotV01_Provenance_attempt = {
  attempt_id: string;
  order: number;
  worker_adapter: string;
  result_manifest: ControlTowerSnapshotV01_Provenance_result_manifest;
  verification: ControlTowerSnapshotV01_Provenance_verification;
  evidence_state: "supported" | "rejected" | "inconclusive" | "worker_error" | "result_manifest_error" | "verification_error";
  error: string | null;
};

export type ControlTowerSnapshotV01_Provenance_required_check = {
  id: string;
  status: string;
};

export type ControlTowerSnapshotV01_Provenance_result_manifest = {
  worker_id: string;
  worker_status: string;
  result_manifest_id: string;
  result_manifest_digest: ControlTowerSnapshotV01_Digest;
} | null;

export type ControlTowerSnapshotV01_Provenance_verification = {
  verifier_id: string;
  verifier_status: string;
  recommendation: "accept_candidate" | "reject_candidate" | "escalate" | "insufficient_evidence";
  verification_semantic_digest: ControlTowerSnapshotV01_Digest;
  required_checks: ControlTowerSnapshotV01_Provenance_required_check[];
  identity_distinct_from_worker: boolean;
  independence_claim: string;
} | null;

/** Read-only local dependency and declared-effort recommendation. Does not admit, execute, verify, accept or integrate work. */
export type CoordinationPreflightV01 = {
  kind: "idkmesh-coordination-preflight";
  schema_version: "0.1";
  scope: CoordinationPreflightV01_Scope;
  graph_digest: CoordinationPreflightV01_Digest;
  observation_digest: CoordinationPreflightV01_Digest;
  binding: CoordinationPreflightV01_Binding;
  inputs_digest: CoordinationPreflightV01_Digest | null;
  ready: boolean;
  satisfied: boolean;
  blockers: string[];
  prerequisite_pins: CoordinationPreflightV01_Observation[];
  effort: {
    components: number | null;
    ambiguity: CoordinationPreflightV01_EffortClass;
    coupling: CoordinationPreflightV01_EffortClass;
    execution_seconds: CoordinationPreflightV01_Duration;
    verification_minutes: CoordinationPreflightV01_Duration;
    integration_minutes: CoordinationPreflightV01_Duration;
    estimate_source: CoordinationPreflightV01_Text;
    deterministic_operation: boolean;
  };
  capability: {
    trusted_floor: CoordinationPreflightV01_Tier;
    recommended_tier: CoordinationPreflightV01_Tier | null;
    reasons: string[];
    expected_total_seconds: number | null;
    evidence_class: "declared_estimate";
  };
  routing: {
    authority_mode: "deterministic" | "agent_candidate" | "human_gate_then_agent" | "human_required";
    risk_class: "low" | "medium" | "high" | "critical";
    project_spend_usd_max: 0.0;
    eligible: {
      connection_id: string;
      supported_tier: CoordinationPreflightV01_Tier;
    }[];
    ineligible: {
      connection_id: string;
      reasons: string[];
    }[];
    recommended_connection_id: string | null;
    selection_reason: string[];
  };
  authority: {
    dispatch: false;
    executes_worker: false;
    accepts_candidate: false;
    merge: false;
  };
};

export type CoordinationPreflightV01_Binding = {
  work_unit_id: string;
  work_unit_version: number;
  work_unit_digest: CoordinationPreflightV01_Digest;
  source_revision: CoordinationPreflightV01_Revision;
};

export type CoordinationPreflightV01_Digest = string;

export type CoordinationPreflightV01_Duration = number | null;

export type CoordinationPreflightV01_EffortClass = "low" | "medium" | "high" | "unknown";

export type CoordinationPreflightV01_Observation = {
  scope: CoordinationPreflightV01_Scope;
  event_id: CoordinationPreflightV01_Text;
  sequence: number;
  binding: CoordinationPreflightV01_Binding;
  state: "pending" | "candidate" | "integrated" | "rejected";
  inputs_digest: CoordinationPreflightV01_Digest;
  integrated_revision: CoordinationPreflightV01_Revision | null;
  artifacts_digest: CoordinationPreflightV01_Digest | null;
  verification_reference: CoordinationPreflightV01_Text | null;
  integration_reference: CoordinationPreflightV01_Text | null;
};

export type CoordinationPreflightV01_Revision = string;

export type CoordinationPreflightV01_Scope = {
  tenant_id: string;
  project_id: string;
};

export type CoordinationPreflightV01_Text = string;

export type CoordinationPreflightV01_Tier = "T0" | "T1" | "T2" | "T3" | "T4";

/** A five-arm decomposition comparison with explicit per-unit observations and evidence classification. */
export type DecompositionBenchmarkV01 = {
  schema_version: "0.1";
  benchmark_id: string;
  task_class: string;
  task_description: string;
  /** Synthetic fixtures test infrastructure only; only observed independent runs may support scientific claims. */
  evidence_class: "synthetic_fixture" | "observed";
  workers: ({
    id: string;
    worker_type: "human" | "agent" | "hybrid" | "synthetic";
    implementation: string;
    revision: string;
  })[];
  provenance: {
    source: string;
    source_revision: string;
    recorded_by: string;
  };
  arms: DecompositionBenchmarkV01_Arm[];
};

export type DecompositionBenchmarkV01_Arm = {
  strategy: "monolithic" | "human_subtasks" | "file_module" | "dependency_dag" | "formal_work_units";
  units: DecompositionBenchmarkV01_Unit[];
  observations: DecompositionBenchmarkV01_Observation[];
};

export type DecompositionBenchmarkV01_Observation = {
  attempt_id: string;
  worker_id: string;
  unit_id: string;
  completed: boolean;
  integration_failed: boolean;
  merge_conflicts: number;
  rework_cycles: number;
  context_bytes: number;
  cross_worker_messages: number;
  hidden_tests_passed: number;
  hidden_tests_total: number;
  assumption_mismatches: number;
  dependency_violations: number;
  verification_seconds: number;
  human_integration_minutes: number;
};

export type DecompositionBenchmarkV01_Unit = {
  id: string;
  description: string;
  dependencies: string[];
  allowed_paths: string[];
  global_context_required: boolean;
  formal_work_unit_path?: string;
};

/** Declares domain-specific Work Unit kinds, verification policies, roles, risk defaults, adapters, and metrics without changing IDKMesh Core. */
export type DomainPack = {
  schema_version: "0.1";
  id: string;
  version: string;
  name: string;
  description?: string;
  core_compatibility: {
    core_api_version: string;
    work_unit_schema_version: string;
  };
  work_unit_kinds: ({
    kind: "coding" | "testing" | "review" | "benchmarking" | "documentation" | "research" | "integration" | "governance" | "other";
    default_risk_class: "low" | "medium" | "high" | "critical";
    required_verification_policy: string;
    required_capabilities: string[];
    required_evidence: ("test_output" | "review" | "benchmark" | "citation" | "trace" | "attestation" | "artifact_hash" | "other")[];
  })[];
  verification_policies: ({
    id: string;
    strategy: "all_required" | "quorum" | "threshold" | "custom";
    independent_from_worker: boolean;
    minimum_independent_verifiers: number;
    human_integration_required: boolean;
    description?: string;
  })[];
  worker_roles: {
    id: string;
    description?: string;
    required_capabilities: string[];
  }[];
  risk_classes: ({
    id: "low" | "medium" | "high" | "critical";
    sandbox_required: boolean;
    human_review_required: boolean;
    description?: string;
  })[];
  adapters: {
    definitions: ({
      id: string;
      interface: string;
      discovery: "builtin" | "registry" | "project-manifest" | "external";
      trust_boundary: string;
    })[];
    required: string[];
    optional: string[];
  };
  metrics: {
    default: string[];
  };
  compatibility: {
    backward_compatible_with: string[];
    breaking_change_policy: string;
  };
};

export type E025LearnedVerifierResult = {
  schema_version: "e025.learned-verifier-results.v1";
  experiment: "E025-learned-verifier-reliability-dependence";
  configuration: {
    seed_start: number;
    seeds: number;
    history_trials: number[];
    heldout_trials: number;
    panel: {
      name: string;
      group: string;
      accuracy: number;
    }[];
    correlation_threshold: number;
    methods: ("naive_majority" | "declared_group_oracle" | "inferred_dependence_groups" | "effective_sample_heuristic" | "empirical_effective_evidence" | "bayesian_reliability" | "combined_reliability_dependence")[];
    uncertainty: string;
  };
  separation: {
    calibration_seed_formula: string;
    heldout_seed_formula: string;
    frozen_model_before_heldout: true;
    heldout_truth_available_to_aggregator: false;
    matched_heldout_votes_across_methods: true;
  };
  findings: {
    stable_improvement_cells: number;
    shift_harm_cells: number;
    improvement_observed: boolean;
    harm_observed: boolean;
    production_reputation_claim: false;
  };
  cells: ({
    scenario: "stable_shared_shock" | "stable_item_difficulty" | "reliability_shift" | "dependence_dissipates" | "dependence_emerges";
    purpose: string;
    history_trials: number;
    heldout_trials: number;
    calibration: E025LearnedVerifierResult_StreamConfig;
    heldout: E025LearnedVerifierResult_StreamConfig;
    metrics: {
      naive_majority: E025LearnedVerifierResult_MethodMetrics;
      declared_group_oracle: E025LearnedVerifierResult_MethodMetrics;
      inferred_dependence_groups: E025LearnedVerifierResult_MethodMetrics;
      effective_sample_heuristic: E025LearnedVerifierResult_MethodMetrics;
      empirical_effective_evidence: E025LearnedVerifierResult_MethodMetrics;
      bayesian_reliability: E025LearnedVerifierResult_MethodMetrics;
      combined_reliability_dependence: E025LearnedVerifierResult_MethodMetrics;
    };
    correlation_estimation: E025LearnedVerifierResult_CorrelationDiagnostics;
    heldout_correlation_misspecification: E025LearnedVerifierResult_CorrelationDiagnostics;
    effective_evidence: E025LearnedVerifierResult_EvidenceDiagnostics;
    model_uncertainty: {
      mean_accuracy_ci95_width: E025LearnedVerifierResult_Summary;
      interval: string;
    };
    stream_identity: {
      distinct_calibration_digests: number;
      distinct_heldout_digests: number;
    };
  })[];
  limitations: string[];
};

export type E025LearnedVerifierResult_CorrelationDiagnostics = {
  pairwise_correlation_mae: E025LearnedVerifierResult_Summary;
  pairwise_correlation_signed_error: E025LearnedVerifierResult_Summary;
  overestimated_independence_pair_rate: E025LearnedVerifierResult_Summary;
  underestimated_independence_pair_rate: E025LearnedVerifierResult_Summary;
  exact_group_recovery: E025LearnedVerifierResult_Summary;
};

export type E025LearnedVerifierResult_EvidenceDiagnostics = {
  learned_rho_heuristic_total: E025LearnedVerifierResult_Summary;
  true_rho_heuristic_total: E025LearnedVerifierResult_Summary;
  calibration_observed_effective_total: E025LearnedVerifierResult_Summary;
  nominal_verifiers: E025LearnedVerifierResult_Summary;
};

export type E025LearnedVerifierResult_MethodMetrics = {
  false_accept_rate: E025LearnedVerifierResult_Summary;
  false_reject_rate: E025LearnedVerifierResult_Summary;
  error_rate: E025LearnedVerifierResult_Summary;
  brier_score: E025LearnedVerifierResult_Summary;
  mean_confidence: E025LearnedVerifierResult_Summary;
  high_confidence_error_rate: E025LearnedVerifierResult_Summary;
};

export type E025LearnedVerifierResult_StreamConfig = {
  correlation: number;
  dependence: "shared-shock" | "item-difficulty";
  accuracy: number[];
};

export type E025LearnedVerifierResult_Summary = {
  n: number;
  mean: number;
  stdev: number;
  ci95_low: number;
  ci95_high: number;
  min: number;
  max: number;
};

/** Normalized trusted identity claims for enterprise authorization. This object must be produced by a trusted authentication adapter; task/issue/model text is not an identity source. */
export type EnterpriseActorContextV01 = {
  kind: "idkmesh-enterprise-actor-context";
  schema_version: "0.1";
  principal_id: string;
  actor_type: "human" | "github_app" | "github_actions" | "service" | "provider" | "node";
  issuer: string;
  roles: ("owner" | "admin" | "integrator" | "worker" | "reviewer" | "dispatcher" | "node_operator" | "auditor")[];
  scopes: {
    tenant_id: string;
    project_id: string;
  }[];
  data_clearance: "public" | "internal" | "confidential" | "restricted";
  identity_revision: string;
  authenticated: boolean;
  revoked: boolean;
  expires_at_epoch: number | null;
};

/** Compact tamper-evident enterprise security/audit evidence. Events are append-only, hash-chained and evidence-only; they grant no execution, canonical-state-write, Git-push, or merge authority. */
export type EnterpriseAuditEventV01 = {
  kind: "idkmesh-enterprise-audit-event";
  schema_version: "0.1";
  event_id: string;
  sequence: number;
  occurred_at_epoch: number;
  scope: {
    tenant_id: string;
    project_id: string;
  };
  correlation: {
    request_id: string;
    run_id: string | null;
  };
  actor: EnterpriseAuditEventV01_Identity;
  service: EnterpriseAuditEventV01_Identity & ({
    actor_type?: "github_app" | "github_actions" | "service" | "node";
  });
  action: "read" | "claim" | "release" | "dispatch" | "execute" | "verify" | "integrate" | "decide" | "manage_policy" | "audit_export";
  resource: {
    resource_type: string;
    resource_id: string;
    revision: string;
  };
  authorization: {
    effect: "allow" | "deny" | "requires_approval";
    reason_code: string;
    approved_by: string | null;
    approval_reference: string | null;
    policy_id: string;
    policy_revision: string;
    decision_digest: EnterpriseAuditEventV01_Digest;
  };
  outcome: "succeeded" | "failed" | "denied" | "not_executed";
  evidence_digest: EnterpriseAuditEventV01_Digest | null;
  retention: {
    minimum_days: number;
    eligible_after_epoch: number;
  };
  previous_event_digest: EnterpriseAuditEventV01_Digest | null;
  event_digest: EnterpriseAuditEventV01_Digest;
  authority: {
    audit_only: true;
    authorizes_action: false;
    canonical_state_write: false;
    git_push: false;
    merge: false;
  };
};

export type EnterpriseAuditEventV01_Digest = string;

export type EnterpriseAuditEventV01_Identity = {
  principal_id: string;
  actor_type: "human" | "github_app" | "github_actions" | "service" | "provider" | "node";
  issuer: string;
  identity_revision: string;
};

/** Deterministic authorization evidence for one scoped request. The object records an allow/deny/approval-required result but performs no action and carries no merge/canonical-write authority itself. */
export type EnterpriseAuthorizationDecisionV01 = {
  kind: "idkmesh-enterprise-authorization-decision";
  schema_version: "0.1";
  effect: "allow" | "deny" | "requires_approval";
  code: string;
  message: string;
  request_id: string;
  principal_id: string;
  action: "read" | "claim" | "release" | "dispatch" | "execute" | "verify" | "integrate" | "decide" | "manage_policy" | "audit_export";
  resource: {
    tenant_id: string;
    project_id: string;
    resource_type: string;
    resource_id: string;
  };
  requested_risk: "low" | "medium" | "high" | "critical";
  effective_risk: "low" | "medium" | "high" | "critical";
  data_classification: "public" | "internal" | "confidential" | "restricted";
  policy: {
    policy_id: string;
    revision: string;
  };
  identity_revision: string;
  evaluated_at_epoch: number;
  approved_by: string | null;
  approval_reference: string | null;
  authority: {
    executes_action: false;
    canonical_state_write: false;
    merge: false;
  };
};

/** An explicit, time-bounded, reason-carrying temporary role elevation for one human principal in exactly one tenant/project (E3-E, issue #670). A grant can only change a role_denied outcome: scope, revocation, expiry, data clearance, executor separation and high-risk distinct approval are still evaluated by idkmesh.enterprise_authz. The document is policy evidence only; it executes nothing and carries no canonical-write or merge authority. Do not put credentials in reason; it is retained verbatim. */
export type EnterpriseBreakGlassGrantV01 = {
  kind: "idkmesh-enterprise-break-glass-grant";
  schema_version: "0.1";
  grant_id: string;
  scope: {
    tenant_id: string;
    project_id: string;
  };
  incident_id: string;
  reason: string;
  beneficiary_principal_id: string;
  beneficiary_identity_revision: string;
  approver_principal_id: string;
  approver_identity_revision: string;
  granted_roles: ("integrator" | "worker" | "reviewer" | "dispatcher" | "node_operator")[];
  actions: ("read" | "claim" | "release" | "dispatch" | "execute" | "verify" | "integrate")[];
  max_risk: "low" | "medium" | "high";
  max_data_classification: "public" | "internal" | "confidential";
  policy_id: string;
  policy_revision: string;
  issued_at_epoch: number;
  expires_at_epoch: number;
};

export type EnterpriseControlProfileBaselineV01 = {
  api_version: "idkmesh.io/v1alpha1";
  kind: "EnterpriseControlProfile";
  metadata: {
    name: string;
    environment: "development" | "staging" | "production";
    enforcement_mode: "audit" | "enforce";
  };
  deployment: {
    profile: "G0" | "G1" | "G2" | "G3";
    tenant_mode: "single_project" | "single_organization" | "multi_tenant";
    tenant_isolation: "not_applicable" | "declared" | "enforced";
    network_mode: "public" | "controlled_egress" | "private_network";
  };
  identity: {
    human_identity_source: "github" | "enterprise_sso" | "oidc" | "saml";
    service_identity: "github_actions" | "github_app" | "oidc_workload" | "managed_identity";
    mfa_required: boolean;
    high_risk_separation_of_duties: boolean;
  };
  data: {
    default_classification: "public" | "internal" | "confidential" | "restricted";
    external_processing_allowed_classes: ("public" | "internal" | "confidential" | "restricted")[];
    egress_mode: "unrestricted" | "allowlist" | "deny_by_default";
  };
  secrets: {
    backend: "github_environment" | "external_secret_manager" | "provider_managed";
    workload_identity: "none" | "github_oidc" | "external_oidc" | "managed_identity";
    long_lived_cloud_keys_allowed: boolean;
  };
  audit: {
    append_only: boolean;
    integrity: "git_history" | "hash_chain" | "external_worm";
    retention_days: number;
    external_export_required: boolean;
    actor_policy_revision_required: boolean;
  };
  reliability: {
    availability_target_percent: number;
    rpo_minutes: number;
    rto_minutes: number;
    restore_test_interval_days: number;
    backpressure_required: boolean;
  };
  supply_chain: {
    immutable_action_pins_required: boolean;
    sbom_required: boolean;
    provenance_attestation_required: boolean;
    vulnerability_response_sla_hours: number;
  };
  change_management: {
    high_risk_two_person_rule: boolean;
    break_glass: {
      enabled: boolean;
      time_bound_minutes: number;
      reason_required: boolean;
      audit_required: boolean;
    };
  };
};

/** Declared enterprise deployment/control policy input. The profile describes intended controls and grants no runtime authority or evidence that a control is actually enforced. */
export type EnterpriseControlProfileV01 = {
  kind: "idkmesh-enterprise-control-profile";
  schema_version: "0.1";
  profile_id: string;
  semantics: {
    profile_role: "policy_input_only";
    control_evidence: "declared_not_observed";
    grants_runtime_authority: false;
  };
  deployment: {
    profile: "g0_local_operator" | "g1_github_native_team" | "g2_self_hosted_team" | "g3_multi_tenant_service";
    tenant_scope: "single_project" | "single_org" | "multi_tenant";
    remote_api_enabled: boolean;
    coordinator_lifecycle: "local_process" | "github_actions_ephemeral" | "long_lived_service";
    canonical_code_authority: "github_protected_integration";
  };
  identity: {
    human_source: "local_trusted_operator" | "github" | "oidc" | "saml" | "external";
    service_source: "process" | "github_actions" | "oidc" | "mtls" | "external";
    high_risk_distinct_approval: boolean;
    break_glass_enabled: boolean;
  };
  authority: {
    worker_can_merge: false;
    verifier_can_merge: false;
    worker_can_modify_policy: false;
    integration_authority: "github_protected_integration" | "external_human_or_governance";
  };
  data: {
    default_classification: "public" | "internal" | "confidential" | "restricted";
    allowed_classifications: ("public" | "internal" | "confidential" | "restricted")[];
    external_processing: {
      public: boolean;
      internal: boolean;
      confidential: boolean;
      restricted: boolean;
    };
    egress_default: "deny" | "allow";
  };
  secrets: {
    backend: "none" | "environment" | "github_actions" | "oidc_workload_identity" | "external_secret_manager";
    long_lived_cloud_keys_allowed: boolean;
    raw_secret_material_in_work_units: false;
    raw_secret_material_in_evidence: false;
  };
  audit: {
    enabled: boolean;
    tamper_evident_required: boolean;
    retention_days: number;
    export: "none" | "file" | "siem" | "archive";
  };
  reliability: {
    availability_target: number;
    rpo_minutes: number;
    rto_minutes: number;
    backups_required: boolean;
    restore_test_required: boolean;
  };
  supply_chain: {
    immutable_action_pins_required: boolean;
    sbom_required: boolean;
    provenance_required: boolean;
    vulnerability_response_sla_hours: number;
  };
  change_management: {
    protected_integration_required: boolean;
    policy_change_approval_required: boolean;
    break_glass_reason_required: boolean;
  };
  enforcement: {
    mode: "audit" | "enforce";
    unknown_control_behavior: "warn" | "fail";
    startup_profile_validation: true;
  };
};

/** Maintainer-reviewed classification-vs-destination egress policy (E5, issue #672). Each destination is an exact lowercase fully qualified hostname with a trust zone and the explicit data classes it may receive. Policy input to idkmesh.enterprise_egress_policy, evaluated together with an enterprise control profile; deny by default, non-compensating. It grants no runtime authority and must never contain credentials. */
export type EnterpriseEgressPolicyV01 = {
  kind: "idkmesh-enterprise-egress-policy";
  schema_version: "0.1";
  policy_id: EnterpriseEgressPolicyV01_Identifier;
  semantics: {
    policy_role: "policy_input_only";
    grants_runtime_authority: false;
  };
  destinations: ({
    destination_id: EnterpriseEgressPolicyV01_Identifier;
    /** Exact lowercase fully qualified hostname. No wildcard, URL, port, userinfo or IP literal; the final label must start with a letter. */
    host: string;
    zone: "internal" | "external_provider" | "external_public";
    /** Explicit list, not a ceiling: each class is cleared independently. */
    allowed_classes: ("public" | "internal" | "confidential" | "restricted")[];
    provider_id?: EnterpriseEgressPolicyV01_Identifier;
  })[];
};

export type EnterpriseEgressPolicyV01_Identifier = string;

/** Maintainer-reviewed table binding trusted numeric GitHub actor ids to enterprise ActorContext roles, tenant/project scopes, and data clearance (E3-B, issue #670). The numeric actor id is the primary trust key. This is config input to idkmesh.enterprise_identity_github; issue/PR/comment text is never a binding source. */
export type EnterpriseGithubIdentityBindingV01 = {
  kind: "idkmesh-enterprise-github-identity-binding-table";
  schema_version: "0.1";
  bindings: ({
    /** Trusted numeric GitHub actor id; the primary trust key for this binding. */
    actor_id: number;
    /** Expected GitHub login for actor_id. A login match with a different actor_id, or an actor_id with a different login, is denied. */
    login: string;
    /** GitHub identities cannot be a service/provider/node ActorContext actor_type. */
    actor_type: "human" | "github_app" | "github_actions";
    issuer: string;
    roles: ("owner" | "admin" | "integrator" | "worker" | "reviewer" | "dispatcher" | "node_operator" | "auditor")[];
    scopes: {
      tenant_id: string;
      project_id: string;
    }[];
    data_clearance: "public" | "internal" | "confidential" | "restricted";
    identity_revision: string;
    revoked: boolean;
    expires_at_epoch: number | null;
  })[];
};

/** Maintainer-reviewed table binding trusted (issuer, subject) enterprise IdP claim pairs to enterprise ActorContext roles, tenant/project scopes, and data clearance (E3-C, issue #670). The (issuer, subject) pair is the primary trust key. This is config input to idkmesh.enterprise_identity_oidc; issue/PR/comment text is never a binding source. */
export type EnterpriseOidcIdentityBindingV01 = {
  kind: "idkmesh-enterprise-oidc-identity-binding-table";
  schema_version: "0.1";
  bindings: ({
    /** Trusted IdP issuer (the verified token/assertion's iss). Half of the primary trust key. */
    issuer: string;
    /** Trusted IdP subject (the verified token/assertion's sub). Only unique within its issuer, so the primary trust key is the (issuer, subject) pair, not subject alone. */
    subject: string;
    /** Expected relying-party audience (aud) for this binding. Claims whose audience does not match are denied rather than trusted. */
    audience: string;
    /** Enterprise IdP identities cannot be a github_app/github_actions/provider/node ActorContext actor_type. */
    actor_type: "human" | "service";
    roles: ("owner" | "admin" | "integrator" | "worker" | "reviewer" | "dispatcher" | "node_operator" | "auditor")[];
    scopes: {
      tenant_id: string;
      project_id: string;
    }[];
    data_clearance: "public" | "internal" | "confidential" | "restricted";
    identity_revision: string;
    revoked: boolean;
    expires_at_epoch: number | null;
  })[];
};

/** Tenant/project-scoped reference for enterprise operational resources. Scope is part of identity and cannot be inferred from an unscoped resource id. */
export type EnterpriseResourceRefV01 = {
  kind: "idkmesh-enterprise-resource-ref";
  schema_version: "0.1";
  tenant_id: string;
  project_id: string;
  resource_type: string;
  resource_id: string;
};

/** Verifier-owned metadata-only plan binding deterministic evaluator policy to one exact WorkUnit and source revision. */
export type EvaluatorPlanV01 = {
  schema_version: "0.1";
  id: string;
  binding: {
    work_unit_id: string;
    work_unit_version: number;
    work_unit_digest: string;
    source_revision: string;
  };
  visibility: "public" | "hidden";
  execution_mode: "metadata_only";
  verifier: {
    id: "idkmesh-local-verifier";
    type: "system";
    adapter: "deterministic-json-verifier";
    adapter_version: "0.1";
  };
  required_validator_ids: string[];
  candidate_artifact_id: string;
  allowed_files: string[];
  max_candidate_bytes: number;
  required_json: { [key: string]: IdkmeshJsonValue };
  policy: {
    require_plan_outside_candidate_root: true;
    require_output_outside_candidate_root: true;
    require_verifier_distinct_from_worker: true;
  };
  extensions?: { [key: string]: IdkmeshJsonValue };
};

/** Verifier-owned metadata-only plan binding a deterministic unified-diff evaluator to one exact WorkUnit and source revision. */
export type EvaluatorPlanV02 = {
  schema_version: "0.2";
  id: string;
  binding: {
    work_unit_id: string;
    work_unit_version: number;
    work_unit_digest: string;
    source_revision: string;
  };
  visibility: "public" | "hidden";
  execution_mode: "metadata_only";
  verifier: {
    id: "idkmesh-local-verifier";
    type: "system";
    adapter: "deterministic-patch-verifier";
    adapter_version: "0.1.1";
  };
  required_validator_ids: string[];
  candidate_artifact_id: string;
  backend: {
    type: "unified_diff";
    max_candidate_bytes: number;
    max_log_bytes: number;
    required_log_types: ("stdout" | "stderr" | "trace" | "tool_calls" | "other")[];
    required_added_text: string[];
    require_nonempty_patch: true;
    verify_log_digests: true;
  };
  policy: {
    require_plan_outside_candidate_root: true;
    require_output_outside_candidate_root: true;
    require_verifier_distinct_from_worker: true;
  };
  extensions?: { [key: string]: IdkmeshJsonValue };
};

/** Verifier-owned metadata-only plan binding deterministic unified-diff verification to one exact WorkUnit and source revision. v0.3 adds explicit case-sensitive per-added-line substring matching without changing v0.2 exact-line semantics. */
export type EvaluatorPlanV03 = {
  schema_version: "0.3";
  id: string;
  binding: {
    work_unit_id: string;
    work_unit_version: number;
    work_unit_digest: string;
    source_revision: string;
  };
  visibility: "public" | "hidden";
  execution_mode: "metadata_only";
  verifier: {
    id: "idkmesh-local-verifier";
    type: "system";
    adapter: "deterministic-patch-verifier";
    adapter_version: "0.2.0";
  };
  required_validator_ids: string[];
  candidate_artifact_id: string;
  backend: {
    type: "unified_diff";
    max_candidate_bytes: number;
    max_log_bytes: number;
    required_log_types: ("stdout" | "stderr" | "trace" | "tool_calls" | "other")[];
    /** Every value must occur, case-sensitively and contiguously, within at least one single added line inside a structurally valid unified-diff hunk. Matching does not span lines and is not regex-based. */
    required_added_substrings: string[];
    require_nonempty_patch: true;
    verify_log_digests: true;
  };
  policy: {
    require_plan_outside_candidate_root: true;
    require_output_outside_candidate_root: true;
    require_verifier_distinct_from_worker: true;
  };
  extensions?: { [key: string]: IdkmeshJsonValue };
};

/** Verifier-owned metadata-only plan binding deterministic unified-diff verification to one exact WorkUnit and source revision. v0.4 adds explicit case-sensitive added-and-removed line substring transition semantics without changing v0.2 exact-line or v0.3 added-substring behavior. */
export type EvaluatorPlanV04 = {
  schema_version: "0.4";
  id: string;
  binding: {
    work_unit_id: string;
    work_unit_version: number;
    work_unit_digest: string;
    source_revision: string;
  };
  visibility: "public" | "hidden";
  execution_mode: "metadata_only";
  verifier: {
    id: "idkmesh-local-verifier";
    type: "system";
    adapter: "deterministic-patch-verifier";
    adapter_version: "0.3.0";
  };
  required_validator_ids: string[];
  candidate_artifact_id: string;
  backend: {
    type: "unified_diff";
    max_candidate_bytes: number;
    max_log_bytes: number;
    required_log_types: ("stdout" | "stderr" | "trace" | "tool_calls" | "other")[];
    /** Every value must occur, case-sensitively and contiguously, within at least one single added line inside a structurally valid unified-diff hunk. Matching does not span lines and is not regex-based. */
    required_added_substrings: string[];
    /** Every value must occur, case-sensitively and contiguously, within at least one single removed line inside a structurally valid unified-diff hunk. Matching does not span lines and is not regex-based. */
    required_removed_substrings: string[];
    require_nonempty_patch: true;
    verify_log_digests: true;
  };
  policy: {
    require_plan_outside_candidate_root: true;
    require_output_outside_candidate_root: true;
    require_verifier_distinct_from_worker: true;
  };
  extensions?: { [key: string]: IdkmeshJsonValue };
};

/** Local admission/execution-reservation/submission record bound to one exact ready input snapshot. The report is metadata; the durable claim is the admission. It is not a dispatch credential, verification, acceptance or merge authority. */
export type ExecutorAdmissionV01 = {
  kind: "idkmesh-executor-admission";
  schema_version: "0.1";
  phase: "admission" | "execution-reservation" | "submission";
  scope: ExecutorAdmissionV01_Scope;
  graph_digest: ExecutorAdmissionV01_Digest;
  observation_digest: ExecutorAdmissionV01_Digest;
  work_unit_id: string;
  binding: ExecutorAdmissionV01_Binding;
  inputs_digest: ExecutorAdmissionV01_Digest | null;
  created: boolean;
  claim: ExecutorAdmissionV01_Claim;
  authority: {
    dispatch: false;
    executes_worker: false;
    accepts_candidate: false;
    merge: false;
  };
};

export type ExecutorAdmissionV01_Binding = {
  work_unit_id: string;
  work_unit_version: number;
  work_unit_digest: ExecutorAdmissionV01_Digest;
  source_revision: ExecutorAdmissionV01_Revision;
};

/** The embedded local task claim snapshot, identical in shape to task-claim-v0.1. */
export type ExecutorAdmissionV01_Claim = {
  kind: "idkmesh-task-claim";
  schema_version: "0.1";
  task: {
    kind: "idkmesh-enterprise-resource-ref";
    schema_version: "0.1";
    tenant_id: ExecutorAdmissionV01_ScopeId;
    project_id: ExecutorAdmissionV01_ScopeId;
    resource_type: "task";
    resource_id: ExecutorAdmissionV01_ScopeId;
  };
  request_id: ExecutorAdmissionV01_Text;
  request_digest: ExecutorAdmissionV01_Digest;
  slot: number;
  epoch: number;
  owner: {
    principal_id: string;
    issuer: string;
    actor_type: "human" | "github_app" | "github_actions" | "service" | "provider" | "node";
  };
  binding: ExecutorAdmissionV01_ClaimBinding;
  state: "active" | "released" | "expired";
  created_at: ExecutorAdmissionV01_EpochSeconds;
  acknowledged_at: ExecutorAdmissionV01_EpochSeconds | null;
  ack_by: ExecutorAdmissionV01_EpochSeconds;
  lease_until: ExecutorAdmissionV01_EpochSeconds;
  progress_by: ExecutorAdmissionV01_EpochSeconds;
  hard_until: ExecutorAdmissionV01_EpochSeconds;
  occupancy: "none" | "unknown" | "running" | "terminal";
  operation_id: ExecutorAdmissionV01_Digest | null;
  execution_reference: string | null;
  submission_digest: ExecutorAdmissionV01_Digest | null;
  authority: {
    executes_worker: false;
    accepts_candidate: false;
    merge: false;
  };
};

export type ExecutorAdmissionV01_ClaimBinding = {
  work_unit_digest: ExecutorAdmissionV01_Digest;
  source_revision: string;
  inputs_digest: ExecutorAdmissionV01_Digest;
};

export type ExecutorAdmissionV01_Digest = string;

export type ExecutorAdmissionV01_EpochSeconds = number;

export type ExecutorAdmissionV01_Revision = string;

export type ExecutorAdmissionV01_Scope = {
  tenant_id: ExecutorAdmissionV01_ScopeId;
  project_id: ExecutorAdmissionV01_ScopeId;
};

export type ExecutorAdmissionV01_ScopeId = string;

export type ExecutorAdmissionV01_Text = string;

export type ExperimentManifestV01 = {
  schema_version: "0.1";
  id: string;
  title: string;
  description?: string;
  research_tracks: string[];
  hypotheses: {
    id: string;
    statement: string;
    falsification: string;
  }[];
  work_units: {
    id: string;
    path: string;
  }[];
  configurations: ({
    id: string;
    description: string;
    agent_count: number;
    topology: "single" | "independent" | "all_to_all" | "hierarchical" | "dag" | "custom";
    verification_policy: string;
    runner: {
      type: "deterministic_smoke" | "command" | "external";
      command?: string[];
      external_ref?: string;
    };
    parameters?: { [key: string]: IdkmeshJsonValue };
  })[];
  metrics: ({
    name: string;
    direction: "maximize" | "minimize" | "report_only";
    unit: string;
    description?: string;
  })[];
  repetitions: number;
  seeds: number[];
  stopping_rules: ({
    type: "max_runs" | "max_wall_seconds" | "max_compute_units" | "statistical" | "manual";
    value: IdkmeshJsonValue;
    description?: string;
  })[];
  environment: {
    python: string;
    platform: string;
    container_image?: string;
    notes?: string;
  };
  budget: {
    max_wall_seconds?: number;
    max_compute_units?: number;
    max_human_minutes?: number;
  };
  extensions?: { [key: string]: IdkmeshJsonValue };
};

/** Common envelope for reproducible IDKMesh experiment outputs. */
export type ExperimentResult = {
  schema_version: "0.1.0";
  experiment_id: string;
  hypothesis: string;
  implementation_ref: string;
  repository_commit?: string;
  created_at?: string;
  environment?: {
    python?: string;
    os?: string;
    architecture?: string;
    hardware?: string;
  };
  configuration: {
    seed: number;
    agents?: number;
    generations?: number;
    change_at?: number;
    bins?: number;
  };
  baselines?: string[];
  metrics?: string[];
  results: ({
    strategy: string;
    pre_change_best?: number;
    post_change_immediate?: number;
    post_change_mean?: number;
    final_best?: number;
    recovery_generations?: number | null;
    viable_evaluations?: number;
    archive_size?: number;
    trace?: number[];
  })[];
  limitations: string[];
  notes?: string[];
};

export type ExperimentResultV01 = {
  schema_version: "0.1";
  experiment_id: string;
  run_id: string;
  configuration_id: string;
  seed: number;
  status: "passed" | "failed" | "error" | "skipped";
  started_at: string;
  finished_at: string;
  metrics: { [key: string]: number | null };
  costs: {
    wall_seconds: number;
    compute_units: number;
    human_minutes: number;
    tokens?: number;
  };
  verification: {
    policy: string;
    passed: boolean;
    checks: {
      id: string;
      passed: boolean;
      detail?: string;
    }[];
  };
  artifacts: {
    type: string;
    locator: string;
    digest?: string;
  }[];
  provenance: {
    harness_version: string;
    manifest_digest: string;
    git_commit?: string;
    host?: string;
  };
  notes?: string;
  extensions?: { [key: string]: IdkmeshJsonValue };
};

/** Measured pairwise verifier error-dependence for the exact same verdict matrix a gate-audit-report-v0.1 was computed from (bound by provenance.input_digest_sha256), produced by `idkmesh gate-audit-dependence`. gate-audit-report-v0.1 exposes only the panel mean pairwise error correlation; this artifact exists so a future adaptive verifier-allocation revision can consume each pair's own measured phi correlation instead of reconstructing it from the mean or from provider/family identity. It is decision support only: it grants no routing, acceptance, EvaluatorPlan, or merge authority, and it never aggregates pairs into a per-verifier reputation score. */
export type GateAuditDependenceV01 = {
  schema: "gate-audit-dependence-v0.1";
  gate_id: string;
  /** Copied verbatim from the input declaration. A report can never upgrade synthetic fixture data into an observed claim. */
  evidence_class: "synthetic" | "observed";
  authority: "diagnostic_only";
  non_probe_candidate_count: number;
  /** Every verifier id from the input, sorted, independent of input list order. */
  verifier_ids: string[];
  /** One entry per unordered verifier pair, in the order itertools.combinations(sorted(verifier_ids), 2) produces. */
  pairs: ({
    verifier_a: string;
    verifier_b: string;
    /** Pearson correlation of the pair's binary error vectors over non-probe candidates, or null when unmeasurable. */
    phi_error: number | null;
    /** False when either error vector has zero variance; phi_error is then null, never 0 - unmeasurable is not the same claim as independent. */
    measurable: boolean;
    joint_error_count: number;
    a_error_count: number;
    b_error_count: number;
  })[];
  warnings: string[];
  provenance: {
    tool: "idkmesh gate-audit-dependence";
    tool_version: string;
    /** sha256 of the canonical (sort_keys, compact-separator) verdict-matrix input JSON. Identical to the matching gate-audit-report-v0.1's provenance.input_digest_sha256 for the same input, so the two artifacts can be proven to describe the same audited population. */
    input_digest_sha256: string;
  };
};

/** Diagnostic report on a verifier panel produced by `idkmesh gate-audit`: per-verifier accuracy, pairwise error correlation, measured effective independent votes, the accuracy-dependent effective-vote ceiling, and the breach rate of seeded known-bad probes. It is decision support about the review layer itself and grants no acceptance or merge authority. */
export type GateAuditReportV01 = {
  schema: "gate-audit-report-v0.1";
  gate_id: string;
  /** Copied verbatim from the input declaration. A report can never upgrade synthetic fixture data into an observed claim. */
  evidence_class: "synthetic" | "observed";
  inputs: {
    candidates: number;
    non_probe_candidates: number;
    probe_candidates: number;
    verifiers: number;
    known_good: number;
    known_bad: number;
  };
  verifiers: {
    id: string;
    accuracy: number;
    errors: number;
  }[];
  panel: {
    quorum: number;
    nominal_votes: number;
    mean_verifier_accuracy: number;
    /** Mean pairwise phi of verifier error vectors over non-probe candidates; null when no pair had measurable variance. */
    mean_pairwise_error_correlation: number | null;
    skipped_correlation_pairs: number;
    error: number;
    false_accept_rate: number | null;
    false_reject_rate: number | null;
    /** Smallest independent panel size reproducing the measured panel error at the measured mean accuracy; null when the panel does not discriminate (mean accuracy <= 0.5). */
    effective_votes: number | null;
    /** The classic N/(1+(N-1)rho) value, reported only for contrast; E015 falsified it as a sizing rule. */
    heuristic_n_eff: number | null;
    /** Largest effective size any panel at this accuracy/correlation can reach; the string 'unbounded' when measured correlation is <= 0. */
    effective_votes_ceiling: number | "unbounded" | null;
  };
  /** Seeded known-bad candidates pushed through the same panel rule; null when the input contained no probes. */
  probes: {
    total: number;
    breached: number;
    breach_rate: number;
    by_kind: { [key: string]: {
        total: number;
        breached: number;
      } };
  } | null;
  warnings: string[];
  provenance: {
    tool: "idkmesh gate-audit";
    tool_version: string;
    /** SHA-256 of the canonicalized (sorted-key, compact) input document, binding the report to the exact verdict matrix it was computed from. */
    input_digest_sha256: string;
  };
};

/** gate-audit-report-v0.1 plus an optional finite-sample bootstrap uncertainty section (issue #520). Emitted only when the caller opts into `--bootstrap`; every field present in v0.1 keeps its v0.1 meaning unchanged. It is decision support about the review layer itself and grants no acceptance or merge authority. */
export type GateAuditReportV02 = {
  schema: "gate-audit-report-v0.2";
  gate_id: string;
  /** Copied verbatim from the input declaration. A report can never upgrade synthetic fixture data into an observed claim. */
  evidence_class: "synthetic" | "observed";
  inputs: {
    candidates: number;
    non_probe_candidates: number;
    probe_candidates: number;
    verifiers: number;
    known_good: number;
    known_bad: number;
  };
  verifiers: {
    id: string;
    accuracy: number;
    errors: number;
  }[];
  panel: {
    quorum: number;
    nominal_votes: number;
    mean_verifier_accuracy: number;
    /** Mean pairwise phi of verifier error vectors over non-probe candidates; null when no pair had measurable variance. */
    mean_pairwise_error_correlation: number | null;
    skipped_correlation_pairs: number;
    error: number;
    false_accept_rate: number | null;
    false_reject_rate: number | null;
    /** Smallest independent panel size reproducing the measured panel error at the measured mean accuracy; null when the panel does not discriminate (mean accuracy <= 0.5). */
    effective_votes: number | null;
    /** The classic N/(1+(N-1)rho) value, reported only for contrast; E015 falsified it as a sizing rule. */
    heuristic_n_eff: number | null;
    /** Largest effective size any panel at this accuracy/correlation can reach; the string 'unbounded' when measured correlation is <= 0. */
    effective_votes_ceiling: number | "unbounded" | null;
  };
  /** Finite-sample bootstrap uncertainty on the panel metrics above (issue #520): a candidate-level nonparametric bootstrap that resamples whole candidate rows, preserving cross-verifier dependence within a replicate. Conditional on the candidate set being an exchangeable sample; never evidence of verifier independence. */
  uncertainty: {
    method: string;
    sampling_unit: "non_probe_candidate_row";
    confidence_level: number;
    replicates: number;
    seed: number;
    non_probe_candidates: number;
    min_candidates_for_inference: number;
    /** False when non_probe_candidates is below min_candidates_for_inference; every metric field below is then null. */
    sufficient_for_inference: boolean;
    panel_error: GateAuditReportV02_Metric_interval | null;
    mean_verifier_accuracy: GateAuditReportV02_Metric_interval | null;
    mean_pairwise_error_correlation: GateAuditReportV02_Metric_interval | null;
    effective_votes: GateAuditReportV02_Effective_votes_interval | null;
  };
  /** Seeded known-bad candidates pushed through the same panel rule; null when the input contained no probes. */
  probes: {
    total: number;
    breached: number;
    breach_rate: number;
    by_kind: { [key: string]: {
        total: number;
        breached: number;
      } };
  } | null;
  warnings: string[];
  provenance: {
    tool: "idkmesh gate-audit";
    tool_version: string;
    /** SHA-256 of the canonicalized (sorted-key, compact) input document, binding the report to the exact verdict matrix it was computed from. Invariant to the bootstrap parameters: it binds the input, not the uncertainty computed from it. */
    input_digest_sha256: string;
  };
};

export type GateAuditReportV02_Effective_votes_interval = {
  point: number | null;
  ci_low: number | null;
  ci_high: number | null;
  /** True when ci_high lands on the same table-resolution ceiling gate_audit.is_saturated defines for the point estimate: a lower bound, not a resolved interval edge. */
  ci_high_censored: boolean;
  replicates_used: number;
  replicates_undefined: number;
};

export type GateAuditReportV02_Metric_interval = {
  point: number | null;
  ci_low: number | null;
  ci_high: number | null;
  replicates_used: number;
  replicates_undefined: number;
};

/** One compact, secret-free, append-only GitHub-first ledger event. The record preserves run, WorkUnit/source, route, idempotency, attempt/provider, candidate/result/verification/human-decision references needed for restart-safe reconstruction. It grants no dispatch, verification, acceptance, integration, Git-push, or merge authority. */
export type GithubLedgerRecordV01 = {
  schema_version: "0.1";
  kind: "idkmesh-github-ledger-record";
  record_id: GithubLedgerRecordV01_Id;
  repository: string;
  project_id: GithubLedgerRecordV01_Id;
  run_id: GithubLedgerRecordV01_Id;
  ledger_sequence: number;
  previous_record_digest: null | GithubLedgerRecordV01_Digest;
  event: GithubLedgerRecordV01_Event;
  work_unit: GithubLedgerRecordV01_WorkUnit;
  routing: GithubLedgerRecordV01_Routing;
  idempotency: GithubLedgerRecordV01_Idempotency;
  attempt: null | GithubLedgerRecordV01_Attempt;
  provider: null | GithubLedgerRecordV01_Provider;
  candidate_reference: null | GithubLedgerRecordV01_EvidenceRef & {
    kind?: "candidate_reference";
  };
  result_manifest: null | GithubLedgerRecordV01_EvidenceRef & {
    kind?: "result_manifest";
  };
  verification_results: GithubLedgerRecordV01_EvidenceRef & {
    kind?: "verification_result";
  }[];
  human_decision: GithubLedgerRecordV01_HumanDecision;
  failure: null | GithubLedgerRecordV01_Failure;
  authority: GithubLedgerRecordV01_Authority;
};

export type GithubLedgerRecordV01_Attempt = {
  attempt_id: GithubLedgerRecordV01_Id;
  attempt_number: number;
  reason: "initial" | "retry" | "escalation" | "recovery";
  connector_id: GithubLedgerRecordV01_Id;
};

export type GithubLedgerRecordV01_Authority = {
  dispatch: false;
  verification: false;
  acceptance: false;
  canonical_state_write: false;
  git_push: false;
  integration: false;
  merge: false;
};

export type GithubLedgerRecordV01_Digest = string;

export type GithubLedgerRecordV01_Event = {
  event_id: GithubLedgerRecordV01_Id;
  event_type: string;
  occurred_at: GithubLedgerRecordV01_UtcTimestamp;
  state: "proposed" | "previewed" | "admission_blocked" | "admitted" | "dispatched" | "attempt_failed" | "candidate_observed" | "normalized" | "verification_requested" | "verification_error" | "evidence_ready" | "awaiting_human_decision" | "decided" | "cancelled";
  trigger: "issue" | "workflow_dispatch" | "workflow_call" | "webhook" | "schedule" | "recovery" | "provider_observation" | "system";
  actor: {
    github_actor_id: number;
    login: string;
  };
  github_delivery_id: null | string;
};

export type GithubLedgerRecordV01_EvidenceRef = {
  kind: "candidate_reference" | "result_manifest" | "verification_result" | "human_decision_record";
  digest: GithubLedgerRecordV01_Digest;
  storage_path: null | GithubLedgerRecordV01_RepoPath;
};

export type GithubLedgerRecordV01_Failure = {
  code: string;
  classification: "policy_denied" | "configuration" | "provider" | "candidate_normalization" | "verification" | "timeout" | "cancelled" | "recovery_required" | "internal";
  retryable: boolean;
};

export type GithubLedgerRecordV01_GitRevision = string;

export type GithubLedgerRecordV01_HumanDecision = {
  state: "not_recorded" | "pending" | "recorded";
  record: null | GithubLedgerRecordV01_EvidenceRef & {
    kind?: "human_decision_record";
  };
};

export type GithubLedgerRecordV01_Id = string;

export type GithubLedgerRecordV01_Idempotency = {
  dispatch_key: string;
  request_digest: GithubLedgerRecordV01_Digest;
  attempt_number: number;
};

export type GithubLedgerRecordV01_Provider = {
  driver: string;
  driver_version: string;
  submission_state: "not_submitted" | "submitted" | "ambiguous" | "definite_failure";
  external_run_id: string | null;
  external_session_id: string | null;
  external_job_id: string | null;
};

export type GithubLedgerRecordV01_RepoPath = string;

export type GithubLedgerRecordV01_Routing = {
  routing_digest: GithubLedgerRecordV01_Digest;
  policy_version: string;
  required_capability_tier: "T0" | "T1" | "T2" | "T3" | "T4";
  authority_mode: "deterministic" | "agent_candidate" | "human_gate_then_agent" | "human_required";
  risk_class: "low" | "medium" | "high" | "critical";
  eligible_connectors: ({
    connection_id: GithubLedgerRecordV01_Id;
    supported_tier: "T0" | "T1" | "T2" | "T3" | "T4";
  })[];
  ineligible_connectors: {
    connection_id: GithubLedgerRecordV01_Id;
    reasons: string[];
  }[];
  selected_connection_id: null | GithubLedgerRecordV01_Id;
  selection_reason: string[];
};

export type GithubLedgerRecordV01_UtcTimestamp = string;

export type GithubLedgerRecordV01_WorkUnit = {
  id: GithubLedgerRecordV01_Id;
  version: number;
  digest: GithubLedgerRecordV01_Digest;
  source_revision: GithubLedgerRecordV01_GitRevision;
};

/** A strict public-safe projection of digest-bound Product Spine run/evidence state for read-only GitHub publication. It contains no raw evidence, logs, prompts, provider payloads, secrets, artifact locators, worker/verifier identity, or actuation authority. */
export type GithubPublicEvidenceV01 = {
  schema_version: "0.1";
  kind: "idkmesh-github-public-evidence";
  repository: string;
  run: {
    run_id: string;
    state: "proposed" | "previewed" | "admission_blocked" | "admitted" | "dispatched" | "attempt_failed" | "candidate_observed" | "normalized" | "verification_requested" | "verification_error" | "evidence_ready" | "awaiting_human_decision" | "decided" | "cancelled";
    work_unit_id: string;
    work_unit_version: number;
    work_unit_digest: GithubPublicEvidenceV01_Digest;
    source_revision: string;
    evidence_report_digest: GithubPublicEvidenceV01_Digest | null;
    human_decision_record_digest: GithubPublicEvidenceV01_Digest | null;
  };
  attempts: GithubPublicEvidenceV01_Attempt[];
  evidence_summary: null | GithubPublicEvidenceV01_EvidenceSummary;
  human_decision_status: "not_recorded" | "pending" | "recorded";
  authority: {
    dispatch: false;
    verification: false;
    human_decision: false;
    canonical_state_write: false;
    git_push: false;
    integration: false;
    merge: false;
  };
  privacy: {
    data_classification: "public";
    projection_only: true;
    raw_evidence_included: false;
    raw_logs_included: false;
    raw_prompts_included: false;
    provider_payloads_included: false;
    secret_material_included: false;
    artifact_locator_included: false;
    worker_or_verifier_identity_included: false;
  };
};

export type GithubPublicEvidenceV01_Attempt = {
  attempt_id: string;
  order: number;
  connector_id: string;
  state: "created" | "dispatched" | "worker_error" | "candidate_observed" | "normalization_error" | "normalized" | "verification_requested" | "verification_error" | "verified" | "cancelled";
  candidate_reference_digest: GithubPublicEvidenceV01_Digest | null;
  candidate: GithubPublicEvidenceV01_Candidate;
  result_manifest_digest: GithubPublicEvidenceV01_Digest | null;
  verification_semantic_digest: GithubPublicEvidenceV01_Digest | null;
  evidence_state: null | "supported" | "rejected" | "inconclusive" | "worker_error" | "result_manifest_error" | "verification_error";
  verifier_recommendation: null | "accept_candidate" | "reject_candidate" | "escalate" | "insufficient_evidence";
};

export type GithubPublicEvidenceV01_Candidate = null | {
  type: "github_pull_request";
  repository: string;
  number: number;
  head_sha: string;
  url: string;
} | {
  type: "artifact_bundle";
  digest: GithubPublicEvidenceV01_Digest;
};

export type GithubPublicEvidenceV01_Digest = string;

export type GithubPublicEvidenceV01_EvidenceSummary = {
  attempt_count: number;
  supported: number;
  rejected: number;
  inconclusive: number;
  control_errors: number;
  verification_disagreement: boolean;
  control_failure_present: boolean;
};

/** Normalized untrusted planning hints collected from a GitHub WorkUnit request. This object is not a WorkUnit, routing decision, authorization decision, dispatch instruction, verification result, or integration decision. */
export type GithubWorkunitIntakeV01 = {
  schema_version: "0.1";
  kind: "idkmesh-github-workunit-intake";
  objective: string;
  task_class: "coding" | "testing" | "review" | "benchmarking" | "documentation" | "research" | "integration" | "governance" | "other";
  expected_outputs: string[];
  /** Untrusted requested write scope. Later trusted policy may narrow or reject it; this field cannot broaden canonical WorkUnit permissions. */
  requested_allowed_paths: string[];
  /** Untrusted requested exclusions. Later trusted policy may add stricter forbidden paths. */
  requested_forbidden_paths: string[];
  dependencies: ({
    reference: string;
    relation: "requires" | "blocked_by" | "informs";
  })[];
  /** Requested acceptance checks. They are planning content, not executable command authority. */
  acceptance_checks: string[];
  /** Requester hint only. Trusted policy/risk analysis may raise risk and may never be weakened by this value. */
  risk_hint: "low" | "medium" | "high" | "critical" | "unspecified";
  /** Requester preference only. 'allowed' never grants external-processing authority. */
  external_processing_hint: "forbidden" | "allowed" | "unspecified";
  /** Requester hint only. Trusted classification may raise sensitivity and may never be downgraded by this value. */
  data_sensitivity_hint: "public" | "internal" | "confidential" | "restricted" | "unspecified";
  /** Requester hint only. It cannot waive a review or human-decision requirement imposed by policy. */
  human_review_hint: "required" | "preferred" | "unspecified";
  /** Advisory connector identifier only. It cannot select a connector, resolve a secret, or authorize dispatch. */
  preferred_connector_hint: string | null;
  authority_ceiling: {
    policy_authority: false;
    secret_authority: false;
    command_authority: false;
    network_authority: false;
    filesystem_authority: false;
    connector_selection_authority: false;
    dispatch_authority: false;
    verification_authority: false;
    integration_authority: false;
  };
};

/** A graph for uncertain goals, competing hypotheses, work, evidence, risks, decisions, and provenance. */
export type GoalGraph = {
  schema_version: "0.1.0";
  graph_id: string;
  title?: string;
  description?: string;
  created_at?: string;
  updated_at?: string;
  nodes: GoalGraph_Node[];
  edges: GoalGraph_Edge[];
  metadata?: { [key: string]: IdkmeshJsonValue };
};

export type GoalGraph_Edge = {
  id: string;
  source: string;
  target: string;
  type: "depends_on" | "supports" | "contradicts" | "implements" | "verifies" | "derived_from" | "supersedes" | "blocks" | "produced_by" | "tests" | "measures" | "mitigates" | "challenges" | "motivates" | "decomposes_into" | "related_to" | "other";
  weight?: number | null;
  confidence?: number | null;
  created_by?: string;
  created_at?: string;
  evidence_refs?: string[];
  attributes?: { [key: string]: IdkmeshJsonValue };
};

export type GoalGraph_Node = {
  id: string;
  type: "goal" | "question" | "assumption" | "hypothesis" | "requirement" | "constraint" | "proposal" | "work_unit" | "artifact" | "test" | "evidence" | "decision" | "risk" | "failure" | "metric" | "participant" | "agent" | "compute_node" | "other";
  title: string;
  description?: string;
  status: "proposed" | "active" | "supported" | "contested" | "blocked" | "verified" | "rejected" | "superseded" | "resolved" | "archived";
  confidence?: number | null;
  priority?: number | null;
  novelty?: number | null;
  information_value?: number | null;
  risk_level?: "low" | "medium" | "high" | "critical" | null;
  created_by?: string;
  created_at?: string;
  updated_at?: string;
  tags?: string[];
  refs?: {
    kind?: string;
    uri?: string;
    sha256?: string;
  }[];
  attributes?: { [key: string]: IdkmeshJsonValue };
};

/** A recorded, accountable human integration decision against one immutable Run Evidence Report. It captures who decided, what was decided, when, and why, bound to the report by content digest so a swapped or corrupted report is detectable. It is a record of a decision that was made, not an executor of that decision: it carries no canonical-state-write, git-push, or merge authority of its own. */
export type HumanDecisionRecordV01 = {
  schema_version: "0.1";
  kind: "idkmesh-human-decision-record";
  decision_id: string;
  evidence_report: {
    kind: "idkmesh-run-evidence-report";
    schema_version: "0.1";
    run_id: string;
    /** canonical_digest() of the exact evidence-report document this decision was made against. A decision record whose digest no longer matches the referenced report's current content is stale/tampered evidence, not a valid decision. */
    digest: HumanDecisionRecordV01_Digest;
  };
  /** The attempt_id (from the referenced evidence report's attempts[]) this decision applies to, or null when the decision concerns the run as a whole rather than one attempt. */
  selected_attempt_id: string | null;
  /** The human's own explicit choice. This is deliberately a distinct vocabulary from the machine-suggested decision_support.recommendation values (accept_candidate/reject_candidate/escalate/insufficient_evidence) carried by the evidence report: recording a decision here is never satisfied by echoing that recommendation. */
  decision: "accept" | "reject" | "escalate";
  rationale: string;
  decider: {
    id: string;
    type: "human" | "governance_body";
    display_name?: string;
  };
  decided_at: string;
  authority: {
    canonical_state_write: false;
    git_push: false;
    merge: false;
  };
};

export type HumanDecisionRecordV01_Digest = string;

/** Optional protocol-neutral identity evidence for a worker/result. Identity evidence is provenance only and does not grant authorization, verification, or integration authority. */
export type IdentityBindingV01 = {
  schema_version: "0.1";
  protocol: string;
  subject: string;
  verified: boolean;
  evidence_digest?: string;
  evidence_locator?: string;
  verification_method?: string;
};

/** Initial machine-readable schema for IDKMesh typed temporal task/evidence/provenance graphs. */
export type Idkgraph = {
  graph_id: string;
  version: string;
  generated_at?: string;
  nodes: Idkgraph_Node[];
  hyperedges: Idkgraph_Hyperedge[];
  events?: Idkgraph_Event[];
};

export type Idkgraph_Event = {
  id: string;
  type: "NodeCreated" | "NodeUpdated" | "EdgeAdded" | "EdgeRemoved" | "ClaimUpdated" | "EvidenceAttached" | "TaskSplit" | "TaskMerged" | "DocumentMoved" | "DecisionSuperseded" | "VerificationPassed" | "VerificationFailed" | "PolicyChanged";
  timestamp: string;
  affected_ids: string[];
  actor_id?: string;
  attributes?: { [key: string]: IdkmeshJsonValue };
};

export type Idkgraph_Hyperedge = {
  id: string;
  relation: Idkgraph_RelationType;
  sources: string[];
  targets: string[];
  confidence?: number;
  attributes?: { [key: string]: IdkmeshJsonValue };
  provenance?: Idkgraph_Provenance;
};

export type Idkgraph_Node = {
  id: string;
  type: Idkgraph_NodeType;
  title: string;
  state?: string;
  confidence?: number;
  risk?: "low" | "medium" | "high" | "critical";
  tags?: string[];
  attributes?: { [key: string]: IdkmeshJsonValue };
  provenance?: Idkgraph_Provenance;
};

export type Idkgraph_NodeType = "goal" | "question" | "hypothesis" | "constraint" | "work_unit" | "artifact" | "evidence" | "decision" | "metric" | "contributor" | "agent" | "compute_resource" | "document" | "concept" | "policy" | "experiment";

export type Idkgraph_Provenance = {
  actor_id?: string;
  activity_id?: string;
  source?: string;
  commit?: string;
  created_at?: string;
  model?: string;
  tool?: string;
};

export type Idkgraph_RelationType = "decomposes_into" | "depends_on" | "requires" | "produces" | "blocks" | "supports" | "contradicts" | "verifies" | "invalidates" | "derived_from" | "supersedes" | "implements" | "documents" | "defines" | "mentions" | "duplicates" | "assigned_to" | "reviewed_by" | "generated_by" | "uses_compute" | "measured_by" | "governed_by" | "bridges";

/** The standard error envelope every IDKMesh JSON API returns, per docs/specifications/API_CONVENTIONS_V0_1.md section 5. `code` is the compatibility-sensitive machine identifier; `message` is explanatory only and is never a parsing contract. A provider/worker domain failure is not automatically mapped to this shape as an HTTP 5xx -- that mapping is owned by the endpoint's own domain specification. */
export type IdkmeshApiErrorV01 = {
  /** The URL compatibility version this response was served under, e.g. "v1". Independent of schema_version -- see section 1. */
  api_version: string;
  schema_version: "0.1";
  kind: "idkmesh-api-error";
  ok: false;
  error: {
    /** Stable machine-readable error code. This is the compatibility contract; message text may change freely. */
    code: string;
    /** Human-readable explanation. Never parsed by a compliant client. */
    message: string;
    /** Whether an identical retry of the same request could plausibly succeed without caller changes. */
    retryable: boolean;
    /** Bounded structured recovery information. Must never contain secrets, tokens, prompts, or private raw payloads (section 18). */
    details?: { [key: string]: IdkmeshJsonValue };
  };
};

/** Privacy-safe, process-lifetime aggregate HTTP service telemetry. The contract deliberately has no request path, query, request-id, identity, authentication, prompt, evidence, run, WorkUnit, or arbitrary-label fields. */
export type IdkmeshApiOperationalMetricsV01 = {
  schema_version: "0.1";
  kind: "idkmesh-api-operational-metrics";
  service: string;
  service_version: string;
  scope: "process_lifetime";
  requests: {
    total: number;
    client_errors_total: number;
    server_errors_total: number;
    by_status_class: {
      "1xx": number;
      "2xx": number;
      "3xx": number;
      "4xx": number;
      "5xx": number;
    };
  };
  latency_ms: {
    count: number;
    sum: number;
    max: number;
    buckets: {
      le_ms: number;
      count: number;
    }[];
  };
  concurrency: {
    in_flight_requests: number;
    max_concurrent_requests: number;
    event_stream_clients: number;
    max_event_stream_clients: number;
  };
  admission: {
    overload_rejections_total: number;
    draining_rejections_total: number;
    rate_limit_rejections_total: 0;
    rate_limit_status: "not_implemented";
  };
  operations: {
    run_evidence_inspections_total: number;
    human_decision_ingestions_total: 0;
    human_decision_ingestion_status: "not_implemented";
  };
  dependencies: {
    product_spine_store: {
      state: "not_configured" | "configured_unprobed";
      required_for_core_readiness: false;
    };
  };
  telemetry: {
    trace_context: "w3c-traceparent-v00-pass-through";
    path_labels: false;
    query_labels: false;
    request_id_labels: false;
    authentication_labels: false;
    payload_labels: false;
  };
  authority: {
    canonical_state_write: false;
    git_push: false;
    merge: false;
  };
};

/** Machine-readable operational SLO and saturation-alert targets for the local single-token API profile (issue #744). These are targets, not measured results. The id sets are closed: each id is bound to one indicator computed by idkmesh/api_slo.py, and the contract carries no labels, endpoints, credentials, or authority. */
export type IdkmeshApiSloContractV01 = {
  schema_version: "0.1";
  kind: "idkmesh-api-slo-contract";
  profile: "local_single_token";
  claim: "operational_target_not_measured_result";
  window_seconds: number;
  objectives: [{
    id: "server_error_fraction";
    comparison: "less_than";
    threshold: number;
  }, {
    id: "latency_within_1000ms_fraction";
    comparison: "at_least";
    threshold: number;
    latency_bound_ms: 1000;
  }, {
    id: "overload_rejections";
    comparison: "at_most";
    threshold: number;
    alert_after_consecutive_intervals: number;
  }];
  saturation_alerts: [{
    id: "api_concurrency_hot";
    comparison: "at_least";
    threshold: number;
    for_seconds: number;
  }, {
    id: "sse_saturation";
    comparison: "at_least";
    threshold: number;
    for_seconds: number;
  }];
  authority: {
    canonical_state_write: false;
    git_push: false;
    merge: false;
    pages_deploy: false;
  };
};

/** Public-safe read projection of one persisted connector-control record. It reports only secret-reference presence, never a secret reference or value, settings, provider payload, dispatch authority, verification authority, acceptance authority, Git push authority, or merge authority. */
export type IdkmeshConnectionResourceV01 = {
  id: string;
  kind: string;
  driver: string;
  enabled: boolean;
  auth_ref_configured: boolean;
  capability_tiers: string[];
  task_classes: string[];
  tools: string[];
  candidate_types: string[];
  max_risk: string;
  external_processing: boolean;
  project_spend_usd_max: number;
  max_concurrency: number;
};

/** The success envelope returned by `GET /api/v1/connections/{connection_id}`, wrapping the public-safe connection resource. Reading a connection performs no probe, secret resolution, dispatch, or provider call, and grants no execution authority. */
export type IdkmeshControlTowerConnectionResponseV01 = {
  api_version: "v1";
  schema_version: "0.1";
  kind: "idkmesh-control-tower-connection-response";
  ok: true;
  connection: IdkmeshConnectionResourceV01;
};

/** The success envelope returned by `GET /api/v1/connector-drivers`: the static, secret-free driver descriptors (kind, driver id, version) of the registry the server can construct. `registry` names that registry and `live_adapters` is always false: today only the offline fake-driver registry exists, so the entries are not evidence that any live provider adapter is installed. Reading the listing performs no probe, secret resolution, dispatch, or provider call, and grants no execution authority. */
export type IdkmeshControlTowerConnectorDriversResponseV01 = {
  api_version: "v1";
  schema_version: "0.1";
  kind: "idkmesh-control-tower-connector-drivers-response";
  ok: true;
  registry: "offline-fake";
  live_adapters: false;
  drivers: ({
    kind: "agent" | "execution" | "model" | "scm";
    driver: string;
    version: string;
  })[];
};

/** The success envelope returned by `POST /api/v1/run-evidence/inspect` (docs/specifications/CONTROL_TOWER_LOCAL_API_V0_1.md), wrapping one deterministic, digest-bound `idkmesh-control-tower-snapshot`. The wrapper itself carries no authority; `snapshot_digest` is the canonical digest of `snapshot`, so a caller can detect a swapped or corrupted snapshot without re-deriving it. The full snapshot shape is its own frozen contract -- schemas/control-tower-snapshot-v0.1.schema.json -- and is intentionally not duplicated here; this schema only constrains the wrapper and the snapshot's own identity fields. */
export type IdkmeshControlTowerInspectionResponseV01 = {
  api_version: "v1";
  schema_version: "0.1";
  kind: "idkmesh-control-tower-inspection-response";
  ok: true;
  /** canonical_digest() of the sibling snapshot field. */
  snapshot_digest: string;
  snapshot: {
    kind: "idkmesh-control-tower-snapshot";
    schema_version: "0.1";
  };
};

/** The success envelope returned by `GET /api/v1/projects/{project_id}`, wrapping the derived project summary (ADR-0021). A 404 means no stored run names the project; it does not assert the project does not exist elsewhere. */
export type IdkmeshControlTowerProjectResponseV01 = {
  api_version: "v1";
  schema_version: "0.1";
  kind: "idkmesh-control-tower-project-response";
  ok: true;
  project: IdkmeshProjectResourceV01;
};

/** The success envelope returned by `GET /api/v1/runs/{run_id}/attempts`, wrapping the same idkmesh/product_spine.py:AttemptProjection.to_dict() shape already embedded in the full run document. `attempts` is a reserved trailing path segment (ADR-0019): a run_id ending in "/attempts" cannot be read through the plain single-run GET, only through this endpoint. */
export type IdkmeshControlTowerRunAttemptsResponseV01 = {
  api_version: "v1";
  schema_version: "0.1";
  kind: "idkmesh-control-tower-run-attempts-response";
  ok: true;
  run_id: string;
  attempts: ({
    attempt_id: string;
    order: number;
    connector_id: string;
    state: "created" | "dispatched" | "worker_error" | "candidate_observed" | "normalization_error" | "normalized" | "verification_requested" | "verification_error" | "verified" | "cancelled";
    provider_reference: string | null;
    candidate_reference_digest: IdkmeshControlTowerRunAttemptsResponseV01_Digest | null;
    result_manifest_digest: IdkmeshControlTowerRunAttemptsResponseV01_Digest | null;
    verification_semantic_digest: IdkmeshControlTowerRunAttemptsResponseV01_Digest | null;
    error_code: string | null;
  })[];
};

export type IdkmeshControlTowerRunAttemptsResponseV01_Digest = string;

/** The success envelope returned by `GET /api/v1/runs/{run_id}/evidence` (ADR-0024). `evidence_report` is the Run Evidence Report retained in the run row, returned as retained after its canonical digest was verified against `evidence_report_digest`; a mismatch is refused with 500 evidence_integrity_error and never served. `evidence` is a reserved trailing path segment (ADR-0019). */
export type IdkmeshControlTowerRunEvidenceResponseV01 = {
  api_version: "v1";
  schema_version: "0.1";
  kind: "idkmesh-control-tower-run-evidence-response";
  ok: true;
  run_id: string;
  evidence_report_digest: string;
  evidence_report: RunEvidenceReportV01;
};

/** The success envelope returned by `GET /api/v1/runs/{run_id}`, wrapping the same idkmesh/product_spine_run_store.py:PersistedProductSpineRun.to_dict() shape the CLI's `idkmesh run status --json` already prints -- the HTTP read surface reuses the CLI's application service rather than defining a second one (docs/architecture/API_CONTROL_PLANE_ARCHITECTURE.md). `created` and `replayed` are always false for a read: they describe the outcome of a create call, carried over from the shared projection type rather than given a second one. */
export type IdkmeshControlTowerRunResponseV01 = {
  api_version: "v1";
  schema_version: "0.1";
  kind: "idkmesh-control-tower-run-response";
  ok: true;
  run: {
    kind: "idkmesh-product-spine-run";
    schema_version: "0.1";
  };
  idempotency_key: string;
  create_request_digest: string;
  created: false;
  replayed: false;
  provider_execution_terminated: false;
  candidate_accepted: false;
  merge_authority: false;
};

/** The authenticated discovery/status document returned by `GET /api/v1/status` (docs/specifications/CONTROL_TOWER_LOCAL_API_V0_1.md). It publishes accepted media types, source/output schema URLs, explicitly enabled read capabilities, explicitly disabled actuation capabilities, and the endpoint list -- it performs no action of its own. */
export type IdkmeshControlTowerStatusV01 = {
  api_version: "v1";
  schema_version: "0.1";
  kind: "idkmesh-control-tower-status";
  ok: true;
  service: string;
  mode: string;
  media_types: string[];
  source_contracts: string[];
  schemas: { [key: string]: string };
  /** The five actuation capabilities are pinned false: this API grants no write, execution, or merge authority regardless of future read-side additions. */
  capabilities: {
    run_evidence_inspection: boolean;
    semantic_timeline: boolean;
    provenance_chain: boolean;
    human_decision_recording: false;
    worker_execution: false;
    canonical_state_write: false;
    git_push: false;
    merge: false;
    automatic_candidate_selection: false;
  };
  operations: {
    request_id_header: "X-Request-ID";
    traceparent_header?: "traceparent";
    metrics_include_payload_labels?: false;
    liveness: string;
    readiness: string;
    access_log_env: string;
    access_logs_include_bodies: false;
    access_logs_include_authentication: false;
    /** The service limits actually in force (ADR-0022). Optional so a bare status document stays valid; the Control Tower server always includes it. `per_client_rate_limit` is `not_implemented`: 429 is reserved until a per-client identity exists. */
    limits?: {
      request_timeout_seconds: number;
      max_concurrent_requests: number;
      retry_after_seconds: number;
      drain_timeout_seconds: number;
      max_request_line_bytes: number;
      max_header_line_bytes: number;
      max_header_count: number;
      max_request_body_bytes: number;
      overload_status: 503;
      connection_policy: "close_after_response";
      per_client_rate_limit: "not_implemented";
      max_sse_clients?: number;
      sse_heartbeat_seconds?: number;
      sse_max_stream_seconds?: number;
    };
  };
  endpoints: { [key: string]: string };
};

/** The success envelope returned by `GET /api/v1/work-units/{work_unit_id}`, wrapping the derived WorkUnit resource (ADR-0021). A 404 means no stored run references the id; it does not assert the WorkUnit does not exist elsewhere. */
export type IdkmeshControlTowerWorkUnitResponseV01 = {
  api_version: "v1";
  schema_version: "0.1";
  kind: "idkmesh-control-tower-work-unit-response";
  ok: true;
  work_unit: IdkmeshWorkUnitResourceV01;
};

/** One durable event of the canonical append-only stream (ADR-0023): an item of `GET /api/v1/events`, the `data:` payload of `GET /api/v1/events/stream`, and an item of `idkmesh events list`. `sequence` is the stream's monotonic position (resume with `Last-Event-ID: <sequence>`); `event_id` is unique within the stream so clients can dedupe at-least-once delivery. `occurred_at` is supplied by the producer of the state change, never read from a clock by the store. `authority_class` keeps recommendations and decisions distinguishable: v0.1 emits only `local_control`; the other classes are reserved. `payload_digest` is the sha256 of the canonical JSON of `payload`. Coverage in v0.1 is Product Spine run create and cancel only. */
export type IdkmeshEventV01 = {
  schema_version: "0.1";
  kind: "idkmesh-event";
  event_id: string;
  sequence: number;
  occurred_at: string;
  event_type: "run.created" | "run.cancelled";
  principal: {
    type: string;
    id: string;
  };
  authority_class: "local_control" | "worker_observation" | "verifier_recommendation" | "human_decision";
  project_id: string;
  work_unit_id: string;
  run_id: string;
  attempt_id: string | null;
  source_revision: string | null;
  evidence_reference: {
    kind: string;
    digest: IdkmeshEventV01_Digest;
  } | null;
  payload: { [key: string]: IdkmeshJsonValue };
  payload_digest: IdkmeshEventV01_Digest;
};

export type IdkmeshEventV01_Digest = string;

/** Transport request body for recording an immutable Human Decision Record. The caller supplies only the explicit decision, rationale, selected attempt and exact evidence-report binding. Authenticated principal identity, decision_id, decided_at and authority are trusted server/domain outputs and cannot be supplied by this request. Idempotency-Key is an HTTP header governed by API_CONVENTIONS_V0_1 section 12, not a body field. This contract does not itself execute integration, Git push or merge. */
export type IdkmeshHumanDecisionRequestV01 = {
  schema_version: "0.1";
  kind: "idkmesh-human-decision-request";
  evidence_report: {
    kind: "idkmesh-run-evidence-report";
    schema_version: "0.1";
    run_id: string;
    /** canonical_digest() of the exact evidence-report document this decision was made against. A decision record whose digest no longer matches the referenced report's current content is stale/tampered evidence, not a valid decision. */
    digest: HumanDecisionRecordV01_Digest;
  };
  selected_attempt_id: (string | null);
  decision: ("accept" | "reject" | "escalate");
  rationale: string;
};

/** Successful transport response for immutable human-decision recording. Fresh creation and exact idempotent replay return the same decision record and canonical digest. The nested Human Decision Record carries no canonical-state-write, Git-push or merge authority; recording a decision remains separate from integration execution. */
export type IdkmeshHumanDecisionResponseV01 = {
  api_version: "v1";
  schema_version: "0.1";
  kind: "idkmesh-human-decision-response";
  ok: true;
  decision_record: HumanDecisionRecordV01;
  decision_record_digest: HumanDecisionRecordV01_Digest;
};

/** Request-identity reservation and conflict metadata for externally retried mutations (docs/specifications/API_CONVENTIONS_V0_1.md section 12, ADR-0018). The admission form is retained before any external side effect: the same idempotency key with the same canonical request digest replays the original logical result, and the same key with a different digest produces the conflict form (the 409 error code contract is idkmesh-api-error-v0.1 `code: idempotency_conflict`). idempotency_key, request_id and run_id are identity metadata only: they deduplicate operations and must not create fresh work slots, task ownership or execution authority. The record grants no dispatch, worker execution, candidate acceptance or merge authority, and it is not verification evidence. */
export type IdkmeshIdempotencyV01 = IdkmeshIdempotencyV01_Admission | IdkmeshIdempotencyV01_Conflict;

/** One idempotency key reserved against one canonical request digest before side effects. created and replayed are exact complements: a fresh reservation reports created=true/replayed=false, an exact replay reports created=false/replayed=true and never renews or re-executes. */
export type IdkmeshIdempotencyV01_Admission = {
  schema_version: "0.1";
  kind: "idkmesh-idempotency-admission";
  idempotency_key: IdkmeshIdempotencyV01_Text;
  request_id: IdkmeshIdempotencyV01_Text | null;
  request_digest: IdkmeshIdempotencyV01_Digest;
  run_id: IdkmeshIdempotencyV01_Text;
  state?: IdkmeshIdempotencyV01_Text;
  created: boolean;
  replayed: boolean;
  authority: IdkmeshIdempotencyV01_Authority;
};

export type IdkmeshIdempotencyV01_Authority = {
  dispatch: false;
  executes_worker: false;
  accepts_candidate: false;
  merge: false;
};

/** Same idempotency key presented with a different canonical request digest. Fail closed with the standard error envelope code `idempotency_conflict`; the retained digest is immutable and a deliberate new request needs a new key. */
export type IdkmeshIdempotencyV01_Conflict = {
  schema_version: "0.1";
  kind: "idkmesh-idempotency-conflict";
  idempotency_key: IdkmeshIdempotencyV01_Text;
  retained_request_digest: IdkmeshIdempotencyV01_Digest;
  presented_request_digest: IdkmeshIdempotencyV01_Digest;
  code: "idempotency_conflict";
  message: IdkmeshIdempotencyV01_Text;
  authority: IdkmeshIdempotencyV01_Authority;
};

export type IdkmeshIdempotencyV01_Digest = string;

export type IdkmeshIdempotencyV01_Text = string;

/** The standard paginated list response shape for IDKMesh JSON list endpoints, per docs/specifications/API_CONVENTIONS_V0_1.md section 10. Uses an opaque cursor rather than offset pagination so mutable event/run streams stay safe to page through. This envelope carries no dispatch, verification, acceptance, or merge authority -- it is a read projection only. */
export type IdkmeshListV01 = {
  kind: "idkmesh-list";
  schema_version: "0.1";
  /** The page of resources. Each item's own shape is owned by the domain schema for that resource type, not by this envelope. */
  items: IdkmeshJsonValue[];
  page: {
    /** Opaque continuation token for the next page, or null when this is the last page. Never constructed by a client; never an offset. */
    next_cursor: string | null;
    /** The bounded page size actually applied to this response. */
    limit: number;
  };
};

/** An immutable read projection over one Product Spine lifecycle (idkmesh/product_spine.py:ProductSpineRun), as returned by `idkmesh run status`/`run create`/`run cancel` and by `GET /api/v1/runs/{run_id}`. It records bounded lifecycle state and per-attempt digests; it carries no canonical-state-write, git-push, or merge authority of its own -- see the fixed `authority` block. */
export type IdkmeshProductSpineRunV01 = {
  schema_version: "0.1";
  kind: "idkmesh-product-spine-run";
  run_id: string;
  request_digest: IdkmeshProductSpineRunV01_Digest;
  project_id: string;
  work_unit: {
    id: string;
    version: number;
    digest: IdkmeshProductSpineRunV01_Digest;
    source_revision: string;
  };
  routing: {
    policy_version: string;
    authority_mode: "deterministic" | "agent_candidate" | "human_gate_then_agent" | "human_required";
    admitted_connectors: string[];
  };
  state: "proposed" | "previewed" | "admission_blocked" | "admitted" | "dispatched" | "attempt_failed" | "candidate_observed" | "normalized" | "verification_requested" | "verification_error" | "evidence_ready" | "awaiting_human_decision" | "decided" | "cancelled";
  attempts: ({
    attempt_id: string;
    order: number;
    connector_id: string;
    state: "created" | "dispatched" | "worker_error" | "candidate_observed" | "normalization_error" | "normalized" | "verification_requested" | "verification_error" | "verified" | "cancelled";
    provider_reference: string | null;
    candidate_reference_digest: IdkmeshProductSpineRunV01_Digest | null;
    result_manifest_digest: IdkmeshProductSpineRunV01_Digest | null;
    verification_semantic_digest: IdkmeshProductSpineRunV01_Digest | null;
    error_code: string | null;
  })[];
  evidence_report_digest: IdkmeshProductSpineRunV01_Digest | null;
  human_decision_record_digest: IdkmeshProductSpineRunV01_Digest | null;
  authority: {
    canonical_state_write: false;
    git_push: false;
    merge: false;
  };
};

export type IdkmeshProductSpineRunV01_Digest = string;

/** The `project` member of `GET /api/v1/projects/{project_id}`. A summary derived on demand from stored Product Spine runs (ADR-0021): no project record exists, so this is counts only. `runs_by_state` always carries every canonical run state (zero-filled) so the shape is identical for every project. It carries no health, status or score rollup and selects nothing. `work_unit_count` is the number of distinct WorkUnit ids referenced by this project's runs; list them with `GET /api/v1/work-units?project_id=`. */
export type IdkmeshProjectResourceV01 = {
  project_id: string;
  /** Sum of runs_by_state. */
  run_count: number;
  runs_by_state: {
    proposed: number;
    previewed: number;
    admission_blocked: number;
    admitted: number;
    dispatched: number;
    attempt_failed: number;
    candidate_observed: number;
    normalized: number;
    verification_requested: number;
    verification_error: number;
    evidence_ready: number;
    awaiting_human_decision: number;
    decided: number;
    cancelled: number;
  };
  work_unit_count: number;
};

/** The minimal `GET /readyz` readiness document built by `idkmesh/service_runtime.py:readiness_document()` and shared by every IDKMesh HTTP service (currently the Control Tower Local API). It carries no project/evidence state and no secrets -- readiness answers only whether the process is ready for its declared profile (docs/specifications/API_CONVENTIONS_V0_1.md section 16). */
export type IdkmeshReadinessV01 = {
  status: "ready";
  service: string;
  service_version: string;
  mode: string;
  /** Present only when the caller's service has a versioned HTTP API; omitted otherwise. */
  api_version?: string;
};

/** One item of `GET /api/v1/work-units` and the `work_unit` member of `GET /api/v1/work-units/{work_unit_id}`. A read model derived on demand from the WorkUnit references stored in Product Spine runs (ADR-0021): no WorkUnit body is stored or returned, `digest` is the binding for the body, and no revision is selected as latest. `revisions` is ordered ascending by (version, digest, source_revision). Under a `project_id` filter, run counts include only that project's runs. */
export type IdkmeshWorkUnitResourceV01 = {
  id: string;
  /** Sum of the revisions' run_count. */
  run_count: number;
  revisions: {
    version: number;
    digest: IdkmeshWorkUnitResourceV01_Digest;
    source_revision: string;
    run_count: number;
  }[];
};

export type IdkmeshWorkUnitResourceV01_Digest = string;

/** Preregistered design/holdout benchmark configuration for issue #693. Selection rules are fixed by implementation version; holdout rows are evaluation-only. */
export type MarginalEvidenceBenchmarkConfigV01 = {
  schema: "marginal-evidence-benchmark-config-v0.1";
  benchmark_id: string;
  design_matrix: string;
  holdout_matrix: string;
  current_verifier_ids: string[];
  candidate_verifier_ids: string[];
  verifier_families: { [key: string]: string };
  random_seed: number;
  bootstrap: {
    replicates: number;
    seed: number;
    confidence_level: number;
  };
};

/** Diagnostic held-out comparison of a preregistered marginal-evidence selector and four simple baselines. The report grants no routing, verification, acceptance, EvaluatorPlan, or merge authority. */
export type MarginalEvidenceBenchmarkReportV01 = {
  schema: "marginal-evidence-benchmark-report-v0.1";
  benchmark_id: string;
  gate_id: string;
  evidence_class: "synthetic" | "observed";
  authority: "diagnostic_only";
  analysis: {
    current_verifier_ids: MarginalEvidenceBenchmarkReportV01_Id_array;
    candidate_verifier_ids: MarginalEvidenceBenchmarkReportV01_Id_array;
    verifier_families: { [key: string]: string };
    random_seed: number;
    bootstrap: MarginalEvidenceBenchmarkReportV01_Bootstrap_config;
    selection_rule_version: "marginal-selection-interval-dominance-v0.1";
  };
  splits: {
    design: MarginalEvidenceBenchmarkReportV01_Split;
    holdout: MarginalEvidenceBenchmarkReportV01_Split;
  };
  selection_plan: {
    rule_version: "marginal-selection-interval-dominance-v0.1";
    source: "design_only";
    current_verifier_ids: MarginalEvidenceBenchmarkReportV01_Id_array;
    candidate_verifier_ids: MarginalEvidenceBenchmarkReportV01_Id_array;
    selectors: [MarginalEvidenceBenchmarkReportV01_Selector & {
      strategy: "marginal_effective_votes";
    }, MarginalEvidenceBenchmarkReportV01_Selector & {
      strategy: "random_eligible";
    }, MarginalEvidenceBenchmarkReportV01_Selector & {
      strategy: "highest_standalone_accuracy";
    }, MarginalEvidenceBenchmarkReportV01_Selector & {
      strategy: "different_family_first";
    }, MarginalEvidenceBenchmarkReportV01_Selector & {
      strategy: "minimum_mean_pairwise_error_correlation";
    }];
    digest_sha256: MarginalEvidenceBenchmarkReportV01_Sha256;
    design_input_digest_sha256: MarginalEvidenceBenchmarkReportV01_Sha256;
  };
  holdout_results: [MarginalEvidenceBenchmarkReportV01_Holdout_result & {
    strategy: "marginal_effective_votes";
  }, MarginalEvidenceBenchmarkReportV01_Holdout_result & {
    strategy: "random_eligible";
  }, MarginalEvidenceBenchmarkReportV01_Holdout_result & {
    strategy: "highest_standalone_accuracy";
  }, MarginalEvidenceBenchmarkReportV01_Holdout_result & {
    strategy: "different_family_first";
  }, MarginalEvidenceBenchmarkReportV01_Holdout_result & {
    strategy: "minimum_mean_pairwise_error_correlation";
  }];
  warnings: string[];
  provenance: {
    tool: "idkmesh marginal-evidence-benchmark";
    tool_version: string;
    config_digest_sha256: MarginalEvidenceBenchmarkReportV01_Sha256;
    selection_plan_digest_sha256: MarginalEvidenceBenchmarkReportV01_Sha256;
  };
};

export type MarginalEvidenceBenchmarkReportV01_Bootstrap_config = {
  replicates: number;
  seed: number;
  confidence_level: number;
};

export type MarginalEvidenceBenchmarkReportV01_Holdout_result = {
  strategy: MarginalEvidenceBenchmarkReportV01_Strategy;
  selection_status: "selected" | "unresolved";
  selected_verifier_id: string | null;
  status: "evaluated" | "evaluated_with_unresolved_metrics" | "not_evaluated";
  holdout_candidate_status: "measured" | "unresolved" | null;
  panel_error_delta: number | null;
  delta_effective_votes: number | null;
  standalone_accuracy: number | null;
  mean_error_correlation_with_current_panel: number | null;
  uncertainty: null | MarginalEvidenceBenchmarkReportV01_Uncertainty;
  probe_effect: null | MarginalEvidenceBenchmarkReportV01_Probe_effect;
  warnings: string[];
};

export type MarginalEvidenceBenchmarkReportV01_Id_array = string[];

export type MarginalEvidenceBenchmarkReportV01_Metric_interval = {
  point: number | null;
  ci_low: number | null;
  ci_high: number | null;
  replicates_used: number;
  replicates_undefined: number;
};

export type MarginalEvidenceBenchmarkReportV01_Probe_effect = {
  total: number;
  current_breached: number;
  augmented_breached: number;
  breaches_prevented: number;
  current_breach_rate: number;
  augmented_breach_rate: number;
};

export type MarginalEvidenceBenchmarkReportV01_Selector = {
  strategy: MarginalEvidenceBenchmarkReportV01_Strategy;
  status: "selected" | "unresolved";
  selected_verifier_id: string | null;
  reason_code: string;
  design_score: number | null;
};

export type MarginalEvidenceBenchmarkReportV01_Sha256 = string;

export type MarginalEvidenceBenchmarkReportV01_Split = {
  matrix: string;
  input_digest_sha256: MarginalEvidenceBenchmarkReportV01_Sha256;
  non_probe_candidates: number;
  probe_candidates: number;
};

export type MarginalEvidenceBenchmarkReportV01_Strategy = "marginal_effective_votes" | "random_eligible" | "highest_standalone_accuracy" | "different_family_first" | "minimum_mean_pairwise_error_correlation";

export type MarginalEvidenceBenchmarkReportV01_Uncertainty = {
  method: "paired candidate-level nonparametric bootstrap (percentile interval, linear interpolation)";
  sampling_unit: "non_probe_candidate_row";
  confidence_level: number;
  replicates: number;
  seed: number;
  non_probe_candidates: number;
  min_candidates_for_inference: 5;
  sufficient_for_inference: boolean;
  panel_error_delta: null | MarginalEvidenceBenchmarkReportV01_Metric_interval;
  effective_votes_delta: null | MarginalEvidenceBenchmarkReportV01_Metric_interval;
};

/** Diagnostic add-one verifier analysis for a fixed verdict matrix and gate rule. The report measures contextual panel changes and grants no routing, acceptance, EvaluatorPlan, or merge authority. */
export type MarginalEvidenceReportV01 = {
  schema: "marginal-evidence-report-v0.1";
  gate_id: string;
  evidence_class: "synthetic" | "observed";
  authority: "diagnostic_only";
  analysis: {
    current_verifier_ids: string[];
    candidate_verifier_ids: string[];
    bootstrap: null | {
      replicates: number;
      seed: number;
      confidence_level: number;
    };
    quorum: number;
    non_probe_candidates: number;
    probe_candidates: number;
  };
  current_panel: {
    nominal_votes: number;
    error: number;
    mean_verifier_accuracy: number;
    mean_pairwise_error_correlation: number | null;
    effective_votes: number | null;
    effective_votes_censored: boolean;
  };
  candidates: ({
    id: string;
    status: "measured" | "unresolved";
    unresolved_reasons: string[];
    standalone_accuracy: number;
    current_panel_error: number;
    augmented_panel_error: number;
    panel_error_delta: number;
    current_effective_votes: number | null;
    augmented_effective_votes: number | null;
    delta_effective_votes: number | null;
    current_effective_votes_censored: boolean;
    augmented_effective_votes_censored: boolean;
    mean_error_correlation_with_current_panel: number | null;
    pairwise_error_correlations: ({
      current_verifier_id: string;
      error_correlation: number | null;
    })[];
    transition_counts: {
      candidate_correct_on_current_panel_errors: number;
      candidate_wrong_on_current_panel_correct_rows: number;
      panel_decisions_changed: number;
      panel_decisions_changed_to_correct: number;
      panel_decisions_changed_to_wrong: number;
    };
    probe_effect: null | {
      total: number;
      current_breached: number;
      augmented_breached: number;
      breaches_prevented: number;
      current_breach_rate: number;
      augmented_breach_rate: number;
    };
    uncertainty: null | MarginalEvidenceReportV01_Uncertainty;
    warnings: string[];
  })[];
  warnings: string[];
  provenance: {
    tool: "idkmesh marginal-evidence";
    tool_version: string;
    input_digest_sha256: string;
    analysis_digest_sha256: string;
  };
};

export type MarginalEvidenceReportV01_Metric_interval = {
  point: number | null;
  ci_low: number | null;
  ci_high: number | null;
  replicates_used: number;
  replicates_undefined: number;
};

export type MarginalEvidenceReportV01_Uncertainty = {
  method: "paired candidate-level nonparametric bootstrap (percentile interval, linear interpolation)";
  sampling_unit: "non_probe_candidate_row";
  confidence_level: number;
  replicates: number;
  seed: number;
  non_probe_candidates: number;
  min_candidates_for_inference: 5;
  sufficient_for_inference: boolean;
  panel_error_delta: null | MarginalEvidenceReportV01_Metric_interval;
  effective_votes_delta: null | MarginalEvidenceReportV01_Metric_interval;
};

/** Frozen manifest for descriptive synthesis of at least two already-produced marginal-evidence benchmark reports. It grants no routing, selection, acceptance, or merge authority. */
export type MarginalEvidenceSynthesisConfigV01 = {
  schema: "marginal-evidence-synthesis-config-v0.1";
  synthesis_id: string;
  evidence_class: string;
  selection_rule_version: "marginal-selection-interval-dominance-v0.1";
  benchmark_reports: string[];
};

/** Descriptive cross-cohort aggregation of frozen held-out marginal-evidence benchmark reports. The report intentionally contains no winner, ranking, routing recommendation, EvaluatorPlan, acceptance verdict, or merge authority. */
export type MarginalEvidenceSynthesisReportV01 = {
  schema: "marginal-evidence-synthesis-report-v0.1";
  synthesis_id: string;
  evidence_class: string;
  authority: "diagnostic_only";
  analysis: {
    mode: "descriptive-cross-cohort-v0.1";
    selection_rule_version: "marginal-selection-interval-dominance-v0.1";
    benchmark_count: number;
    total_holdout_non_probe_candidates: number;
  };
  cohorts: MarginalEvidenceSynthesisReportV01_Cohort[];
  strategies: [MarginalEvidenceSynthesisReportV01_Strategy & {
    strategy?: "marginal_effective_votes";
  }, MarginalEvidenceSynthesisReportV01_Strategy & {
    strategy?: "random_eligible";
  }, MarginalEvidenceSynthesisReportV01_Strategy & {
    strategy?: "highest_standalone_accuracy";
  }, MarginalEvidenceSynthesisReportV01_Strategy & {
    strategy?: "different_family_first";
  }, MarginalEvidenceSynthesisReportV01_Strategy & {
    strategy?: "minimum_mean_pairwise_error_correlation";
  }];
  warnings: string[];
  provenance: {
    tool: "idkmesh marginal-evidence-synthesis";
    tool_version: string;
    config_digest_sha256: MarginalEvidenceSynthesisReportV01_Sha256hex;
    synthesis_input_digest_sha256: MarginalEvidenceSynthesisReportV01_Sha256hex;
  };
};

export type MarginalEvidenceSynthesisReportV01_Cohort = {
  benchmark_id: string;
  gate_id: string;
  report: string;
  report_digest_sha256: MarginalEvidenceSynthesisReportV01_Sha256hex;
  design_input_digest_sha256: MarginalEvidenceSynthesisReportV01_Sha256hex;
  holdout_input_digest_sha256: MarginalEvidenceSynthesisReportV01_Sha256hex;
  holdout_non_probe_candidates: number;
};

export type MarginalEvidenceSynthesisReportV01_FiniteNumberOrNull = number | null;

export type MarginalEvidenceSynthesisReportV01_MetricEffectiveVotes = {
  measured: number;
  unresolved: number;
  positive: number;
  unchanged: number;
  negative: number;
  macro_mean: MarginalEvidenceSynthesisReportV01_FiniteNumberOrNull;
};

export type MarginalEvidenceSynthesisReportV01_MetricPanelError = {
  measured: number;
  unresolved: number;
  improved: number;
  unchanged: number;
  worsened: number;
  macro_mean: MarginalEvidenceSynthesisReportV01_FiniteNumberOrNull;
  holdout_row_weighted_mean: MarginalEvidenceSynthesisReportV01_FiniteNumberOrNull;
};

export type MarginalEvidenceSynthesisReportV01_Outcome = {
  benchmark_id: string;
  holdout_non_probe_candidates: number;
  strategy: "marginal_effective_votes" | "random_eligible" | "highest_standalone_accuracy" | "different_family_first" | "minimum_mean_pairwise_error_correlation";
  selection_status: "selected" | "unresolved";
  selected_verifier_id: string | null;
  status: "not_evaluated" | "evaluated" | "evaluated_with_unresolved_metrics";
  panel_error_delta: MarginalEvidenceSynthesisReportV01_FiniteNumberOrNull;
  delta_effective_votes: MarginalEvidenceSynthesisReportV01_FiniteNumberOrNull;
};

export type MarginalEvidenceSynthesisReportV01_Sha256hex = string;

export type MarginalEvidenceSynthesisReportV01_Strategy = {
  strategy: "marginal_effective_votes" | "random_eligible" | "highest_standalone_accuracy" | "different_family_first" | "minimum_mean_pairwise_error_correlation";
  cohorts_total: number;
  selection_resolved: number;
  selection_unresolved: number;
  holdout_evaluated: number;
  holdout_not_evaluated: number;
  panel_error_delta: MarginalEvidenceSynthesisReportV01_MetricPanelError;
  effective_votes_delta: MarginalEvidenceSynthesisReportV01_MetricEffectiveVotes;
  cohort_outcomes: MarginalEvidenceSynthesisReportV01_Outcome[];
};

/** Declares one project that runs on IDKMesh Core through explicit DomainPack, verification, governance, storage, and adapter boundaries. */
export type ProjectManifest = {
  schema_version: "0.1";
  id: string;
  version: string;
  name: string;
  description?: string;
  core_compatibility: {
    core_api_version: string;
    work_unit_schema_version: string;
  };
  roots: ({
    id: string;
    kind: "repository" | "artifact" | "dataset" | "knowledge" | "other";
    uri: string;
    writable: boolean;
  })[];
  goal_entrypoints: string[];
  domain_packs: {
    id: string;
    version: string;
    path: string;
  }[];
  allowed_work_unit_kinds: ("coding" | "testing" | "review" | "benchmarking" | "documentation" | "research" | "integration" | "governance" | "other")[];
  verification: {
    default_policy_ref: string;
    minimum_independent_verifiers: number;
    human_integration_required: boolean;
  };
  risk_policy: {
    allowed_risk_classes: ("low" | "medium" | "high" | "critical")[];
    maximum_autonomous_risk: "none" | "low" | "medium" | "high" | "critical";
  };
  integration_policy: {
    mode: "proposal_only" | "protected_pr" | "manual" | "custom";
    target_branch: string;
    automatic_merge_allowed: boolean;
    human_decision_required: boolean;
  };
  governance: {
    owners: string[];
    reviewers: string[];
    decision_refs: string[];
  };
  metrics: {
    primary: string;
    secondary: string[];
  };
  worker_constraints: {
    required_capabilities: string[];
    forbidden_capabilities: string[];
  };
  storage: {
    artifact_root: string;
    result_root: string;
    provenance_root: string;
  };
  enabled_adapters: string[];
  metadata?: { [key: string]: IdkmeshJsonValue };
};

/** Checked-in, expiring authorization that allows already-concrete zero-project-cost compute offers to survive Free Resource Mesh admission. Discovery/resource capabilities and concrete runtime capabilities use separate vocabularies and are gated separately. This schema grants no dispatch, correctness, repository-write, or merge authority. */
export type ResourceComputeBindingsV01 = {
  version: 1;
  bindings: ResourceComputeBindingsV01_Binding[];
};

export type ResourceComputeBindingsV01_Binding = {
  id: string;
  resource_id: string;
  provider: string;
  allowed_cost_classes: ("local_owned" | "donated" | "public_project_ci" | "grant" | "free_tier")[];
  /** Broad capability evidence that must still be present on the bound Free Resource Mesh resource. These names belong to the discovery/resource vocabulary, not the concrete runtime-offer vocabulary. */
  required_resource_capabilities: string[];
  /** Concrete runtime capability names that the binding permits an already-materialized Compute Offer to expose. */
  allowed_capabilities: string[];
  offer_id_prefix?: string;
  enabled: boolean;
  terms_eligible: boolean;
  authorization_scope: string;
  reviewed_at: string;
  max_age_days: number;
};

export type ResourceOfferRegistryV01 = {
  version: 1;
  observed_at: string;
  offers: ({
    id: string;
    status: "available" | "conditional" | "manual" | "excluded";
    kind: string;
    task_classes: string[];
    capabilities: string[];
    project_cost_usd: 0;
    human_interaction_required: boolean;
    requires_repository_secret: boolean;
    external_data_processor: boolean;
    availability_weight: number;
    human_setup_cost: number;
    scarcity: number;
    security_risk: number;
    activation: string;
    security: {
      repo_write_authority: false;
      merge_authority: false;
    };
    source: {
      url: string;
      checked_at: string;
      max_age_days: number;
    };
  })[];
};

/** A provenance-carrying result produced for a Work Unit and suitable for independent verification. */
export type ResultManifest = {
  schema_version: "0.1.0";
  work_unit_id: string;
  attempt_id?: string;
  status: "completed" | "failed" | "partial" | "cancelled" | "timed_out" | "rejected";
  worker: {
    id: string;
    implementation?: string;
    agent_role?: string;
    model_family?: string;
    model_version?: string;
    key_id?: string;
  };
  environment: {
    os?: string;
    architecture?: string;
    cpu?: string;
    gpu?: string;
    memory_mb?: number;
    container_image?: string;
    container_digest?: string;
    repository_commit?: string;
    tool_versions?: { [key: string]: string };
  };
  artifacts: {
    name: string;
    kind: string;
    uri?: string;
    sha256: string;
    size_bytes?: number;
    media_type?: string;
  }[];
  evidence: ({
    kind: string;
    outcome: "pass" | "fail" | "inconclusive" | "informational";
    summary?: string;
    artifact_sha256?: string;
    metric?: number;
    unit?: string;
  })[];
  metrics?: { [key: string]: number | string | boolean | null };
  confidence: number;
  started_at?: string;
  finished_at?: string;
  duration_seconds?: number;
  logs?: ({
    uri?: string;
    sha256?: string;
    stream?: "stdout" | "stderr" | "event" | "other";
  })[];
  verifier_results?: ({
    verifier_id: string;
    decision: "accept" | "reject" | "inconclusive" | "escalate";
    confidence?: number;
    model_family?: string;
    method?: string;
    evidence_refs?: string[];
    signature?: string;
  })[];
  reproducibility?: {
    status?: "not_checked" | "reproduced" | "failed_to_reproduce" | "partially_reproduced";
    independent_attempts?: number;
    successful_attempts?: number;
  };
  signature?: string;
  signed_payload_sha256?: string;
};

/** A worker self-report describing one attempt at a Work Unit. This object records candidate outputs and provenance; it is not an acceptance or independent-verification verdict. */
export type ResultManifestV01 = {
  schema_version: "0.1";
  id: string;
  work_unit_id: string;
  work_unit_version: number;
  attempt: number;
  worker: {
    id: string;
    type: "human" | "agent" | "system" | "hybrid";
    adapter: string;
    adapter_version?: string;
    model?: {
      provider?: string;
      name: string;
      version?: string;
    };
  };
  status: "succeeded" | "failed" | "error" | "timeout" | "cancelled";
  started_at: string;
  finished_at: string;
  produced_artifacts: ({
    id: string;
    type: "patch" | "file" | "report" | "test_result" | "dataset" | "decision" | "review" | "log" | "other";
    locator: string;
    digest: string;
    media_type?: string;
    description?: string;
  })[];
  logs: ({
    type: "stdout" | "stderr" | "trace" | "tool_calls" | "other";
    locator: string;
    digest?: string;
  })[];
  metrics: { [key: string]: number | null };
  resources: {
    wall_seconds: number;
    cpu_seconds?: number;
    max_rss_mb?: number;
    compute_units?: number;
    human_minutes?: number;
    tokens?: number;
  };
  self_report: {
    summary: string;
    claims: string[];
    confidence?: {
      value: number;
      meaning: "probability_of_success" | "subjective" | "uncalibrated";
    };
  };
  provenance: {
    work_unit_digest: string;
    source_revision: string;
    worker_config_digest?: string;
    environment: {
      platform?: string;
      python?: string;
      container_image?: string;
      tool_versions?: { [key: string]: string };
    };
  };
  verification_request: {
    expected_validator_ids: string[];
    evidence_artifact_ids: string[];
    notes?: string;
  };
  extensions?: { [key: string]: IdkmeshJsonValue };
};

/** Read-only historical/shadow dataset for comparing task-routing strategies without changing repository state. Routing inputs and retrospective outcomes are separated to reduce hindsight leakage. */
export type RoutingReplayV0 = {
  schema_version: "0.1.0";
  dataset_id: string;
  repository: {
    full_name: string;
    commit?: string;
    source_url?: string;
    captured_at?: string;
  };
  annotation_policy: {
    method: string;
    hindsight_rule: string;
    annotator?: string;
    notes?: string[];
  };
  tasks: {
    id: string;
    source_ref: string;
    skill: string;
    impact: number;
    information_gain: number;
    review_cost: number;
    compute_cost: number;
    risk: number;
    accessibility: number;
    feature_provenance?: { [key: string]: string };
  }[];
  workers: {
    id: string;
    group: string;
    skills: { [key: string]: number };
    profile_provenance?: string;
  }[];
  snapshots: {
    id: string;
    observed_at: string;
    available_task_ids: string[];
    available_worker_ids: string[];
    active_attempts: {
      task_id: string;
      worker_group: string;
    }[];
    /** Evidence known by the replay time. Future outcomes must not appear here. */
    evidence: {
      task_id: string;
      verified: boolean;
      quality: number;
      verification_strength: number;
      diversity: number;
      descendant_value: number;
      human_review_cost: number;
      compute_cost: number;
      penalty?: number;
      source_ref?: string;
    }[];
    observed_duplicate_rate?: number;
    observed_concentration?: number;
    /** Held-out outcomes that became known after the snapshot. Routing code must not use these to generate recommendations. */
    retrospective_outcomes: { [key: string]: {
        verified_utility?: number;
        eventual_verified?: boolean;
        source_ref?: string;
      } };
    source_refs?: string[];
  }[];
  limitations: string[];
};

/** A non-selecting run-level aggregation of canonical worker ResultManifest and independent VerificationResult evidence. It is human/governance decision support and cannot authorize integration. */
export type RunEvidenceReportV01 = {
  schema_version: "0.1";
  kind: "idkmesh-run-evidence-report";
  run_id: string;
  source_run_kind: "idkmesh-two-attempt-run";
  source_run_digest: RunEvidenceReportV01_Digest;
  source_config_digest: RunEvidenceReportV01_Digest;
  orchestrator_version: string;
  work_unit: {
    id: string;
    version: number;
    digest: RunEvidenceReportV01_Digest;
  };
  verifier_policy_digest: RunEvidenceReportV01_Digest;
  attempts: RunEvidenceReportV01_Attempt[];
  summary: {
    attempt_count: number;
    supported: number;
    rejected: number;
    inconclusive: number;
    control_errors: number;
    verification_disagreement: boolean;
    control_failure_present: boolean;
  };
  warnings: string[];
  human_decision: {
    status: "pending";
    selected_attempt_id: null;
    integration_authority: "external_human_or_governance";
  };
  authority: {
    canonical_state_write: false;
    git_push: false;
    merge: false;
    automatic_candidate_selection: false;
  };
};

export type RunEvidenceReportV01_Attempt = {
  attempt_id: string;
  order: number;
  worker_adapter: string;
  state: "verified" | "worker_error" | "result_manifest_error" | "verification_error";
  evidence_state: "supported" | "rejected" | "inconclusive" | "worker_error" | "result_manifest_error" | "verification_error";
  worker: RunEvidenceReportV01_Worker;
  verifier: RunEvidenceReportV01_Verifier;
  error: string | null;
};

export type RunEvidenceReportV01_Check = {
  id: string;
  status: string;
  required: boolean;
};

export type RunEvidenceReportV01_Digest = string;

export type RunEvidenceReportV01_Verifier = {
  id: string;
  status: string;
  recommendation: "accept_candidate" | "reject_candidate" | "escalate" | "insufficient_evidence";
  verification_semantic_digest: RunEvidenceReportV01_Digest;
  checks: RunEvidenceReportV01_Check[];
} | null;

export type RunEvidenceReportV01_Worker = {
  id: string;
  status: string;
  result_manifest_id: string;
  result_manifest_digest: RunEvidenceReportV01_Digest;
} | null;

/** Observed search/answer-engine visibility evidence; records observations without converting them into ranking guarantees or population-level claims. */
export type SearchVisibilityObservationV01 = {
  schema_version: "0.1";
  observations: SearchVisibilityObservationV01_Observation[];
};

export type SearchVisibilityObservationV01_Observation = {
  id: string;
  observed_at: string;
  engine: "google" | "bing" | "duckduckgo" | "brave" | "yahoo" | "apple" | "amazon" | "meta" | "chatgpt" | "gemini" | "claude" | "perplexity" | "copilot" | "grok" | "mistral" | "you" | "other";
  surface: "web_search" | "ai_answer" | "webmaster_console" | "referral" | "index_status";
  evidence_class: "manual_reproduction" | "webmaster_export" | "referral_log" | "index_inspection";
  mapped_intent: string;
  query: string;
  target_url: string;
  surfaced: boolean;
  citation_url?: string | null;
  position?: number | null;
  evidence_ref?: string | null;
  notes: string;
};

/** Local coordinator metadata. A snapshot is not a capability, execution permission, verification, acceptance or merge authority. */
export type TaskClaimV01 = {
  kind: "idkmesh-task-claim";
  schema_version: "0.1";
  task: {
    kind: "idkmesh-enterprise-resource-ref";
    schema_version: "0.1";
    tenant_id: TaskClaimV01_ScopeId;
    project_id: TaskClaimV01_ScopeId;
    resource_type: "task";
    resource_id: TaskClaimV01_ScopeId;
  };
  request_id: string;
  request_digest: TaskClaimV01_Digest;
  slot: number;
  epoch: number;
  owner: {
    principal_id: string;
    issuer: string;
    actor_type: "human" | "github_app" | "github_actions" | "service" | "provider" | "node";
  };
  binding: {
    work_unit_digest: TaskClaimV01_Digest;
    source_revision: string;
    inputs_digest: TaskClaimV01_Digest;
  };
  state: "active" | "released" | "expired";
  created_at: TaskClaimV01_EpochSeconds;
  acknowledged_at: TaskClaimV01_EpochSeconds | null;
  ack_by: TaskClaimV01_EpochSeconds;
  lease_until: TaskClaimV01_EpochSeconds;
  progress_by: TaskClaimV01_EpochSeconds;
  hard_until: TaskClaimV01_EpochSeconds;
  occupancy: "none" | "unknown" | "running" | "terminal";
  operation_id: TaskClaimV01_Digest | null;
  execution_reference: string | null;
  submission_digest: TaskClaimV01_Digest | null;
  authority: {
    executes_worker: false;
    accepts_candidate: false;
    merge: false;
  };
};

export type TaskClaimV01_Digest = string;

export type TaskClaimV01_EpochSeconds = number;

export type TaskClaimV01_ScopeId = string;

/** An independent verifier's evidence and recommendation for one worker ResultManifest. It is decision support, not the final integration/merge decision. */
export type VerificationResultV01 = {
  schema_version: "0.1";
  id: string;
  result_manifest_id: string;
  work_unit_id: string;
  work_unit_version: number;
  attempt: number;
  verifier: {
    id: string;
    type: "human" | "agent" | "system" | "hybrid";
    adapter: string;
    adapter_version?: string;
    model?: {
      provider?: string;
      name: string;
      version?: string;
    };
  };
  independence: {
    independent_from_worker: boolean;
    worker_id_observed: string;
    shared_model_family: boolean;
    shared_runtime: boolean;
    correlation_notes?: string;
  };
  status: "passed" | "failed" | "inconclusive" | "error" | "timeout" | "cancelled";
  started_at: string;
  finished_at: string;
  checks: ({
    id: string;
    type: "test" | "review" | "schema" | "lint" | "security" | "formal" | "reproduction" | "policy" | "other";
    required: boolean;
    status: "passed" | "failed" | "skipped" | "inconclusive" | "error";
    summary: string;
    evidence_ids: string[];
    diagnostics?: string;
  })[];
  evidence: ({
    id: string;
    type: "test_output" | "review" | "benchmark" | "trace" | "attestation" | "artifact_hash" | "static_analysis" | "security_report" | "other";
    locator: string;
    digest: string;
    media_type?: string;
    description?: string;
  })[];
  findings: ({
    severity: "info" | "low" | "medium" | "high" | "critical";
    category: "correctness" | "regression" | "security" | "performance" | "maintainability" | "scope" | "provenance" | "policy" | "other";
    summary: string;
    path?: string;
    line?: number;
  })[];
  metrics: { [key: string]: number | null };
  resources: {
    wall_seconds: number;
    cpu_seconds?: number;
    max_rss_mb?: number;
    compute_units?: number;
    human_minutes?: number;
    tokens?: number;
  };
  provenance: {
    result_manifest_digest: string;
    work_unit_digest: string;
    source_revision: string;
    verifier_config_digest?: string;
    environment: {
      platform?: string;
      python?: string;
      container_image?: string;
      tool_versions?: { [key: string]: string };
    };
  };
  decision_support: {
    recommendation: "accept_candidate" | "reject_candidate" | "escalate" | "insufficient_evidence";
    confidence: number;
    rationale: string;
  };
  attestation?: {
    signer_id: string;
    algorithm: string;
    signature: string;
  };
  extensions?: { [key: string]: IdkmeshJsonValue };
};

/** A point-in-time, domain-scoped view of verifier availability, validator coverage, independence, cost, and reliability evidence for advisory verifier-allocation research. It is not a durable reputation record. */
export type VerifierObservationPoolV01 = {
  schema_version: "0.1";
  kind: "idkmesh-verifier-observation-pool";
  repository: string;
  source_revision: string;
  captured_at: string;
  work_unit_id: string;
  task_domain: string;
  worker_id: string;
  reliability_max_age_days: number;
  verifier_candidates: VerifierObservationPoolV01_Verifier[];
  limitations: string[];
};

export type VerifierObservationPoolV01_Verifier = {
  id: string;
  family: string;
  provider_family?: string | null;
  available: boolean;
  supported_validator_ids: string[];
  review_units: number;
  queue_load: number;
  independence: {
    independent_from_worker: boolean;
    shared_model_family: boolean;
    shared_runtime: boolean;
  };
  reliability: {
    basis: "live_outcomes" | "known_bad_probes" | "synthetic" | "unknown";
    alpha: number;
    beta: number;
    sample_count: number;
    domain: string;
    observed_at: string | null;
    shift_warning: boolean;
    source_refs: string[];
    known_bad_probe_trials: number;
    known_bad_probe_breaches: number;
  };
};

/** A bounded unit of useful work that can be scheduled, executed, reproduced, and independently verified. */
export type WorkUnit = {
  schema_version: "0.1.0";
  id: string;
  goal_ref: string;
  parent_work_unit_id?: string | null;
  task_type: "research" | "decompose" | "implement" | "test" | "verify" | "review" | "benchmark" | "simulate" | "analyze" | "document" | "integrate" | "other";
  description: string;
  inputs?: ({
    name: string;
    kind: "artifact" | "repository" | "dataset" | "text" | "url" | "other";
    uri?: string;
    sha256?: string;
    required?: boolean;
  })[];
  dependencies?: string[];
  required_capabilities?: {
    operating_systems?: string[];
    architectures?: string[];
    gpu?: boolean;
    tools?: string[];
    skills?: string[];
    model_families?: string[];
  };
  resource_hints?: {
    cpu_cores?: number;
    memory_mb?: number;
    gpu_memory_mb?: number;
    disk_mb?: number;
    estimated_seconds?: number;
    max_seconds?: number;
  };
  execution_constraints?: {
    network?: "none" | "allowlist" | "unrestricted";
    filesystem?: "ephemeral" | "workspace-read" | "workspace-write";
    secrets_allowed?: boolean;
    deterministic_requested?: boolean;
    sandbox_required?: boolean;
  };
  expected_artifacts?: {
    kind: string;
    name?: string;
    required?: boolean;
  }[];
  verification_policy: {
    mode: "none" | "deterministic" | "independent" | "quorum" | "adversarial" | "hybrid";
    min_verifiers?: number;
    replication_factor?: number;
    required_checks?: string[];
    diversity_dimensions?: string[];
    human_escalation_on_disagreement?: boolean;
  };
  privacy_class: "public" | "restricted" | "private-local" | "confidential";
  priority?: number;
  deadline?: string | null;
  random_seed?: number | null;
  tags?: string[];
  created_at?: string;
  created_by?: string;
  provenance_requirements?: {
    content_hashes?: boolean;
    environment_manifest?: boolean;
    signature?: boolean;
    logs?: boolean;
  };
};

/** A bounded, independently executable and independently verifiable unit of work. */
export type WorkUnitV01 = {
  schema_version: "0.1";
  id: string;
  version: number;
  kind: "coding" | "testing" | "research" | "review" | "integration" | "documentation" | "governance" | "other";
  objective: string;
  context?: {
    summary?: string;
    references?: string[];
    max_context_bytes?: number;
  };
  inputs: WorkUnitV01_ArtifactRef[];
  outputs: WorkUnitV01_ArtifactSpec[];
  dependencies: ({
    work_unit_id: string;
    relationship: "requires" | "blocks" | "informs" | "validates" | "derived_from";
    condition?: string;
  })[];
  constraints: {
    allowed_paths: string[];
    forbidden_paths: string[];
    policies: string[];
  };
  uncertainty: {
    statement: string;
    confidence?: number;
    resolution_strategy?: string;
  }[];
  permissions: {
    network: "none" | "allowlist" | "unrestricted";
    network_allowlist?: string[];
    filesystem_write: string[];
    secrets: string[];
    process_execution: boolean;
  };
  validators: ({
    id: string;
    type: "test" | "review" | "schema" | "lint" | "security" | "formal" | "reproduction" | "other";
    required: boolean;
    command?: string[];
    description?: string;
  })[];
  evidence_requirements: ({
    type: "test_output" | "review" | "benchmark" | "citation" | "trace" | "attestation" | "artifact_hash" | "other";
    required: boolean;
    description?: string;
  })[];
  budget: {
    wall_seconds?: number;
    compute_units?: number;
    human_minutes?: number;
    tokens?: number;
  };
  provenance: {
    created_by: string;
    creator_type: "human" | "agent" | "hybrid" | "system";
    source: string;
    parent_work_unit_ids?: string[];
  };
  failure_semantics: {
    retryable: boolean;
    max_attempts: number;
    on_failure: "stop" | "retry" | "replan" | "escalate" | "continue_degraded";
  };
  /** Namespaced experimental fields. Keys SHOULD use reverse-DNS or project prefixes. */
  extensions?: { [key: string]: IdkmeshJsonValue };
};

export type WorkUnitV01_ArtifactRef = {
  id: string;
  type: "file" | "directory" | "git_ref" | "dataset" | "url" | "text" | "json" | "other";
  locator: string;
  digest?: string;
};

export type WorkUnitV01_ArtifactSpec = {
  id: string;
  type: "patch" | "file" | "report" | "test_result" | "dataset" | "decision" | "review" | "other";
  description: string;
  media_type?: string;
};

/** A bounded, portable unit of work with explicit capabilities, authority, risk, verification, evidence, provenance, and project-spend requirements. */
export type WorkUnitV02 = {
  schema_version: "0.2";
  id: string;
  version: number;
  kind: "coding" | "testing" | "review" | "benchmarking" | "documentation" | "research" | "integration" | "governance" | "other";
  objective: string;
  context?: {
    summary?: string;
    references?: string[];
    max_context_bytes?: number;
  };
  inputs: WorkUnitV02_ArtifactRef[];
  outputs: WorkUnitV02_ArtifactSpec[];
  dependencies: ({
    work_unit_id: string;
    relationship: "requires" | "blocks" | "informs" | "validates" | "derived_from";
    condition?: string;
  })[];
  requirements: {
    /** Vendor-neutral capabilities required from a worker or execution environment. */
    capabilities: string[];
    resources: {
      cpu_cores_min: number;
      memory_mb_min: number;
      disk_mb_min?: number;
      gpu: "none" | "optional" | "required";
      accelerator_capabilities?: string[];
    };
  };
  constraints: {
    allowed_paths: string[];
    forbidden_paths: string[];
    policies: string[];
  };
  uncertainty: {
    statement: string;
    confidence?: number;
    resolution_strategy?: string;
  }[];
  security: {
    risk_class: "low" | "medium" | "high" | "critical";
    data_classification: "public" | "internal" | "confidential" | "restricted";
    minimum_worker_trust: "untrusted" | "identified" | "trusted" | "attested";
    sandbox_required: boolean;
    notes?: string;
  };
  permissions: {
    network: "none" | "allowlist" | "unrestricted";
    network_allowlist?: string[];
    filesystem_write: string[];
    secrets: string[];
    process_execution: boolean;
  };
  verification_policy: {
    strategy: "all_required" | "quorum" | "threshold" | "custom";
    independent_from_worker: boolean;
    minimum_independent_verifiers: number;
    quorum?: number;
    acceptance_rule?: string;
  };
  validators: ({
    id: string;
    type: "test" | "review" | "schema" | "lint" | "security" | "formal" | "reproduction" | "benchmark" | "other";
    required: boolean;
    command?: string[];
    description?: string;
  })[];
  evidence_requirements: ({
    type: "test_output" | "review" | "benchmark" | "citation" | "trace" | "attestation" | "artifact_hash" | "other";
    required: boolean;
    description?: string;
  })[];
  /** Resource limits. project_spend_usd_max is the maximum amount IDKMesh itself may pay for this Work Unit; donor electricity/hardware is tracked separately and must be voluntary and transparent. */
  budget: {
    wall_seconds?: number;
    compute_units?: number;
    human_minutes?: number;
    tokens?: number;
    project_spend_usd_max: number;
    paid_fallback_allowed: boolean;
  };
  provenance: {
    created_by: string;
    creator_type: "human" | "agent" | "hybrid" | "system";
    source: string;
    source_revision?: string;
    created_at?: string;
    parent_work_unit_ids?: string[];
  };
  failure_semantics: {
    retryable: boolean;
    max_attempts: number;
    on_failure: "stop" | "retry" | "replan" | "escalate" | "continue_degraded";
  };
  /** Namespaced experimental fields. Keys SHOULD use reverse-DNS or project prefixes. */
  extensions?: { [key: string]: IdkmeshJsonValue };
};

export type WorkUnitV02_ArtifactRef = {
  id: string;
  type: "file" | "directory" | "git_ref" | "dataset" | "url" | "text" | "json" | "other";
  locator: string;
  digest?: string;
};

export type WorkUnitV02_ArtifactSpec = {
  id: string;
  type: "patch" | "file" | "report" | "test_result" | "dataset" | "decision" | "review" | "other";
  description: string;
  media_type?: string;
};

/** Every served operation, keyed `METHOD /path`. */
export interface IdkmeshApiOperations {
  /** List persisted connector control metadata */
  "GET /api/v1/connections": {
    queryParameters: { cursor?: string; limit?: number; };
    responses: {
      "200": {
        "application/json": IdkmeshListV01;
      };
      "400": {
        "application/json": IdkmeshApiErrorV01;
      };
      "403": {
        "application/json": IdkmeshApiErrorV01;
      };
      "503": {
        "application/json": IdkmeshApiErrorV01;
      };
    };
  };
  /** Read one persisted connector control record */
  "GET /api/v1/connections/{connection_id}": {
    pathParameters: { connection_id: string; };
    responses: {
      "200": {
        "application/json": IdkmeshControlTowerConnectionResponseV01;
      };
      "400": {
        "application/json": IdkmeshApiErrorV01;
      };
      "403": {
        "application/json": IdkmeshApiErrorV01;
      };
      "404": {
        "application/json": IdkmeshApiErrorV01;
      };
      "503": {
        "application/json": IdkmeshApiErrorV01;
      };
    };
  };
  /** List the static connector driver declarations */
  "GET /api/v1/connector-drivers": {
    responses: {
      "200": {
        "application/json": IdkmeshControlTowerConnectorDriversResponseV01;
      };
      "400": {
        "application/json": IdkmeshApiErrorV01;
      };
      "403": {
        "application/json": IdkmeshApiErrorV01;
      };
    };
  };
  /** Query the canonical append-only event stream */
  "GET /api/v1/events": {
    responses: {
      "200": {
        "application/json": IdkmeshListV01;
      };
      "400": {
        "application/json": IdkmeshApiErrorV01;
      };
      "403": {
        "application/json": IdkmeshApiErrorV01;
      };
      "503": {
        "application/json": IdkmeshApiErrorV01;
      };
    };
  };
  /** Stream canonical events (resumable SSE) */
  "GET /api/v1/events/stream": {
    responses: {
      "200": {
        "text/event-stream": IdkmeshEventV01;
      };
      "403": {
        "application/json": IdkmeshApiErrorV01;
      };
    };
  };
  /** Read privacy-safe aggregate operational metrics */
  "GET /api/v1/metrics": {
    responses: {
      "200": {
        "application/json": IdkmeshApiOperationalMetricsV01;
        "application/vnd.idkmesh.control-tower.v1+json": IdkmeshApiOperationalMetricsV01;
      };
      "403": {
        "application/json": IdkmeshApiErrorV01;
      };
    };
  };
  /** Read the aggregate metrics as Prometheus text */
  "GET /api/v1/metrics/prometheus": {
    responses: {
      "200": {
        "text/plain": string;
      };
      "403": {
        "application/json": IdkmeshApiErrorV01;
      };
    };
  };
  /** Read this OpenAPI contract */
  "GET /api/v1/openapi.json": {
    responses: {
      "200": {
        "application/json": { [key: string]: IdkmeshJsonValue };
      };
      "403": {
        "application/json": IdkmeshApiErrorV01;
      };
    };
  };
  /** Read one project's resource projection */
  "GET /api/v1/projects/{project_id}": {
    pathParameters: { project_id: string; };
    responses: {
      "200": {
        "application/json": IdkmeshControlTowerProjectResponseV01;
      };
      "403": {
        "application/json": IdkmeshApiErrorV01;
      };
      "404": {
        "application/json": IdkmeshApiErrorV01;
      };
      "503": {
        "application/json": IdkmeshApiErrorV01;
      };
    };
  };
  /** Validate and render one Run Evidence Report v0.1 */
  "POST /api/v1/run-evidence/inspect": {
    requestBody: {
      "application/json": RunEvidenceReportV01;
      "application/vnd.idkmesh.control-tower.v1+json": RunEvidenceReportV01;
    };
    responses: {
      "200": {
        "application/json": IdkmeshControlTowerInspectionResponseV01;
        "application/vnd.idkmesh.control-tower.v1+json": IdkmeshControlTowerInspectionResponseV01;
      };
      "400": {
        "application/json": IdkmeshApiErrorV01;
      };
      "403": {
        "application/json": IdkmeshApiErrorV01;
      };
      "406": {
        "application/json": IdkmeshApiErrorV01;
      };
      "413": {
        "application/json": IdkmeshApiErrorV01;
      };
      "415": {
        "application/json": IdkmeshApiErrorV01;
      };
    };
  };
  /** List durable Product Spine runs */
  "GET /api/v1/runs": {
    queryParameters: { cursor?: string; limit?: number; project_id?: string; state?: string; };
    responses: {
      "200": {
        "application/json": IdkmeshListV01;
      };
      "400": {
        "application/json": IdkmeshApiErrorV01;
      };
      "403": {
        "application/json": IdkmeshApiErrorV01;
      };
      "503": {
        "application/json": IdkmeshApiErrorV01;
      };
    };
  };
  /** Read one durable Product Spine run's current state */
  "GET /api/v1/runs/{run_id}": {
    pathParameters: { run_id: string; };
    responses: {
      "200": {
        "application/json": IdkmeshControlTowerRunResponseV01;
      };
      "403": {
        "application/json": IdkmeshApiErrorV01;
      };
      "404": {
        "application/json": IdkmeshApiErrorV01;
      };
      "503": {
        "application/json": IdkmeshApiErrorV01;
      };
    };
  };
  /** Read one run's worker/verifier attempts */
  "GET /api/v1/runs/{run_id}/attempts": {
    pathParameters: { run_id: string; };
    responses: {
      "200": {
        "application/json": IdkmeshControlTowerRunAttemptsResponseV01;
      };
      "403": {
        "application/json": IdkmeshApiErrorV01;
      };
      "404": {
        "application/json": IdkmeshApiErrorV01;
      };
      "503": {
        "application/json": IdkmeshApiErrorV01;
      };
    };
  };
  /** Read one run's retained evidence references */
  "GET /api/v1/runs/{run_id}/evidence": {
    pathParameters: { run_id: string; };
    responses: {
      "200": {
        "application/json": IdkmeshControlTowerRunEvidenceResponseV01;
      };
      "403": {
        "application/json": IdkmeshApiErrorV01;
      };
      "404": {
        "application/json": IdkmeshApiErrorV01;
      };
      "503": {
        "application/json": IdkmeshApiErrorV01;
      };
    };
  };
  /** Discover API capabilities and authority limits */
  "GET /api/v1/status": {
    responses: {
      "200": {
        "application/json": IdkmeshControlTowerStatusV01;
        "application/vnd.idkmesh.control-tower.v1+json": IdkmeshControlTowerStatusV01;
      };
      "403": {
        "application/json": IdkmeshApiErrorV01;
      };
    };
  };
  /** List canonical Work Units */
  "GET /api/v1/work-units": {
    responses: {
      "200": {
        "application/json": IdkmeshListV01;
      };
      "400": {
        "application/json": IdkmeshApiErrorV01;
      };
      "403": {
        "application/json": IdkmeshApiErrorV01;
      };
      "503": {
        "application/json": IdkmeshApiErrorV01;
      };
    };
  };
  /** Read one canonical Work Unit */
  "GET /api/v1/work-units/{work_unit_id}": {
    pathParameters: { work_unit_id: string; };
    responses: {
      "200": {
        "application/json": IdkmeshControlTowerWorkUnitResponseV01;
      };
      "403": {
        "application/json": IdkmeshApiErrorV01;
      };
      "404": {
        "application/json": IdkmeshApiErrorV01;
      };
      "503": {
        "application/json": IdkmeshApiErrorV01;
      };
    };
  };
  /** Process liveness probe */
  "GET /healthz": {
    responses: {
      "200": {
        "text/plain": string;
      };
    };
  };
  /** Service readiness probe */
  "GET /readyz": {
    responses: {
      "200": {
        "application/json": IdkmeshReadinessV01;
      };
    };
  };
}

export type IdkmeshApiOperationName = keyof IdkmeshApiOperations;
