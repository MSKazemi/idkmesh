# Testing and CI Practice

How tests run in IDKMesh, why the tiers are drawn where they are, and what to do
when a gate complains. The measurements quoted here were taken on **2026-09-10,
22:12-22:33 UTC**, at commit `5a211bd`, on a 4-core Linux container running
CPython 3.11.15 at load average 0.2-0.9. Re-measure before treating any of them
as current, and re-date this line when you do.

The previous baseline was taken earlier the same day on a 20-core machine.
CPU-seconds are the figure that carries across the two; wall-clock and the
`runs/day` volume are not directly comparable.

## The short version

```bash
make setup          # once: create .venv and install test dependencies
make test           # the gate: full suite, ~67 seconds
```

Everything else is automation around those two commands.

## Measured baseline

Every number in this section is **a measurement with a date attached, not a
constant**, and the drift is not slow. The suite moved from 1792 to 1805
collected tests inside one hour on the morning of 2026-09-10; by 22:30 the same
day it was 1860. The budgets below were originally calibrated against 870 tests
— which is how `make test` came to exceed its own ceiling by 4.2x before this
was re-derived. Re-measure before trusting any figure here, and re-date the line
above when you do.

Numbers first, because the tier boundaries are derived from them rather than
copied from a blog post:

| Quantity | Measurement |
|---|---|
| `make test` (unit tier) | **66.9 s wall, 67.0 CPU-s**, 1489 passed / 2 skipped / 369 deselected / 3000 subtests |
| `make integration` | 67.1 CPU-s (the schema and link gates add well under a second) |
| `make nightly` | 266.7 s wall, 267.0 CPU-s |
| Whole suite, no marker filter (what CI runs) | 1860 collected |
| Slowest single test in the unit tier | 2.20 s (`test_r1_scaling_reference.py::R1ScalingReferenceTests::test_flat_arm_still_regenerates_the_committed_payload`) |
| Slowest single test anywhere | 23.40 s (`test_r1_dependence_shape.py::ReplayTests::test_the_default_invocation_regenerates_the_committed_payload`, `sim`) |
| Affected-test run after a one-file edit | **0.3–1.7 s** |
| CI, mean run | 1.3 min (median 0.6, p95 4.5) |
| CI, slowest run observed | 8.9 min (PR Gate) |
| CI, daily volume | mean 195 runs/day and 259 wall-minutes/day |

The CI rows are measured over the seven full days 2026-09-03 to 2026-09-09
(1366 completed runs across 51 workflows), because a single day is not
representative: daily volume over that window ranged from **2 runs to 466**, and
wall-clock from 1 minute to 856. Treat the mean as an order of magnitude, not a
rate. The slowest run is the slowest in that window; a `PR Gate` run on
2026-09-10 took 12.6 min.

The important consequence: **this suite is still not slow.** A full run costs
about as much as reading the diff you just wrote. Test *selection* is therefore
a convenience for fast feedback, never a substitute for running everything
before a commit — skipping a test you should have run costs far more than the 67
seconds it would have taken.

