# EvaluatorPlan v0.4 calibrated transformation semantics

Status: experimental P0 calibration contract for issue #157.

## Motivation

The burned Phase B2 first-five pilot and diagnostic PR #158 revealed two different failures of a lexical proxy:

1. **false negative** — the correct Task 001 patch contains the intended resolver fragment inside a complete Python line, but v0.2 exact-line matching rejects it;
2. **false positive** — an inert multiline string can contain the expected text while leaving both vulnerable direct path loaders unchanged.

EvaluatorPlan v0.3 fixes the first ambiguity by making added-line substring semantics explicit. It intentionally does **not** claim that added substring presence is sufficient correctness evidence.

EvaluatorPlan v0.4 adds a second metadata-only transformation requirement:

- required semantic evidence in **added** lines; and
- required vulnerable/obsolete evidence in **removed** lines.

Historical v0.2 and v0.3 meanings remain unchanged.

## Version matrix

| Plan | Verifier | Added requirement | Removed requirement | Intended evidence strength |
| --- | --- | --- | --- | --- |
| v0.2 | 0.1.1 | exact full line | none | lexical proxy |
| v0.3 | 0.2.0 | line substring | none | explicit lexical semantic marker |
| v0.4 | 0.3.0 | line substring | line substring | calibrated patch-transformation proxy |

The canonical `experiments/evaluator_plan_runner.py` routes every version by schema version. No old plan is reinterpreted under a new meaning.

## Formal v0.4 condition

Let `A` be the added lines and `R` the removed lines parsed from structurally valid unified-diff hunks.

For required added substrings `S_A` and required removed substrings `S_R`:

```text
added_pass   = AND_s in S_A  exists L in A : s is a contiguous case-sensitive substring of L
removed_pass = AND_s in S_R  exists L in R : s is a contiguous case-sensitive substring of L
semantic_pass = added_pass AND removed_pass
```

Matching is:

- case-sensitive;
- contiguous;
- line-local;
- not regex;
- not fuzzy;
- not cross-line.

Candidate code is never executed by this verifier.

## Why removed evidence matters

Task 001's inert decoy adds the text:

```text
resolve_repo_file(args.cohort
```

inside a harmless multiline string. That satisfies an added-text proxy while leaving the vulnerable form:

```text
(ROOT / args.cohort).resolve()
```

in place.

The calibrated v0.4 plan therefore requires both:

```json
"required_added_substrings": ["resolve_repo_file(args.cohort"],
"required_removed_substrings": ["(ROOT / args.cohort).resolve()"]
```

The straightforward fix removes the vulnerable form and adds the resolver call. The inert decoy adds the marker but removes nothing, so it must fail.

## Evidence-strength boundary

v0.4 is still a **patch-transformation proxy**, not proof of runtime security or correctness.

When a safe task-specific behavioral regression exists, stronger evidence must remain separate and should be required before making a behavioral claim.

For Task 001 the calibration channel executes evaluator-owned public CLI checks in an isolated checkout:

- `validate` with an absolute cohort path;
- `definition-digest` with an absolute cohort path;
- `validate` with traversal;
- `definition-digest` with traversal.

Expected calibration:

```text
straightforward fix:
  v0.4 metadata verification -> support
  behavioral matrix          -> all unsafe paths rejected

inert decoy:
  v0.4 metadata verification -> reject
  behavioral matrix          -> vulnerable paths still accepted
```

The behavioral execution is performed by `tools/task001_evaluator_calibration_v04.py`, not by the metadata-only verifier. This distinction is recorded in the calibration summary and VerificationResult extensions.

## Provenance

A v0.4 VerificationResult must record:

- `deterministic-patch-verifier` adapter version `0.3.0`;
- exact EvaluatorPlan v0.4 canonical digest after runner binding;
- added substring semantic evidence from the v0.3 core;
- removed substring semantic evidence;
- semantic mode `added_and_removed_line_substring_all`;
- added-substring core version `0.2.0`;
- legacy structural/provenance/log/scope core version `0.1.1`;
- `behavioral_correctness_claim=false` for the metadata-only verifier.

## Calibration object

`verification/fixtures/task001-transformation-calibration-evaluator-plan-v0.4.json` is a **post-burn calibration plan** bound to the original Task 001 WorkUnit/source. It is not a replacement for the frozen v0.2 evaluator and must not be substituted into the burned cohort retroactively.

The calibration workflow checks out the exact old source separately and generates both candidates after the burn. These are calibration objects, not benchmark outcomes.

## Successor-cohort gate

Do not freeze the Phase B2 successor until:

1. v0.2 regression remains green;
2. v0.3 semantic-version contrast remains green;
3. v0.4 straightforward-vs-decoy calibration is green;
4. the stronger behavioral evidence boundary is documented;
5. the cohort validator can bind the selected newer EvaluatorPlan version without weakening digest/provenance checks;
6. task 001 is not represented as untouched held-out evidence.

## Authority boundary

No evaluator version grants:

- canonical-state writes;
- push authority;
- PR approval;
- merge authority;
- automatic candidate selection;
- spending authority.

Verifier recommendations remain evidence for later integration/human governance.

Related: #157, PR #158, PR #164, `benchmarks/phase-b2-first-five/BURN_NOTICE.md`.
