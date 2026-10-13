# S3 Verifier Pre-Confirmatory Freeze Toolkit

**Status:** preparation tooling only; no X6/X7 verifier outcome  
**Issue:** [#1080](https://github.com/MSKazemi/idkmesh/issues/1080)  
**Program:** [S3 / Paper A external validity](SCIENTIFIC_PROGRAM.md)  
**Protocol:** [v1 preregistration](VERIFIER_PANEL_EXTERNAL_VALIDITY_PREREG_V1.md), [v1.1 validity amendment](VERIFIER_PANEL_EXTERNAL_VALIDITY_AMENDMENT_V1_1.md), and [v1.2 power-method amendment](VERIFIER_PANEL_EXTERNAL_VALIDITY_AMENDMENT_V1_2.md)

The S3 verifier program now has a deterministic tool for the two things that must
happen before confirmatory verifier execution:

1. derive a calibration-only power plan; and
2. freeze every pre-confirmatory input by content digest.

The implementation is in experiments/s3_verifier_freeze.py.

It does not execute SWE-bench patches, call an LLM, generate verifier verdicts,
validate #804, or update the paper with a result.

## 1. Calibration input contract

The power-plan command accepts JSONL with exactly one record per
(repository_id, task_id, class_label) task/class statistic. Example:

    {"stage":"calibration","repository_id":"django","task_id":"django__django-123","class_label":"official-pass","delta_logscore":0.041}
    {"stage":"calibration","repository_id":"django","task_id":"django__django-123","class_label":"official-fail","delta_logscore":-0.018}

Required fields are exact:

- stage must be calibration; confirmatory rows are rejected;
- repository_id is the source-repository cluster;
- task_id must belong to only one repository;
- class_label is official-pass or official-fail;
- delta_logscore is the task-level per-item-difficulty minus shared-shock
  held-out predictive log-score difference after the frozen producer-lineage
  aggregation.

The power tool does not accept patch-level multiplicity as independent task
evidence. Duplicate/task/provenance handling happens upstream under the v1.1
amendment before these task-level calibration statistics are written.

## 2. Canonical power plan

The canonical design constants are code-level defaults:

| parameter | frozen value |
| --- | ---: |
| smallest effect of interest | log(1.10) nats/item |
| target power | 0.90 |
| simulated cohorts | 10,000 |
| final confirmatory bootstrap replicates per clustering level | 10,000 (recorded, not nested inside power simulation) |
| seed | 20261011 |
| task-count ladder | 50, 75, 100, 150, 200, 300, 500, then full eligible universe |

Example command:

    python experiments/s3_verifier_freeze.py power-plan \
      .cache/s3/calibration-task-logscore.jsonl \
      --eligible-task-count 500 \
      --eligible-repository-count 12 \
      --eligible-pass-items 210 \
      --eligible-fail-items 430 \
      --out .cache/s3/power_plan.json

The tool:

1. centers calibration log-score differences separately within the pass/fail
   strata, removing the observed calibration effect direction;
2. injects only the preregistered smallest effect of interest;
3. resamples empirical repository profiles and their task structure while never creating more repository clusters than the eligible confirmatory universe contains;
4. computes a delete-one-cluster jackknife standard error separately at the
   repository and task levels and applies the two-sided 95% cluster-t critical
   value;
5. counts success only when both planning lower bounds exceed zero;
6. selects the first task count reaching 90% simulated power.

This cluster-t calculation is a **power-planning approximation** registered in
the v1.2 amendment. The final confirmatory result still uses the stricter
10,000-resample percentile bootstrap at both clustering levels.

Smaller simulation counts are allowed for code development, but their output is
marked canonical=false and cannot satisfy the S3 freeze gate. The final
confirmatory bootstrap count is not a development knob in this tool.

Expected scientific outcomes are explicit:

- powered — use the selected task count;
- underpowered_full_universe — retain the full descriptive study, but do not
  claim the positive confirmatory design was adequately powered;
- infeasible — the calibration/eligible universe cannot satisfy the frozen
  repository/class requirements.

No threshold is relaxed to obtain a favorable status.

## 3. Freeze-manifest input

After a canonical power_plan.json exists, prepare a strict input object using
schema idkmesh.s3-freeze-input.v1. The manifest builder parses the bound power
plan again and refuses it unless canonical=true, its self digest is valid, and
its frozen seed, effect size, simulation count, cluster-t planning method,
final confirmatory bootstrap count, and target power still match the current
pre-outcome amendments.

The manifest builder accepts only named pre-confirmatory artifact roles:

- analysis_code;
- power_planning_code;
- power_plan;
- calibration_statistics;
- candidate_inventory;
- verifier_inventory;
- stage_assignment;
- environment_manifest;
- optional prompt_bundle;
- optional sandbox_attestation.

An X7 freeze requires prompt_bundle plus metadata for at least three base-model
lineages. A model marked as benchmark-specifically fine-tuned is rejected from
the primary independent-family freeze.

The bound calibration_statistics file must hash to the calibration_sha256
recorded inside the canonical power plan; a mismatch fails closed. The freeze
input also records the pinned repository commit, upstream benchmark commit and
artifact digests, bootstrap/permutation/stage-assignment seeds,
execution boundary, model/checkpoint metadata, contamination status, and an
optional container image digest.

Build and validate:

    python experiments/s3_verifier_freeze.py freeze-manifest \
      .cache/s3/freeze-input.json \
      --root . \
      --out .cache/s3/freeze-manifest.json

    python experiments/s3_verifier_freeze.py validate \
      .cache/s3/freeze-manifest.json

Output files are never overwritten. Every bound file records its byte size and
SHA-256 digest. The manifest itself has a self_sha256 over canonical JSON with
that field omitted, so the freeze can be checked without timestamps or network
access.

## 4. Security and evidence boundaries

This tool is deliberately incapable of satisfying #804.

- claims.executes_untrusted_code is always false.
- No confirmatory verdict-matrix artifact role exists.
- Unknown artifact roles fail closed.
- JSON/JSONL metadata roles are recursively checked for verdict/vote/model-output
  keys so outcome material cannot be accidentally relabeled as an inventory.
- Source-code roles must bind Python files; metadata roles must bind JSON/JSONL.
- The power-plan role must bind a valid canonical plan; development plans and
  infeasible plans cannot authorize an experiment freeze.
- The exact calibration-statistics artifact is mandatory and its digest must
  equal the digest inside that power plan.
- Artifact paths cannot escape the requested root or be symlinks.
- An execution boundary that says untrusted patches will run while the sandbox
  is not required is rejected.
- The manifest records #804 as the canonical sandbox issue but does not claim
  that issue is resolved.
- Official benchmark pass/fail labels remain operational execution labels, not
  semantic proof of program correctness.

X6 remains blocked on the hostile-code sandbox. X7 can freeze text-only judge
inputs without executing patches, but local recomputation of official labels
inherits the same #804 boundary.

## 5. What this closes and what it does not

This closes the mechanical pre-outcome freeze gap identified in #1023:

- power settings are executable rather than prose-only;
- development runs cannot masquerade as canonical power evidence;
- the result can be powered, underpowered, or infeasible;
- analysis, data, stage assignment, verifier inventory, prompts/models and
  environment are content-addressed before confirmatory work.

It does not close Paper A's external-validity gap. That requires the retained
X6 and independent-family X7/X10 evidence defined by the preregistration.
