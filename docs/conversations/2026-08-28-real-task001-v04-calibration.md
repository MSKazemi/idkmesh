# Conversation record — real Task 001 v0.4 calibration

Date: 2026-08-28

Repository: `MSKazemi/idkmesh`

## User direction

The user asked the project to continue development of the public IDKMesh repository.

## Starting point

The original Phase B2 first-five pilot had already been burned because its frozen v0.2 evaluator plans used semantic fragments where deterministic patch verifier v0.1.1 required exact full added-line equality.

Task 001 itself was solved as real repository work in PR #153. The burned pilot kept:

- source revision `9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2`;
- original definition digest `sha256:4fdec8a2768e32dc223b218ed70aec3a67aefcd87c64b72c5675c9921a4eab5c`;
- original WorkUnits and frozen evaluator plans;
- all five original task outcomes excluded.

PR #164 then introduced EvaluatorPlan v0.3 / verifier 0.2.0 added-line substring semantics without changing v0.2 / verifier 0.1.1 exact-line meaning.

## Stronger adversarial evidence

Closed diagnostic PR #158 preserved a more important calibration fact:

- a straightforward Task 001 repair fixes the repository boundary but is rejected by the old exact-line frozen evaluator;
- an inert valid-Python decoy can contain the expected resolver fragment while leaving both vulnerable direct loaders unchanged;
- the weak lexical evaluator can support that decoy even though the outside-repository path behavior remains vulnerable.

Issue #157 was therefore reopened. Added-substring presence alone could not be treated as sufficient evidence for the successor security task.

## Parallel v0.4 development and convergence

During this continuation, an experimental PR #170 was created to introduce an added+removed transformation contract and calibrate it against the real Task 001 source.

The real calibration was eventually made scientifically clean by separating:

1. current evaluator/control-plane integrity;
2. exact frozen-source candidate generation;
3. metadata-only transition verification;
4. independent behavioral boundary execution.

A successful experimental run on #170 (`33194220134`) established the intended real matrix:

```text
straightforward fix:
  transition verifier -> passed / accept_candidate
  outside-path behavior -> all four cases rejected

inert decoy:
  transition verifier -> failed / reject_candidate
  outside-path behavior -> all four cases accepted
```

That successful run also retained replayable generated evidence as a workflow artifact.

Before #170 could be integrated, concurrent PR #171 independently merged the same core idea in a cleaner canonical implementation:

```text
EvaluatorPlan v0.4
 -> deterministic-patch-verifier 0.3.0
 -> required added-line substrings
 + required removed-line substrings
```

PR #171 merged as `c60549c43232231c724fe3aaaac1f08a26998cbe` and included synthetic correct-vs-Goodhart calibration fixtures, version-preserving routing, Phase 0 tests, and explicit language that v0.4 remains a static proxy rather than behavioral proof.

The correct convergence decision was therefore **not** to merge #170 wholesale. Its duplicate schema/verifier/runner implementation was superseded by #171.

## Unique evidence extracted onto current main

A new branch was created from current `main`:

`experiment/task001-v04-real-calibration`

It reuses the canonical v0.4 implementation from #171 and adds only the stronger repository-specific calibration layer.

### Bound calibration plan

`verification/fixtures/task001-real-transition-calibration-evaluator-plan-v0.4.json`

is a new post-burn calibration object bound to the original Task 001 WorkUnit/source. It requires:

```text
added substring:   resolve_repo_file(args.cohort
removed substring: (ROOT / args.cohort).resolve()
```

It does not replace or mutate the old frozen evaluator.

### Calibration harness

`tools/task001_real_transition_calibration.py`

performs the following:

1. verifies the current first-five cohort is still burned with the original definition digest and five excluded outcomes;
2. resets a separate source checkout to exact SHA `9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2`;
3. generates a straightforward repair and an inert multiline-string decoy independently from that exact source;
4. compiles both candidates and verifies they modify only `tools/benchmark_cohort.py`;
5. creates schema-valid ResultManifest v0.1 records and candidate patch/log bundles;
6. runs the canonical current EvaluatorPlan v0.4 / transition verifier 0.3.0;
7. runs a separate evaluator-owned behavioral boundary matrix over the isolated frozen source;
8. requires the straightforward repair to pass transition verification and reject all unsafe paths;
9. requires the decoy to fail transition verification because no required unsafe line was removed and to remain behaviorally vulnerable;
10. writes replayable generated evidence under `results/`.

The outside-path cohort fixture is deliberately self-contained from files that existed at the frozen source SHA. This avoids a confounder where an escaped path might return nonzero only because later benchmark-control files did not yet exist in the old checkout.

### CI

`.github/workflows/task001-real-transition-calibration.yml`

uses two separate read-only checkouts:

- current evaluator/control plane;
- exact frozen Task 001 source.

It persists no checkout credentials, uses no repository secrets, publishes the calibration summary, and retains generated evidence as an artifact.

### Research record

`docs/research/TASK001_REAL_V04_CALIBRATION.md`

makes the evidence hierarchy explicit:

```text
static added+removed transition proxy
 + separate task-specific behavioral evidence
 != automatic correctness oracle
 != automatic integration authority
```

## Expected final evidence

The clean branch must reproduce the real matrix using the canonical merged v0.4 verifier:

```text
straightforward:
  verifier 0.3.0 -> passed / accept_candidate
  removed match  -> 1/1
  behavior       -> all four unsafe paths rejected

decoy:
  verifier 0.3.0 -> failed / reject_candidate
  removed match  -> 0/1
  behavior       -> all four vulnerable outside paths accepted
```

Both VerificationResults must bind the exact new calibration-plan digest and semantic mode `added_and_removed_line_substring_all`.

## Next gate after clean calibration

The Benchmark Cohort validator had independently been made schema-version-aware for EvaluatorPlan v0.2 and v0.3. After the real v0.4 calibration is green, the next bounded infrastructure step is to teach Benchmark Cohort v0.1 to validate/index public EvaluatorPlan v0.4 without weakening exact digest/provenance checks.

Only after that should a **new successor Phase B2 cohort** be frozen. Task 001 is already known and must not be represented as untouched held-out evidence.

## Authority boundary

No work in this continuation grants:

- canonical-state write authority to workers/verifiers;
- Git push authority;
- PR approval or merge authority;
- automatic candidate selection;
- secret access;
- project-paid compute/spending authority.

The real calibration candidates are post-burn experiment objects, not benchmark outcomes.
