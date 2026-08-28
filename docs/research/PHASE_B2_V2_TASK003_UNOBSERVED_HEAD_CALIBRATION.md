# Phase B2 successor-v2 Task 003 calibration

## Question

Can the provisional EvaluatorPlan v0.4 for
`benchmark/phase-b2-v2/003-branch-unobserved-head` distinguish a real fail-closed
transition from a lexical near-miss, while a separate behavioral check confirms
the intended branch-provenance semantics?

The task concerns `tools/branch_convergence_audit.py` at frozen public source:

`a69aa0ae1ae4862e507511cbd9ad854237d0ad32`

At that source, merged-PR matching contains:

```python
head_sha is None or pr.head_sha == head_sha
```

so an unavailable current branch head can incorrectly satisfy historical merged
PR evidence and become `integrated-via-pr` / cleanup eligible.

## Pre-calibration novelty check

Before creating the calibration branch on 2026-08-28:

- current `main` still contained the same vulnerable condition;
- repository PR search for the Task 003 unobserved-head fix found the scaffold
  PR #186 and premature-freeze provenance #185, not a published implementation
  of the intended fix;
- the successor-v2 task evidence remained pending.

This is a point-in-time novelty check, not a guarantee that the task will remain
novel until a future benchmark freeze. Issue #180 still requires another fresh
novelty audit immediately before freezing the scaffold.

## Frozen evaluator commitment

EvaluatorPlan:

`benchmarks/phase-b2-successor-v2/evaluators/task-003-branch-unobserved-head.evaluator-plan.json`

It requires the candidate patch to add:

```text
head_sha is not None
```

and remove:

```text
head_sha is None or pr.head_sha == head_sha
```

The evaluator is the canonical metadata-only v0.4 transition verifier. It does
not execute candidate code.

## Calibration candidates

### Straightforward

The direct transition changes the merged-PR exact-head filter from accepting a
missing head to requiring an observed non-null current head that exactly matches
the reviewed PR head.

Expected static result:

- added transition: 1/1;
- removed transition: 1/1;
- verification: pass;
- recommendation: `accept_candidate`.

### Inert decoy

The near-miss adds the text `head_sha is not None` as an inert module constant
but leaves the vulnerable merged-PR condition unchanged.

Expected static result:

- added transition: 1/1;
- removed transition: 0/1;
- verification: fail;
- recommendation: `reject_candidate`.

This specifically tests whether v0.4's required-removal evidence prevents a
simple lexical Goodhart failure.

## Behavioral matrix

The calibration imports the modified auditor from a disposable checkout of the
exact frozen source and constructs one merged PR whose reviewed head is
`reviewed-head-sha`.

It then evaluates three current-head observations:

| Current head | Straightforward expectation | Safety meaning |
| --- | --- | --- |
| unavailable / `None` | `post-merge-branch-moved`, not cleanup eligible | fail closed because exact current identity was not observed |
| `reviewed-head-sha` | `integrated-via-pr`, cleanup eligible | exact reviewed source head may retire after provenance checks |
| `new-unreviewed-head-sha` | `post-merge-branch-moved`, not cleanup eligible | post-merge branch reuse does not inherit old approval |

For the inert decoy, the missing-head case is expected to remain vulnerable:
`integrated-via-pr` and cleanup eligible.

This behavioral channel is separate from the metadata-only EvaluatorPlan
verifier. The two channels must agree before Task 003 can be marked calibrated.

## Authority boundary

The workflow is read-only with respect to the repository and uses no secrets.
It writes only to a disposable frozen-source checkout and ignored `results/`
evidence paths.

Calibration does **not**:

- freeze successor-v2;
- add a definition digest;
- create a scored benchmark outcome;
- choose a production candidate;
- modify the canonical branch auditor;
- push, approve, or merge a candidate;
- grant worker or verifier integration authority.

A passing calibration establishes only that the provisional evaluator is fit to
remain a candidate freeze-time evaluator for this task. Issue #180's remaining
calibration, lifecycle, and novelty gates still apply.
