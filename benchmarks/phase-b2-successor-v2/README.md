# Phase B2 successor first-five v2 — scaffold

Status: **mutable, unfrozen calibration corpus** tracked by issue #180.

The required post-calibration novelty audit failed for all five tasks because
the committed calibration programs publicly reconstruct their accepted
straightforward repairs. See the
[pre-freeze novelty audit](../../docs/research/PHASE_B2_V2_PRE_FREEZE_NOVELTY_AUDIT.md).
Do not freeze this scaffold or use it for solution-unseen scored outcomes. The
`freeze_ready=true` bookkeeping value records calibration completion only.

Source snapshot for all five tasks:

`a69aa0ae1ae4862e507511cbd9ad854237d0ad32`

This directory is deliberately **not frozen** yet. `cohort.json` has `stage=scaffold`, `taxonomy_frozen_before_outcomes=false`, and no `definition_digest`.

## Why this is a scaffold

The original first-five pilot was burned after a real solution exposed a defective frozen evaluator. The successor therefore separates four stages:

```text
task hypothesis
 -> bounded WorkUnit + provisional EvaluatorPlan
 -> straightforward-vs-near-miss calibration
 -> task-specific behavioral regression where safe
 -> only then freeze definition digest
 -> only after freeze generate scored candidates
```

A green static transition proxy is not enough to freeze a task. Each evaluator must distinguish a legitimate reference transition from an inert/Goodhart near-miss. When the task admits a safe evaluator-owned behavioral regression, that behavioral channel must agree with the static proxy.

## Five new tasks

| ID | Family | Surface | Pre-freeze defect hypothesis |
| --- | --- | --- | --- |
| V2-001 | `bug_fix` | `tools/benchmark_cohort.py` | direct in-repo symlink references may evade the stated symlink ban because the path is resolved before `is_symlink()` |
| V2-002 | `test_failure` | `experiments/free_compute_router.py` | Python non-standard `NaN`/Infinity values may evade finite cost/probability/resource policy decisions |
| V2-003 | `bounded_feature` | `tools/branch_convergence_audit.py` | missing current head SHA may be treated as matching merged-PR evidence, making cleanup appear safer than observed evidence supports |
| V2-004 | `benchmark` | `experiments/verification_backpressure.py` | non-finite controller inputs can poison debt/priority/fan-out arithmetic where guards use inequalities only |
| V2-005 | `security` | `experiments/local_compute_offer.py` | discovery-only CLI can write arbitrary `--output` paths, contradicting the no-canonical-write authority boundary |

These are **hypotheses to calibrate**, not completed benchmark outcomes.

## Evaluator status

The five public EvaluatorPlan v0.4 files are provisional transition proxies. They bind exact source + WorkUnit digests but may be revised **before freeze** if calibration finds a false positive/negative. Any such change must update this scaffold index and its plan digest. After freeze, the plans may not be silently changed.

## Freeze checklist

Do not set `stage=frozen` or add `definition_digest` until all five tasks satisfy:

- WorkUnit and evaluator schema validation;
- straightforward reference transition supported;
- inert/Goodhart near-miss rejected;
- safe task-specific behavioral negative regression agrees where practical;
- exact source/WorkUnit/EvaluatorPlan provenance retained;
- calibration candidates clearly marked non-benchmark evidence;
- no worker/verifier authority for canonical writes, push, approval, merge, spending, or automatic candidate selection;
- no reuse of burned-v1 tasks as untouched held-out evidence.

Once these are green, compute the pre-outcome definition digest and freeze the cohort **before** generating scored candidate attempts.

This five-task v2 cohort is an engineering bootstrap, not a statistical-power claim and not a substitute for the larger real corpus required by issue #70.
