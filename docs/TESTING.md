# Testing and CI Practice

How tests run in IDKMesh, why the tiers are drawn where they are, and what to do
when a gate complains. The measurements quoted here were taken on 2026-09-19;
re-measure before treating any of them as current.

## The short version

```bash
make setup          # once: create .venv and install test dependencies
make test           # the gate: unit tier, ~62 seconds
```

Everything else is automation around those two commands.

## Contributor command source of truth

For contributor setup and testing, use the **current repository state** rather
than historical issue or pull-request prose. The maintained source of truth is
the combination of [`CONTRIBUTING.md`](../CONTRIBUTING.md), this document, the
executable `Makefile` targets, `scripts/testkit.py`, and `pytest.ini`. If an older
issue says a Makefile target is unmerged or should not be assumed, keep that text
as provenance but follow the current files above.

On Linux/macOS and other POSIX-style development environments, the supported
convenience path is:

```bash
make setup
make test
make integration
```

The Makefile is not the only supported path. A direct-Python workflow remains
available when `make` is inconvenient. After creating the virtual environment,
Linux/macOS can run without shell activation:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-phase0.txt pytest
.venv/bin/python -m pytest -q
```

On Windows PowerShell, use the virtual environment's interpreter directly:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-phase0.txt pytest
.\.venv\Scripts\python.exe -m pytest -q
```

Neither path needs a `PYTHONPATH=.` prefix for pytest: `pytest.ini` sets the
repository root on `pythonpath`. These commands define supported entry points;
they are not evidence that every platform has been independently exercised.

## Measured baseline

Every number in this section is **a measurement with a date attached, not a
constant**. The suite moved from 1792 to 1805 collected tests inside one hour on
2026-09-10, and the budgets below were originally calibrated against 870 tests —
which is how `make test` came to exceed its own ceiling by 4.2x before this was
re-derived. Re-measure before trusting any figure here, and re-date the line
above when you do.

Numbers first, because the tier boundaries are derived from them rather than
copied from a blog post:

| Quantity | Measurement |
|---|---|
| `make test` (unit tier) | **62.4 s wall, 61.9 CPU-s**, 1626 passed / 2 skipped / 369 deselected / 3056 subtests |
| Whole suite, no marker filter (PR Gate no longer runs this; `nightly-full-suite.yml` does) | 1997 collected |
| Slowest single test in the unit tier | 2.49 s (`test_r1_scaling_reference`) |
| Affected-test run after a one-file edit | **0.1–0.4 s** |
| CI, mean run / slowest run / daily volume | not re-measured since PR Gate moved from the full suite to the `unit` tier — the figures that stood here predate that change and would understate PR Gate's new speed and overstate its old one |

The important consequence: **this suite is not slow.** A full run costs about as
much as reading the diff you just wrote. Test *selection* is therefore a
convenience for sub-second feedback, never a substitute for running everything
before a commit — skipping a test you should have run costs far more than the 62
seconds it would have taken.

## The tiers

Each tier owns an explicit CPU-time budget. This is the size-and-budget model
large monorepos use (Google's small/medium/large test sizes; Bazel-style
affected-target selection). A tier that exceeds its budget **fails**, which is
the only mechanism that reliably stops a fast suite from decaying into a slow
one over a few quarters.

| Tier | Scope | Budget | Runs |
|---|---|---|---|
| `smoke` | only tests affected by your uncommitted changes | 25 CPU-s | after every edit |
| `unit` | the whole suite except what's marked `sim` or `slow` (`-m "not sim and not slow"`) | 90 CPU-s | before every commit, and the PR Gate's required check |
| `integration` | `unit` + schema JSON syntax + Markdown link integrity | 600 CPU-s | before every push |
| `nightly` | `integration` + everything marked `sim` or `slow` (`-m "sim or slow"`) | none | scheduled — see `.github/workflows/nightly-full-suite.yml` |

`nightly` currently selects 382 tests: simulation/sweep/evidence-replay work
marked `sim`, plus a smaller set of individually expensive tests marked `slow`
(mostly meta-tests that shell out to `unittest` discovery or pytest collection
as subprocesses — the subprocess spawn, not the assertion, is what's slow).
Both markers land in the same tier; the distinction is about *why* a test is
excluded from `unit`, not where it runs.

```bash
make smoke          # ~0.4 s   what you just changed
make test           # ~62 s    the real gate
make integration    #          unit + link/schema checks
make nightly        #          the long tail
make gate           #          picks the cheapest tier that covers your changes
make profile        #          the 25 slowest tests, when a budget is exceeded
```

All of them delegate to `scripts/testkit.py`, so the Makefile, the Claude Code
hooks, and CI execute the same code path and cannot drift apart.

**PR Gate runs `unit` (`scripts/testkit.py unit`) plus the same Markdown-link
check (`scripts/check_links.py`) as its one required, always-on check** —
seconds, not minutes, so a documentation fix isn't held up by the health of an
unrelated simulation. It does not run `integration` as a single delegated call:
the link check stays its own explicit, stdlib-only step
(`tests/test_ci_local_gate_parity.py` pins that shape) so it can run before
`pip install` and cannot silently diverge into a second, inline copy.

**The complete suite — `nightly`, everything `unit` excludes included — runs
on a schedule** in `.github/workflows/nightly-full-suite.yml`, decoupled from
the merge path. A failure there means the research content regressed, not
that a specific pull request is unsafe to merge.

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
  on an identical tree costs ~0.05 s instead of 62 s, so a conversational turn
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
with the failure text, the Stop hook exits 2 and returns to 0 once the failure is
removed.

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

Repository-wide workflow hygiene is now part of current `main` and has an
executable regression contract in `tests/test_workflow_ci_hygiene.py`. The guard
requires every workflow to declare a concurrency group, rejects a bare
workflow-level `cancel-in-progress: true` that could destroy branch/scheduled
evidence, and requires explicit timeouts for ordinary jobs. Workflow-level
cancellation may instead be disabled or gated to pull-request events.

Job-level concurrency remains a deliberate exception surface: workflows such as
the evolution controller can use separately keyed advisory/canonical groups when
the group expression itself preserves the required isolation. The tests pin
those repository-specific cases rather than flattening every workflow into one
concurrency policy.

When changing `.github/workflows/`, run the focused workflow/security tests in
addition to the normal repository gate and treat the current workflow files plus
their regression tests as the source of truth; do not rely on an older issue or
PR description of CI behavior.

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
