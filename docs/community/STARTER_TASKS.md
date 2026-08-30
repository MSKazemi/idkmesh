# Starter tasks

Ten small, independently useful pieces of work, across seven kinds of
contribution. Each one is bounded, has an acceptance test you can run yourself,
and was checked against the repository at `ce5051b` before being listed here —
none of them is hypothetical.

## Why this file exists

At the time of writing, every newcomer-labelled issue in this repository was an
*independent review* request: `#167` carried `good first issue`, and `#138`,
`#151` and `#167` carried `help wanted`. That is a bootstrapping deadlock. The
one advertised way in requires exactly the kind of person the project is trying
to attract, and offers nothing to someone who would rather start by writing a
test, reading a workflow, or reproducing a number.

These tasks are the other doors. They deliberately span documentation, testing,
security, research, review, community and tooling, because a project that only
accepts code gets only coders.

## How to use this list

- **Claim nothing.** Tasks marked *parallel welcome* are explicitly safe for
  several people to attempt at once; IDKMesh is a project about redundant
  independent attempts, so duplicated effort here is data, not waste.
- **Negative results count.** If you attempt a task and conclude it should not
  be done, that write-up is a contribution and will be treated as one.
- **Read [CONTRIBUTING.md](../../CONTRIBUTING.md) first** for the closing-keyword
  rule and the pull request gate.
- Times are rough estimates for someone new to the repository.

Every task below assumes you have run:

```bash
PYTHONPATH=. python -m pytest -q
```

and seen it pass, so you can tell your change apart from a pre-existing failure.

---

## Testing

### T1 — Assert every command-line tool answers `--help`

**Parallel welcome.** ~45 minutes.

`tools/` contains 40 modules that build an `argparse` parser. Nothing asserts
that they still start. A tool can be broken by an import error, a bad default,
or a renamed helper, and no test in the suite would notice until someone ran it
by hand.

All 40 currently pass, so this task adds a guard rather than fixing a bug.

**Acceptance:** a test that discovers the tools rather than hard-coding a list,
runs each with `--help` in a subprocess, and asserts a zero exit status and
non-empty output. It must fail if a tool is broken — demonstrate that by
temporarily breaking one, and say so in the pull request.

```bash
for f in tools/*.py; do grep -q argparse "$f" && PYTHONPATH=. python "$f" --help >/dev/null || echo "FAIL $f"; done
```

### T2 — Give the untested `sim/` helper modules their own tests

**Parallel welcome** — take one module and say which in the pull request title.
~1–2 hours per module.

Eleven modules under `sim/` have no `tests/test_<name>.py`:
`e015_analyze`, `e015_worker`, `e016_agent`, `e016_corpus`, `e017_analyze`,
`e017_oracles`, `e017_verify`, `run_aco_parameter_sweep`, `run_aco_sweep`,
`run_emergence_sweep`, `run_verifier_correlation_sweep`.

Some are covered indirectly by the experiment tests. Establishing *which* is
itself useful: a module that turns out to be genuinely covered deserves a note
saying so, not a redundant test file.

**Acceptance:** for the module you pick, either new direct tests for its public
functions, or a short written finding showing where it is already exercised.

---

## Security

### S1 — Check every workflow's `permissions:` block is least-privilege

**Parallel welcome** — split the 49 workflows into batches. ~2 hours per batch.

All 49 workflows in `.github/workflows/` declare an explicit top-level
`permissions:` block, so none of them silently inherits the default token
scope. The remaining question is whether each block is *minimal*: a workflow
that only reads the tree should not hold `contents: write`.

Related invariant, already enforced: every third-party action is pinned to an
immutable commit SHA, guarded by
[`tests/test_workflow_action_pinning.py`](../../tests/test_workflow_action_pinning.py)
and recorded in [SECURITY.md](../../SECURITY.md).

**Acceptance:** a table of workflow, declared permissions, and the narrowest
permissions its steps actually need, with a pull request narrowing the ones that
are provably over-scoped. Do not widen anything.

---

## Documentation

### D1 — Mark the completed research tracks as completed

~30 minutes.