It is, however, no longer comfortably inside its ceiling: 67.0 CPU-s against a
90 CPU-s budget is **75% of the unit tier's headroom consumed**, where the
budget was set expecting roughly 2.5x. That is a fact about the suite to act on
by making tests cheaper or moving them to a later tier, not a reason to raise
the number — see [When a budget is exceeded](#when-a-budget-is-exceeded).

## The tiers

Each tier owns an explicit CPU-time budget. This is the size-and-budget model
large monorepos use (Google's small/medium/large test sizes; Bazel-style
affected-target selection). A tier that exceeds its budget **fails**, which is
the only mechanism that reliably stops a fast suite from decaying into a slow
one over a few quarters.

| Tier | Scope | Budget | Runs |
|---|---|---|---|
| `smoke` | only tests affected by your uncommitted changes | 25 CPU-s | after every edit |
| `unit` | the whole suite (`-m "not sim and not slow"`) | 90 CPU-s | before every commit |
| `integration` | `unit` + schema JSON syntax + Markdown link integrity | 600 CPU-s | before every push |
| `nightly` | `integration` + everything marked `sim` or `slow` | none | scheduled |

**`nightly` is no longer equivalent to `integration`.** When this document was
first written no test carried `@pytest.mark.sim`; today 311 do, and a further 58
carry `slow`. Those 369 tests are what `unit` deselects, and running them is
what makes `nightly` (267 CPU-s) four times the cost of `integration` (67
CPU-s). The tier stopped being a placeholder and started doing its job.

```bash
make smoke          # ~0.3-1.7 s  what you just changed
make test           # ~67 s       the real gate
make integration    # ~67 s       what the PR Gate enforces, locally
make nightly        # ~267 s      the long tail
make gate           #             picks the cheapest tier for your changes
make profile        #             the 25 slowest tests, when a budget is exceeded
```

All of them delegate to `scripts/testkit.py`, so the Makefile, the Claude Code
hooks, and CI execute the same code path and cannot drift apart.

### Budgets are CPU-seconds, not wall-clock

The machine this is developed on is shared with other projects. While this
document was being written, a neighbouring repository's test run pushed the load
average past 25 on 20 cores, and the identical IDKMesh suite went from 34 s to
**124 s** of wall-clock without a single line of test code changing. That
observation, and the 53-versus-36 CPU-s pair two paragraphs below, are from the
20-core machine at the size the suite was then. They are kept because the reason
they justify has not changed — not as current timings.

A wall-clock budget would have failed the gate for a reason that had nothing to
do with IDKMesh. CPU time is the load-independent measure of "is the suite
getting slower", so that is what the budget polices. Wall-clock is still
reported, and still used as a hang timeout.

CPU time is not perfectly isolated either — under that same contention the suite
measured 53 CPU-s against an idle baseline of 36, because cache pressure and
context switching are real costs. The 90 CPU-s budget was set with that ~1.5x
contention factor in mind, on top of a 36 CPU-s suite. At 67 CPU-s idle, that
allowance is spent: a contended run today would exceed the budget. Fixing the
suite is the response; raising the budget is not.

**Per-test hang ceilings are deliberately not used.** pytest's
`faulthandler_timeout` looks like a free upgrade, but arming it starts a
faulthandler watchdog thread for the whole run, and
`sim/e033_goal_distance.py` parallelises with
`multiprocessing.get_context("fork")` because each job re-points the
environment's future goal in module globals. Forking a multi-threaded process is
the documented deadlock case: a thread holding a lock at fork time leaves it held
forever in the child. Measured — with `faulthandler_timeout = 300`,
`tests/test_e033_goal_distance.py` emitted two such warnings; at `0`, the same 69
tests emitted none. The watchdog is a C-level thread, so it never shows up in
`threading.enumerate()`; the warning is the only symptom. `pytest.ini` records
this so the setting is not reintroduced.

### When a budget is exceeded

Do **not** raise the budget. Run `make profile`, find what got slow, and either
fix it or mark it for a later tier:

```python
@pytest.mark.sim    # excluded from unit; runs in nightly
@pytest.mark.slow   # measured above the tier-2 per-test budget
```

Raising a budget converts a one-time cost into a permanent one, and there is no
natural point at which anyone ever lowers it again.

## Automation: tests without typing test commands

Two Claude Code hooks in `.claude/settings.json` run the tiers automatically.
This is the agent equivalent of a continuous test runner (NCrunch, Wallaby,
Infinitest): feedback arrives while the change is still in working memory.

| Hook | Event | Tier | Behaviour |
|---|---|---|---|
| `.claude/hooks/test-on-edit.sh` | `PostToolUse` on any edit | `smoke` | `asyncRewake` — runs in the background, interrupts only on failure |
| `.claude/hooks/test-on-stop.sh` | `Stop` | `auto` | blocking — a turn does not end on a red tree |

Two properties make this cheap enough to run constantly:

* **Result caching.** `scripts/testkit.py` fingerprints the content of every
  tracked file plus uncommitted changes. Re-running a tier that already passed
  on an identical tree costs ~0.2 s instead of 67 s, so a conversational turn
  that touched no code is not taxed.

  The fingerprint deliberately has **no extension allowlist**. Hashing only
  `.py`/`.json`/`.ini` looks like a cheap optimisation and is actually unsound
  here: the integration tier link-checks 419 tracked `.md` files and the workflow
  guards read 51 workflow `.yml` files, so a real workflow violation reported
  `cached pass -- tree unchanged` while the guard, run directly, failed. Hashing
  all 1320 tracked files (28 MB) costs 0.13 s. A cache that can hide a genuine
  failure is worth less than the time it saves.
* **`asyncRewake` on the edit hook.** On the happy path it costs nothing; it
  only surfaces when a test the edit actually affects has broken.

The Stop hook honours `stop_hook_active`, so a genuinely unfixable failure
blocks once and then lets the turn end rather than looping forever.

Both were verified against a deliberately failing test: the edit hook exits 2
with the failure text, the Stop hook exits 2 and returns to 0 once the failure
is removed.

### Test selection, and its limits

`smoke` maps changed sources to tests two ways: the `tools/foo.py` →
`tests/test_foo.py` naming convention, and a reverse-import scan for any test
importing the changed module. Changing `tools/idkgraph_link_check.py`, for
instance, selects `test_idkgraph_link_check.py`, `test_idkgraph_health_checks.py`
and `test_check_links.py` — 39 tests in 1.6 s. A change with no importer at all
(`experiments/free_compute_router.py`) reports `no affected Python tests` and
costs nothing.

Selection deliberately **fails open**: a change to a `conftest.py`, an
`__init__.py`, or `pytest.ini` cannot be attributed to specific tests, so the
runner widens to the full suite instead of trusting a partial answer.

## CI

`pytest.ini` sets `pythonpath = .`, so a bare `pytest` now works. The old
`PYTHONPATH=. pytest` prefix is no longer required (plain `unittest` discovery
still under-collects; prefer pytest).

### Workflow hardening

The concurrency-group and cancellation work that accompanied these tiers is now
on `main`, so this section can state it. It is still not stated on trust:
`tests/test_workflow_ci_hygiene.py` re-derives the three invariants from
`.github/workflows/` on every run, over however many workflows exist, so a new
workflow that omits one fails the suite rather than silently contradicting this
paragraph.

* every workflow declares a `concurrency:` group, at workflow or job level;
* no workflow sets a bare workflow-level `cancel-in-progress: true`, which would
  cancel branch and scheduled runs and destroy the evidence artifact for a commit;
* every job declares `timeout-minutes`.

Two workflows — `evolution-loop.yml` and `repository-math-portfolio.yml` — scope
concurrency per *job* rather than per workflow, so that advisory
`pull_request_target` observations stay isolated from canonical ones instead of
sharing one ref-keyed queue. That is deliberate, and
`tests/test_evolution_observer_concurrency.py` pins it.

As of this document's measurement date there are 51 workflows and 49
workflow-level `cancel-in-progress` values. Those two counts are measurements,
like everything else here; the guard checks the property, not the number.

## Adding tests

Conventions are unchanged: files are `test_*.py`, classes end in `Tests`,
methods begin with `test_`, fixtures are deterministic and seeded. `pytest.ini`
sets `--strict-markers`, so a typo'd marker is an error rather than a silent
no-op.

Mark anything long-running:

```python
@pytest.mark.sim
def test_full_sweep_replays_the_committed_evidence(): ...
```

## Troubleshooting

| Symptom | Cause |
|---|---|
| `pytest: command not found` | Run `make setup`. |
| A tier passes instantly without running | Cached pass on an unchanged tree. `make clean-cache` or pass `--no-cache`. |
| `BUDGET EXCEEDED` | Run `make profile`; mark the offender `sim`/`slow`. Do not raise the budget. |
| The Stop hook keeps blocking | The suite is genuinely red. It blocks once per turn, never in a loop. |
| Hooks do not fire | Claude Code watches `.claude/` only if a settings file existed at session start. Open `/hooks` once, or restart the session. |
