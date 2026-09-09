# Which module does the v0.4 calibration actually verify with? — 2026-09-05

**Baseline revision:** `c35b31e`.

Read this as a snapshot. Every claim below was produced by running the named
command against that revision; re-run them to re-derive it.

## What was inspected, and why

`Task 001 canonical v0.4 calibration` failed on pull request #386 with exit code
1 and no output, seven milliseconds into its first script step. The step is a
provenance guard:

```bash
test -f experiments/transition_patch_verifier.py
test ! -f experiments/transformation_patch_verifier.py
```

The second assertion failed: both files existed. The question this record answers
is which of the two the calibration was actually running, and what the guard was
protecting.

## What was found

`experiments/transformation_patch_verifier.py` was imported by nothing.

```
$ grep -rl "transformation_patch_verifier" . --exclude-dir=.git
.github/workflows/task001-v04-canonical-calibration.yml
.github/workflows/evaluator-transformation-calibration.yml
```

No Python module, no test, no fixture — only two workflows. Dispatch runs
entirely through `experiments/evaluator_plan_runner.py`, which imports
`transition_patch_verifier` and routes the `unified_diff_transition` backend to
it at line 256. The orphan participated in no verification at any revision after
#171.

### How it came back

| Commit | Date | Effect |
|---|---|---|
| `c60549c` (#171) | 2026-08-28 | Versions v0.4 transition semantics; adds `transition_patch_verifier.py` and rewires the runner |
| `396f01d` | 2026-08-29 | "Extract additive artifacts from `fix/evaluator-transformation-calibration-v0.4`" — restores the superseded `transformation_patch_verifier.py` |

The rename landed; the deletion did not. Nothing imported the restored file, so
no test and no gate went red. The single successful run of this workflow —
2026-08-28, `2fc8b63`, on `calibration/task001-v04-canonical` — predates the
restoration, and `git ls-tree` at that SHA shows `transition_patch_verifier.py`
alone.

### The workflow evidence named the wrong module

`evaluator-transformation-calibration.yml` ran, under the step name **"Compile
calibrated evaluator path"**:

```bash
python -m py_compile \
  experiments/evaluator_plan_runner.py \
  experiments/transformation_patch_verifier.py \
  ...
```

`py_compile` proved the orphan still parsed. The calibration the step then
performed went through the runner to `transition_patch_verifier`. The workflow's
own evidence therefore named a module that took no part in its result — an
asserted provenance field rather than an observed one.

The same substitution disabled the workflow's trigger. Its `paths:` filter
watched `experiments/transformation_patch_verifier.py`, so editing the module the
calibration genuinely depends on did **not** run the calibration.

### Two workflows that could not both pass

`task001-v04-canonical-calibration.yml` asserts the orphan is absent;
`evaluator-transformation-calibration.yml` compiled it, which requires it to be
present. On `c35b31e` the pair was unsatisfiable. This stayed invisible because
both are narrowly path-gated: the canonical workflow triggers on five paths, and
between 2026-08-29 and 2026-09-03 no pull request touched them.

## Why nothing caught it

Neither the failure nor the contradiction is reachable from the unfiltered PR
Gate. The guard that would have caught it lives inside a path-gated workflow, so
its verdict is only produced for the pull requests least likely to need it. A
dead verifier implementation is exactly the kind of artifact that survives that
gap: it compiles, it is never imported, and a `py_compile` step will keep
reporting success over it indefinitely.

## What changed

- `experiments/transformation_patch_verifier.py` deleted, completing #171.
- `evaluator-transformation-calibration.yml` repointed — both `paths:` filters
  and the `py_compile` list — at `experiments/transition_patch_verifier.py`, the
  module its run actually uses.
- `tests/test_patch_verifier_singularity.py` added, so the invariants hold from
  the unfiltered suite rather than from a path-gated workflow:
  1. every `experiments/*_patch_verifier.py` is imported by the runner
     (parsed with `ast`, so a name in a docstring cannot fake dispatch);
  2. every workflow reference to such a module names one that exists and is
     dispatched — unless the line asserts the module's *absence*, which is how
     the canonical workflow pins the #171 rename.

## Verification

Each invariant was broken on purpose and observed to fail:

| Mutation | Outcome |
|---|---|
| Restore `transformation_patch_verifier.py` from `origin/main` | **caught**, 2 failures — the exact defect on `main` |
| Point a `py_compile` line at the deleted module | **caught** — "names `transformation_patch_verifier.py`, which is missing" |
| Comment out `import transition_patch_verifier` in the runner | **caught** — "imported by no dispatcher, so they verify nothing" |
| All restored | 3 passed |

The originally failing CI step, replayed verbatim, exits 0. Full suite at that
revision: 1664 passed, 2 skipped, 4856 subtests; link findings outside
`tests/fixtures/` 0; observatory exit 0.

### Re-verified on 2026-09-10, base `fa16892`

The change above sat unmerged for five days, so its premise was re-tested rather
than assumed before landing. The defect was still live on `main`: the orphan was
still present, still imported by no Python module, and
`Task 001 canonical v0.4 calibration` had failed on **seven consecutive runs**
since 2026-08-29 — its last success, 2026-08-28, was the branch that introduced
the file.

Each mutation was confirmed to have landed in the file before its run, because a
no-op edit makes a working guard look broken:

| Mutation | Outcome |
|---|---|
| Restore `transformation_patch_verifier.py` from `origin/main` | **caught**, 2 failures |
| Point a `py_compile` line at a module that does not exist | **caught**, 1 failure |
| Comment out `import transition_patch_verifier` in the runner | **caught**, 2 failures |
| Replace that import with a *docstring* naming the module | **caught**, 2 failures |
| All restored | 3 passed |

The fourth mutation is the one that tests the `ast` claim specifically: a name
mentioned in a docstring does not count as dispatch, so the guard cannot be
satisfied by prose.

Suite at this base: **1697 passed, 2 skipped, 4867 subtests**, exit 0; link
findings outside `tests/fixtures/` 0; observatory `--fail-on-errors` exit 0; the
originally failing CI step replayed verbatim exits 0.

The suite figure differs from the 1664 above only because `main` gained tests in
the interval. Neither number is wrong; they are measured on different trees.

## What this does not establish

The calibration's *result* was never wrong — dispatch always reached
`transition_patch_verifier`, so no published calibration outcome is retracted by
this record. What was wrong is the evidence trail: a workflow step named a module
that had no part in the run it certified, and the path filter guarding that run
watched a file the run did not read.
