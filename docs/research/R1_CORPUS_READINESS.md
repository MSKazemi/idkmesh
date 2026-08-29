# R1 Real-Corpus Readiness Gate

**Issues:** 30, 70

**Evidence status:** contract/readiness tooling only; no real R1 outcome

## Why this gate exists

`randomness_lab.r1_replay` is intentionally frozen before the first real
held-out outcome. The repository also has a BenchmarkCohort contract that
binds tasks, evaluators, attempts, and predeclared structural signatures.
Neither component alone rejects every way an incomplete pilot could be fed to
the replay and described as a real R1 result.

`randomness_lab.r1_readiness` bridges that boundary without modifying the
replay algorithm. It checks that a validated BenchmarkCohort has:

- a frozen or burned definition with a committed digest;
- a prospective minimum of at least 20 work units by default;
- held-out, verified coding WorkUnit evidence;
- the exact equal-selection-budget signature layout used by the replay;
- conclusive replay normalization for every attached attempt;
- agreement between the cohort signature and the signature the replay reads;
- independent test outcomes;
- predeclared and measured wall, compute, and human-attention cost fields;
- verified seeded-negative evidence for every eligible work unit;
- no selection, state-write, push, or merge authority.

Every verified or attempt-bearing task must pass all task-level gates. Reaching
20 eligible tasks does not mask an additional ineligible analyzed task, because
the unchanged replay would still consume that task. Pending or excluded tasks
with no attached attempts may remain in the cohort as retained corpus history.

For the default `swarm_size = 2`, the expected retained candidate pool per
work unit is two attempts from the replication baseline and one attempt from a
second signature. The replay samples two candidates for both comparisons:
`A + A` for replication and `A + B` for structural diversity.

This is stricter than merely finding two signature labels in a report. Extra
or missing *attached* attempts block readiness because they can make the primary
candidate pool depend on post-outcome selection.

There is an important limit: the BenchmarkCohort `definition_digest` excludes
evidence and attempts so results can be attached after the task/evaluator
definition is frozen. Exact attached counts therefore cannot prove that no
generated attempt was omitted. Prospective attempt commitments plus collection
provenance must establish that separately; this audit only checks the evidence
that is present.

## Run the current repository-state audit

```bash
python -m randomness_lab.r1_readiness \
  --cohort benchmarks/phase-b2-successor-v2/cohort.json \
  --baseline-signature single-worker-baseline-v2 \
  --diversity-signature single-worker-baseline-v2 \
  --diversity-signature role-specialized-two-attempts-v2 \
  --output /tmp/r1-readiness.json
```

Add `--require-ready` when a data-collection workflow must stop unless every
gate passes. A blocked audit is otherwise successful command output so the
repository can commit an honest pre-evidence status report.

## Current result

The deterministic repository-state report is committed at:

`results/experiments/r1/real-corpus-readiness-current.json`

It is `blocked`, with zero eligible work units. In particular, the current
successor-v2 cohort is a five-task pilot scaffold, has no definition digest or
analyzed attempts, uses `pilot` rather than `held_out` splits, does not
predeclare compute-unit accounting, and does not share one role-specialized
signature spelling across all tasks.

These are useful collection blockers, not experimental outcomes. The report
sets:

```json
{
  "evidence_class": "repository_contract_state_not_coding_outcome",
  "supports_empirical_r1_claim": false,
  "status": "blocked"
}
```

## Boundary of the claim

Even a passing readiness report is not proof that the tasks were truly held
out, that the definition was committed before anyone inspected outcomes, or
that all generated attempts were retained. Those temporal and provenance facts
require Git history, prospective attempt commitments, and human review.

Only after those facts are reviewed should the unchanged
`randomness_lab.r1_replay` produce the primary `helps`, `hurts`, or `uncertain`
result. The readiness command never selects a candidate and never writes
canonical state.
