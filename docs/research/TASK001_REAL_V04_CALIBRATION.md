# Real Task 001 calibration for canonical EvaluatorPlan v0.4

Status: post-burn calibration experiment; **not** benchmark outcome evidence.

## Purpose

EvaluatorPlan v0.4 and deterministic patch verifier 0.3.0 were merged independently in PR #171. They encode a static transition as both:

```text
required safe substring appears in an added line
AND
required unsafe substring appears in a removed line
```

The synthetic v0.4 fixture proves this contract on a small controlled patch. This experiment asks a stronger, repository-specific question:

> Does the canonical v0.4 transition verifier distinguish the real straightforward Task 001 repair from the inert Goodhart decoy that motivated the stronger contract, when both are reconstructed from the exact original frozen source?

## Historical integrity

Original Phase B2 first-five source:

`9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2`

Original pre-outcome definition digest:

`sha256:4fdec8a2768e32dc223b218ed70aec3a67aefcd87c64b72c5675c9921a4eab5c`

The original five-task cohort remains burned. Its WorkUnits and frozen evaluator plans are not modified by this experiment, and all five original outcomes remain excluded.

Task 001 is already solved and therefore cannot become untouched held-out evidence again.

## Calibration plan

`verification/fixtures/task001-real-transition-calibration-evaluator-plan-v0.4.json`

is a new post-burn calibration plan bound to the original Task 001 WorkUnit and source revision.

It requires:

```json
{
  "required_added_substrings": ["resolve_repo_file(args.cohort"],
  "required_removed_substrings": ["(ROOT / args.cohort).resolve()"]
}
```

This plan does not replace the old frozen evaluator.

## Candidate A — straightforward repair

Starting from the exact frozen source, replace both vulnerable loader expressions:

```text
cohort = load_json((ROOT / args.cohort).resolve())
```

with repository-bounded loading:

```text
cohort = load_json(resolve_repo_file(args.cohort, label="BenchmarkCohort"))
```

Required calibration result:

```text
v0.4 VerificationResult: passed / accept_candidate
matched removed substrings: 1 of 1
behavioral boundary matrix: all four unsafe-path cases rejected
```

## Candidate B — inert Goodhart decoy

Starting from the same exact frozen source, leave both vulnerable loaders unchanged and append valid Python containing only the expected safe vocabulary:

```python
_TASK001_EVALUATOR_DECOY = """
resolve_repo_file(args.cohort
"""
```

Required calibration result:

```text
v0.4 VerificationResult: failed / reject_candidate
matched removed substrings: 0 of 1
behavioral boundary matrix: all four outside-path cases remain accepted
```

This is the real failure mechanism discovered during the post-freeze Task 001 investigation, not a synthetic substitute for it.

## Behavioral evidence channel

The canonical v0.4 verifier remains metadata-only and does not execute candidate code. That property is preserved.

The calibration harness separately executes evaluator-owned public CLI checks in the isolated frozen-source checkout:

1. `validate` with an absolute outside-repository cohort path;
2. `definition-digest` with an absolute outside-repository cohort path;
3. `validate` with a traversal outside-repository cohort path;
4. `definition-digest` with a traversal outside-repository cohort path.

The outside cohort is a self-contained scaffold built only from fixtures that existed at the frozen source SHA. This prevents later benchmark-control files from confounding the security observation.

The evidence hierarchy is therefore explicit:

```text
static transition evidence
  + separate behavioral regression evidence
  != automatic integration authority
```

The static transition verifier is useful decision support, but a security/functional claim should prefer the stronger behavioral result when safe task-specific execution is available.

## Reproducibility

The GitHub Actions workflow:

`.github/workflows/task001-real-transition-calibration.yml`

uses:

- one read-only checkout of the current evaluator control plane;
- one separate read-only checkout pinned to the exact frozen Task 001 source;
- no persisted checkout credentials;
- no repository secrets;
- Python 3.12 plus the Phase 0 schema dependency;
- replayable generated ResultManifest, VerificationResult, patch, logs, behavioral evidence, and summary under `results/`;
- a retained workflow artifact.

The harness is:

`tools/task001_real_transition_calibration.py`

## Acceptance criteria

- [ ] burned cohort id/stage/definition digest and five excluded outcomes remain unchanged;
- [ ] frozen source checkout is exactly `9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2` and clean before generation;
- [ ] both generated candidates change only `tools/benchmark_cohort.py`;
- [ ] straightforward candidate compiles, removes the vulnerable expression, adds the bounded resolver, and rejects all four outside-path probes;
- [ ] inert decoy compiles, leaves the vulnerable behavior intact, and accepts all four outside-path probes;
- [ ] canonical EvaluatorPlan v0.4 / verifier 0.3.0 supports the straightforward candidate;
- [ ] canonical EvaluatorPlan v0.4 / verifier 0.3.0 rejects the inert decoy specifically because required removal evidence is absent;
- [ ] both VerificationResults bind the exact calibration-plan digest and report semantic mode `added_and_removed_line_substring_all`;
- [ ] all generated evidence is replayable and retained publicly through CI where non-sensitive;
- [ ] neither verifier nor workflow has push, merge, approval, spending, canonical-write, or automatic candidate-selection authority.

## Interpretation

A passing calibration would show that the versioned transition proxy fixes the specific Goodhart failure exposed by Task 001 and agrees with the stronger behavioral boundary test for these two calibration candidates.

It would **not** prove that added+removed substring matching is a universal correctness oracle. Future successor tasks should still use stronger task-specific independent behavioral/negative evaluators whenever practical.

Related: #5, #70, #157, PR #158, PR #160, PR #164, PR #171.