[`docs/research/FIRST_RESEARCH_PROGRAM.md`](../research/FIRST_RESEARCH_PROGRAM.md)
presents three research tracks as the current program. Two of the three are
finished: issue `#14` and issue `#15` are both closed, while `#13` is still
open. A reader following the program cannot tell which is which.

**Acceptance:** each track annotated with its state and, where the work landed
somewhere in the tree, a link to it. Do not delete the closed tracks — the
document is a record of what the program was.

### D2 — Resolve the four documents reachable only from non-markdown artifacts

**Parallel welcome.** ~1 hour.

The repository observatory reports four documents referenced only by
non-markdown artifacts, at `notice` severity. They are reachable by code but
invisible to a human browsing the documentation.

```bash
PYTHONPATH=. python tools/idkgraph_observatory.py . --output-dir /tmp/obs --pretty
python -c "import json;d=json.load(open('/tmp/obs/observatory.json'));print(d['residual_health'])"
```

**Acceptance:** each of the four either linked from an appropriate index, or
documented as intentionally standalone. Preserve false positives rather than
silencing them — see the note on retained detector findings in
[`docs/community/README.md`](README.md).

---

## Research

### R1 — Independently reproduce the E029 negative result

**Parallel welcome** — independent reproductions are the point. ~3 hours.

[`experiments/E029-first-real-model-attempts.md`](../../experiments/E029-first-real-model-attempts.md)
reports that a pinned open-weight model produced **0 of 60** attempts the
verifier was even asked to judge, and that 56 of the 60 failures were
unified-diff *protocol* failures rather than failures of the proposed change.

That is a strong claim resting on one run by one person.

**Acceptance:** an independent run, with your numbers next to the published
ones and an explicit statement of where they diverge. A reproduction that
disagrees is more valuable than one that agrees.

### R2 — Re-derive the benchmark publication by hand

~1 hour.

[`benchmarks/PUBLICATION.md`](../../benchmarks/PUBLICATION.md) is generated from
the cohort definitions by
[`tools/benchmark_publication.py`](../../tools/benchmark_publication.py). It
claims 4 cohorts, 20 tasks, 5 tasks with a verified outcome and 5 attempts, all
sharing one structural signature.

An earlier hand-written audit claimed six attempts spread across all four
cohorts and was wrong, which is why the number is generated now. Checking the
generator against the raw files is therefore exactly the kind of scrutiny this
number has already failed once.

```bash
PYTHONPATH=. python tools/benchmark_publication.py --check
```

**Acceptance:** counts derived independently from `benchmarks/*/cohort.json`,
compared against the published report, and any discrepancy reported as an issue
rather than silently corrected.

---

## Review

### V1 — Independently review the IDKGraph orphan cohort

~2–3 hours. Tracked as issue `#167`.

Fifteen candidate documents need an independent `agree` / `disagree` /
`uncertain` judgement. The task needs no understanding of the wider
architecture and can be completed from public repository evidence alone.

**Acceptance:** as stated on the issue — all 15 candidates judged, reviewer
minutes recorded honestly, and disagreements preserved rather than reconciled
to match the existing audit.

---

## Community

### C1 — Walk the newcomer path and record where you stopped

**Parallel welcome** — several independent walks are far more useful than one.
~1 hour.

[`docs/community/onboarding-tests/2026-08-29-newcomer-path.md`](onboarding-tests/2026-08-29-newcomer-path.md)
records one attempt to follow this project's front door as a newcomer. One
sample is not a measurement.

**Acceptance:** a new dated record in `onboarding-tests/` following the existing
format, saying honestly where you became confused or stopped. Do not fix the
documentation in the same pull request — the observation is the contribution,
and mixing the two makes it impossible to see what confused you.

---

## Tooling

### G1 — Report per-family coverage in the benchmark publication

~2 hours.

Each cohort declares required task families. The publication reports totals and
per-cohort state but not which families actually carry a verified outcome, so a
cohort could be complete in aggregate while an entire family sits untested.

**Acceptance:** family-level coverage added to the generated report, the
committed `benchmarks/publication.json` and `PUBLICATION.md` regenerated, and
`--check` still returning zero. Publish no aggregate score or pass rate — see
the reasoning already recorded in the publication itself.
