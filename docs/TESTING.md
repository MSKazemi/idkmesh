# Testing and CI Practice

How tests run in IDKMesh, why the tiers are drawn where they are, and what to do
when a gate complains. The measurements quoted here were taken on 2026-09-10;
re-measure before treating any of them as current.

## The short version

```bash
make setup          # once: create .venv and install test dependencies
make test           # the gate: full suite, ~64 seconds
```

Everything else is automation around those two commands.

## Measured baseline

Every number in this section is **a measurement with a date attached, not a
constant**. The suite moved from 1792 to 1865 collected tests inside one day on
2026-09-10, and the budgets below were originally calibrated against 870 tests —
which is how `make test` came to exceed its own ceiling by 4.2x before this was
re-derived. Re-measure before trusting any figure here, and re-date the line
above when you do.

The timing rows were taken on **4 cores at load average 1.02**, so they are not
comparable to a figure from a busier or wider machine; the section below on
CPU-seconds explains why. The counting rows are properties of the tree, not of
the machine, and `tests/test_documented_tier_scopes.py` re-derives the marker
expressions this document publishes directly from `scripts/testkit.py`.

Numbers first, because the tier boundaries are derived from them rather than
copied from a blog post:

| Quantity | Measurement |
|---|---|
| `make test` (unit tier) | **65.0 s wall, 65.0 CPU-s**, 1494 passed / 2 skipped / 369 deselected / 3000 subtests |
| Whole suite, no marker filter (what CI runs) | 1865 collected |
| Selected by the nightly leg (`-m "sim or slow"`) | 369 |
| Slowest single test in the unit tier | 2.20 s (`test_flat_arm_still_regenerates_the_committed_payload`) |
| Affected-test run after a one-file edit | **0.1–0.4 s** |
| CI, mean run | 0.7 min |
| CI, slowest run observed | 3.5 min (PR Gate) |
| CI, daily volume | ~122 runs/day, ~90 wall-minutes/day |

The important consequence: **this suite is not slow.** A full run costs about as
much as reading the diff you just wrote. Test *selection* is therefore a
convenience for sub-second feedback, never a substitute for running everything
before a commit — skipping a test you should have run costs far more than the
minute it would have taken.

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
| `nightly` | `integration` + everything marked `sim` or `slow` (`-m "sim or slow"`) | none | scheduled |

**`nightly` is not equivalent to `integration`.** The two tier markers are in
use: 311 tests carry `sim`, and `-m "sim or slow"` selects 369 — exactly the 369
the unit tier deselects in the table above. Every one of them runs only in
`nightly`, so a change that breaks one is invisible to the pre-commit and
pre-push gates until the scheduled run.

This paragraph previously said the opposite — that no test carried
`@pytest.mark.sim` and that the two tiers therefore did the same work — while
the baseline table in the section immediately above already recorded 369
deselected tests. The document contradicted itself on arrival, which is why the
marker expressions are now re-derived from `scripts/testkit.py` by a test rather
than retyped here.

```bash
make smoke          # ~0.4 s   what you just changed
make test           # ~64 s    the real gate
make integration    #          what the PR Gate enforces, locally
make nightly        #          the long tail
make gate           #          picks the cheapest tier that covers your changes
make profile        #          the 25 slowest tests, when a budget is exceeded
```

All of them delegate to `scripts/testkit.py`, so the Makefile, the Claude Code
hooks, and CI execute the same code path and cannot drift apart.

### Budgets are CPU-seconds, not wall-clock

This machine is shared with other projects. During development of this document
a neighbouring repository's test run pushed the load average past 25 on 20
cores, and the identical IDKMesh suite went from 34 s to **124 s** of wall-clock
without a single line of test code changing.

A wall-clock budget would have failed the gate for a reason that had nothing to
do with IDKMesh. CPU time is the load-independent measure of "is the suite
getting slower", so that is what the budget polices. Wall-clock is still
reported, and still used as a hang timeout.

CPU time is not perfectly isolated either — under that same contention the suite
measured 53 CPU-s against an idle baseline of 36, because cache pressure and
context switching are real costs. The 90 CPU-s budget is set with that in mind.

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
  on an identical tree costs ~0.05 s instead of 64 s, so a conversational turn
  that touched no code is not taxed.

  The fingerprint deliberately has **no extension allowlist**. Hashing only
  `.py`/`.json`/`.ini` looks like a cheap optimisation and is actually unsound
  here: the integration tier link-checks 398 tracked `.md` files and the workflow
  guards read 51 `.yml` files, so a real workflow violation reported
  `cached pass -- tree unchanged` while the guard, run directly, failed. Hashing
  all 1232 tracked files (~28 MB) costs 0.1 s. A cache that can hide a genuine
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
instance, selects both `test_idkgraph_link_check.py` and
`test_idkgraph_health_checks.py`.

Selection deliberately **fails open**: a change to a `conftest.py`, an
`__init__.py`, or `pytest.ini` cannot be attributed to specific tests, so the
runner widens to the full suite instead of trusting a partial answer.

## CI

`pytest.ini` sets `pythonpath = .`, so a bare `pytest` now works. The old
`PYTHONPATH=. pytest` prefix is no longer required (plain `unittest` discovery
still under-collects; prefer pytest).

### Workflow hardening

The concurrency-group and cancellation work that accompanied these tiers has
since landed. All 51 workflows carry a `concurrency` group, a
`cancel-in-progress` value, and `timeout-minutes`, and
`tests/test_workflow_ci_hygiene.py` pins all three so the property is asserted
by the suite rather than restated here. That test is deliberately text-based:
the PR Gate installs only `pytest` and `requirements-phase0.txt`, so a
YAML-parsing guard would pass locally and fail in the gate it describes.

`cancel-in-progress` is not a bare `true`. A superseded pull-request run should
be cancelled, but a branch or scheduled run must not be — several of these
workflows are the only uploader of their commit's evidence artifact, and
cancelling one destroys a record nothing can re-derive.

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
