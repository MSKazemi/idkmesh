---
title: "Tutorial: Run the Local Two-Attempt Loop"
description: "Run idkmesh local-loop on two committed examples, read the evidence bundle, replay the saved run, and record a human decision. Nothing is selected, pushed, or merged."
---
# Tutorial: run the local two-attempt loop

This walkthrough runs one bounded WorkUnit through the checkout-only
`idkmesh local-loop` command: two attempts, independent verification of each,
and one non-selecting evidence report. You then replay the saved run and record
a human decision with two repository scripts. Every command below was run from
a repository checkout on current `main`, and the output shown is copied from
that session (paths shortened only where noted).

Read [What this does and does not show](#what-this-does-and-does-not-show)
before you rely on any of it: the attempts are **precollected fixtures**, not
live workers.

## Prerequisites

- Python 3.11 or 3.13 (see [`../CONTRIBUTING.md`](https://github.com/MSKazemi/idkmesh/blob/main/CONTRIBUTING.md) for the
  environment setup used by the project);
- a clone of this repository, with every command run from the repository root,
  because `local-loop` reads the example configs and the `experiments/` scripts
  from the checkout and is not shipped in the wheel;
- the CLI plus the optional schema-verifier dependency:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[verify]'
```

(`python -m idkmesh.cli` works everywhere `idkmesh` does. The `[verify]` extra
installs `jsonschema`; see
[`decisions/ADR-0012-optional-verification-dependency.md`](decisions/ADR-0012-optional-verification-dependency.md).)

## Step 1 — find the command

```bash
idkmesh --help
```

The command list ends with `local-loop`, described as running a bounded
WorkUnit through the local product loop. Its own help lists the two arguments
this tutorial uses:

```bash
idkmesh local-loop --help
```

`CONFIG` is a repository-relative two-attempt orchestration config, and
`--output-dir` is a repository-relative directory under `results/` that must not
already exist non-empty (`results/` is Git-ignored, so nothing here can be
committed by accident).

## Step 2 — a supported attempt beside a rejected one

The first config binds one WorkUnit and one verifier-owned EvaluatorPlan to two
precollected patch candidates, a good one and a semantically wrong one.

```bash
idkmesh local-loop \
  examples/orchestration/two-attempt-evaluator-plan-good-vs-bad.json \
  --output-dir results/local-loop-tutorial-evaluator-plan
```

```text
# idkmesh local-loop: two-attempt-evaluator-plan-good-vs-bad

WorkUnit `verification/patch-smoke` v1 -> 2 isolated attempt(s) -> independent verification -> evidence report.

- Supported: 1
- Rejected: 1
- Inconclusive: 0
- Control errors: 0
- Verification disagreement: yes

## Evidence bundle

- Evidence report (human-readable): `results/local-loop-tutorial-evaluator-plan/evidence-report.md`
- Evidence report (machine-readable): `results/local-loop-tutorial-evaluator-plan/evidence-report.json`
- Run record: `results/local-loop-tutorial-evaluator-plan/run-record.json`
- Replay manifest: `results/local-loop-tutorial-evaluator-plan/replay-source.json`
- Raw VerificationResult: `results/local-loop-tutorial-evaluator-plan/verification-result-attempt-001.json`
- Raw VerificationResult: `results/local-loop-tutorial-evaluator-plan/verification-result-attempt-002.json`
```

The command exits `0`: **exit status reports that the loop ran, not that every
candidate passed.** One attempt is supported and one is rejected, and the
summary says plainly that the two verification recommendations disagree. The
real output continues with a Warnings section and the two manual next steps
that Steps 5 and 6 below carry out.

## Step 3 — read the evidence bundle

```bash
ls results/local-loop-tutorial-evaluator-plan
```

```text
evidence-report.json
evidence-report.md
NEXT_STEPS.md
replay-source.json
run-record.json
verification-result-attempt-001.json
verification-result-attempt-002.json
```

| File | What it holds |
| --- | --- |
| `run-record.json` | The orchestration record: per-attempt state, a projection of each worker ResultManifest, and a projection of each verification. Its `authority` block has `automatic_candidate_selection`, `canonical_state_write`, `git_push` and `merge` all `false`. |
| `verification-result-attempt-001.json`, `verification-result-attempt-002.json` | The raw, unprojected VerificationResult for each attempt that reached verification, including its checks, evidence, and `decision_support` recommendation. |
| `evidence-report.md`, `evidence-report.json` | One combined, **non-selecting** report of the same evidence, for people and for tools. |
| `replay-source.json` | A manifest naming the config and the saved files, so a replay does not need the original command line. |
| `NEXT_STEPS.md` | The same two human-gated next steps the command printed. |

Open `evidence-report.md`. Its attempts table is the quickest summary:

```text
| Attempt | Worker state | Worker | Verifier | Recommendation | Evidence state | Required checks |
| --- | --- | --- | --- | --- | --- | --- |
| attempt-001 | verified | fixture/patch-worker | idkmesh-local-verifier | accept_candidate | supported | result-manifest-schema=passed, independent-review=passed |
| attempt-002 | verified | fixture/patch-worker | idkmesh-local-verifier | reject_candidate | rejected | result-manifest-schema=passed, independent-review=failed |
```

Look at `attempt-002`: its worker state is `verified` (the worker finished and
produced a well-formed ResultManifest), but the independent check failed, so
the evidence state is `rejected`. A worker reporting success is not the same as
the candidate being acceptable. The report also states
`Human integration decision: pending` and contains no selected candidate.

## Step 4 — a failed worker beside a healthy peer

The second config makes one attempt end in a simulated worker failure before any
ResultManifest exists.

```bash
idkmesh local-loop examples/orchestration/two-attempt-worker-failure.json \
  --output-dir results/local-loop-tutorial-worker-failure
```

```text
# idkmesh local-loop: orchestration/two-attempt-worker-failure

WorkUnit `verification/local-smoke` v1 -> 2 isolated attempt(s) -> independent verification -> evidence report.

- Supported: 1
- Rejected: 0
- Inconclusive: 0
- Control errors: 1
- Verification disagreement: no
```

The exit status is again `0`. The worker failure is counted as a **control
error**, kept separate from a rejection: the failed attempt produced nothing to
reject. Its row in `evidence-report.md` reads `worker_error` and is followed by
the simulated error text, the healthy peer is still verified and `supported`, and
only `verification-result-attempt-001.json` is written because attempt 2 never
reached verification.

## Step 5 — replay the saved run

`replay_run.py` is a repository script, not an `idkmesh` subcommand. It re-runs
the exact config recorded in `replay-source.json` against the same fixtures and
compares the result with the saved bundle.

```bash
python experiments/replay_run.py replay \
  --bundle results/local-loop-tutorial-evaluator-plan/replay-source.json
```

```text
replay of run_id='two-attempt-evaluator-plan-good-vs-bad' (config=examples/orchestration/two-attempt-evaluator-plan-good-vs-bad.json)
  [OK] run-record
  [OK] evidence-report
  [OK] verification-result[attempt-001]
    (5 expected-to-vary field(s) present and not compared: ...)
  [OK] verification-result[attempt-002]
    (5 expected-to-vary field(s) present and not compared: ...)
PASS: replay reproduced every must-match field
```

(The two `expected-to-vary` lines are shortened here with `...`; the real output lists the
exact fields, such as timestamps and the interpreter platform string, that a raw
VerificationResult legitimately changes from run to run.) The script exits `0`
on `PASS` and non-zero with an itemized diff if any must-match field diverges.
`python experiments/replay_run.py replay --help` documents the argument.

## Step 6 — record a human decision

The loop never records an integration decision. A person does that with a
second repository script, against the evidence report:

```bash
python experiments/record_human_decision.py record \
  --evidence-report results/local-loop-tutorial-evaluator-plan/evidence-report.json \
  --output results/local-loop-tutorial-evaluator-plan/human-decision-record.json \
  --decision-id two-attempt-evaluator-plan-good-vs-bad.decision.001 \
  --decision accept \
  --selected-attempt-id attempt-001 \
  --rationale "attempt-001 was supported and attempt-002 was rejected by the verifier." \
  --decider-id tutorial-reader
```

```text
recorded accept decision 'two-attempt-evaluator-plan-good-vs-bad.decision.001' for run 'two-attempt-evaluator-plan-good-vs-bad' (evidence_report_digest=sha256:...)
```

`--decision` takes `accept`, `reject`, or `escalate`; `--selected-attempt-id`
is optional (omit it for a run-level decision). The new
`human-decision-record.json` binds the decision to the digest of the evidence
report, names the decider, and carries an `authority` block with
`canonical_state_write`, `git_push` and `merge` all `false`. **Recording a
decision does not integrate anything.** Merging is a separate step governed by
the repository's normal pull request and review policy.

## What this does and does not show

- **Precollected fixtures, not live workers.** The first config uses the
  `result-bundle` worker adapter, which only collects ResultManifest bundles
  that already exist under `examples/`. The second uses the `fixture-result` and
  `fixture-failure` adapters, which replay committed fixtures and a simulated
  failure. No model, agent, or external service is invoked, and no candidate is
  produced by this command.
- **Not hostile-code isolation.** "Isolated attempts" means separate records and
  verification paths, not a sandbox. The local sandbox backend that would make
  running untrusted worker code safe is tracked in
  [issue #804](https://github.com/MSKazemi/idkmesh/issues/804) and is still
  open; see the
  [local agent execution boundary](specifications/LOCAL_AGENT_EXECUTION_BOUNDARY_V0_1.md).
  Do not point `local-loop` at code you would not run yourself.
- **Replay and the human decision are scripts.** Neither `replay_run.py` nor
  `record_human_decision.py` is an `idkmesh` subcommand, and `local-loop` runs
  neither on your behalf.
- **No automatic authority.** Automatic candidate selection, canonical-state
  write, Git push, and merge are all `false` in every file the loop writes. The
  report is decision support; worker success is not acceptance, and a
  verification recommendation is not merge authority.
- **Verification here is the repository's own local verifier** on committed
  fixtures. It demonstrates the structure of the evidence, not that any
  real-world agent output would pass or fail.

## Cleanup

```bash
rm -rf results/local-loop-tutorial-evaluator-plan results/local-loop-tutorial-worker-failure
```

## Where to go next

- [`reference/CLI_HTTP_QUICK_REFERENCE.md`](reference/CLI_HTTP_QUICK_REFERENCE.md) —
  the shipped command surface, including the `local-loop` row.
- [`RUN_LIFECYCLE_TUTORIAL.md`](RUN_LIFECYCLE_TUTORIAL.md) — the separate
  `idkmesh run` bookkeeping commands and the read-only Control Tower API.
- [`specifications/LOCAL_AGENT_EXECUTION_BOUNDARY_V0_1.md`](specifications/LOCAL_AGENT_EXECUTION_BOUNDARY_V0_1.md) —
  what local execution would have to enforce before worker code could run safely.
- [`GETTING_STARTED.md`](GETTING_STARTED.md) — the other newcomer paths.
