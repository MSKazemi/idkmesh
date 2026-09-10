# First-run report: the three setup paths disagree — 2026-09-10

## What this is, and what it is not

This is an **AI-assisted agent's first run** through the documented setup path,
recorded against [issue 403](https://github.com/MSKazemi/idkmesh/issues/403).
It is **not** an independent human newcomer report, and it must not be counted
as one of the three that issue is waiting for. The contributor pilot is explicit
on this point: "Do not label AI-written first-time-user feedback as an
independent human observation."

What it can honestly supply is the part a machine is good at: following the
written instructions literally, and reporting where they contradict the
repository. Every finding below is a document disagreeing with another document
or with the tree, checked by running the command or grepping for the file.

- Base revision: `5a211bd`.
- Tool: Claude Code (Opus 5), running `make`, `pytest`, `git log` and `grep`.
- Verified by a person: no. The findings are mechanical and reproducible; the
  judgement about which fix is right is not.

## Journey

| Step | Observation |
| --- | --- |
| `README.md` | "Run the repository checks" gives a three-line `pip` + `PYTHONPATH=. python -m pytest -q` recipe. No mention of a `Makefile`, and no link to `docs/TESTING.md`. |
| `CONTRIBUTING.md` | "Running the tests" gives the same recipe, then states that these commands "work without an unmerged Makefile or local testkit", and that if an older issue refers to `make setup`, `make test` or `make integration`, the reader should prefer the instructions there. |
| `ls` | There **is** a `Makefile` at the repository root. It declares `setup`, `smoke`, `test`, `integration`, `nightly`, `gate`, `profile` and `clean-cache`, and its header points at `docs/TESTING.md`. |
| `docs/TESTING.md` | Opens with "The short version: `make setup`, `make test`", and calls everything else "automation around those two commands". |
| `AGENTS.md` | The file coding agents read first gives only the `pytest` recipe. It never mentions the `Makefile`, `scripts/testkit.py`, the tiers, or the budgets an agent can trip. |
| `grep -rn "TESTING.md" --include=*.md .` | Zero inbound links. `docs/TESTING.md` is reachable only from the `Makefile` header comment. |

## Findings

### 1. The contribution guide denies that the primary workflow exists

`CONTRIBUTING.md` told a reader on 2026-09-10 that `make setup` and `make test`
belong to unmerged tooling. `Makefile`, `scripts/testkit.py` and
`docs/TESTING.md` were added to `main` that same day in
[`807a41b`](https://github.com/MSKazemi/idkmesh/commit/807a41b) (#435); the
paragraph denying them was written the day before, in
[`217695a`](https://github.com/MSKazemi/idkmesh/commit/217695a). It was accurate
when written and became wrong 24 hours later.

This is not a hypothetical cost. The corrections on issues
[397](https://github.com/MSKazemi/idkmesh/issues/397) and
[398](https://github.com/MSKazemi/idkmesh/issues/398) are the same defect seen
from the other side: two tasks were put on hold specifically because the file
and the commands they named were not on `main` yet. A newcomer who reads those
corrections today, then finds a `Makefile` in their checkout, has no way to tell
which source is current.

### 2. `docs/TESTING.md` had no inbound link from anywhere

The document that explains the tiers, the CPU-second budgets, the caching and
the automation hooks was unreachable by navigation. A contributor who trips a
`BUDGET EXCEEDED` message could not find the page that explains it without
already knowing the filename.

### 3. Three files publish three different first commands

`README.md`, `CONTRIBUTING.md` and `AGENTS.md` all carried the `pip` +
`PYTHONPATH=. pytest` form while `docs/TESTING.md` led with `make`. The
`PYTHONPATH=.` prefix is itself stale: `pytest.ini` sets `pythonpath = .`, and
`docs/TESTING.md` already said so — "the old `PYTHONPATH=. pytest` prefix is no
longer required" — while the three front-door files kept asking for it.

### 4. Agents were routed around the gate they are measured by

`AGENTS.md` sent an agent to bare `pytest`, so the tier budgets, the affected-
test selection and the result cache were invisible to the actor most likely to
run the suite dozens of times in an hour.

## Fixes made in the same change

- `CONTRIBUTING.md`, `README.md` and `AGENTS.md` lead with `make setup` /
  `make test`, keep the direct `pytest` route as the no-`make` fallback, drop
  the obsolete `PYTHONPATH=.` prefix, and link `docs/TESTING.md`.
- `CONTRIBUTING.md` replaces the "unmerged Makefile" paragraph with a dated note
  saying the tooling landed on 2026-09-10 and that a checkout outranks an issue
  comment.
- `AGENTS.md` names `make gate` and points at the tiers and budgets.

## Observation versus preference

| Type | Finding |
| --- | --- |
| Observed contradiction | A guide on `main` describing tooling on `main` as unmerged. Reproducible by reading two files. |
| Observed navigation gap | `docs/TESTING.md` with zero inbound Markdown links. Reproducible by one `grep`. |
| Observed staleness | `PYTHONPATH=.` documented as required in three files; unnecessary since `pytest.ini` gained `pythonpath = .`. |
| Preference, not a defect | Whether `make` or `pytest` should lead. Either is defensible; that the four files should agree is not a preference. |

## Limitation

One run, by one agent, on Linux with `make` and Python 3.11 present. It says
nothing about Windows, about a reader with no `make`, or about whether the
project is *understandable* — only about whether its instructions are internally
consistent. The confusion issue 403 is actually hunting is the kind a person
feels and a grep cannot, and those three reports are still outstanding.
