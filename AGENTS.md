# Repository Guidelines

## Project Structure & Module Organization

Core prototypes live in `experiments/`, simulations in `randomness_lab/` and `sim/`, bindings in `interop/`, and utilities in `tools/` and `scripts/`. Put tests in `tests/` (or `interop/tests/`) and fixtures under `tests/fixtures/` or `verification/fixtures/`. JSON contracts belong in `schemas/`, samples in `examples/`, outputs in `results/`, policies/state in `config/` and `state/`, and rationale in `docs/`. Read `README.md`, `CONTRIBUTING.md`, and `PROJECT_RULES.md` first.

## Build, Test, and Development Commands

From the repository root:

```bash
make setup      # once: creates .venv and installs the test dependencies
make test       # the gate: the whole unit suite, about a minute
make gate       # the cheapest tier that covers what you actually changed
```

Every target delegates to `scripts/testkit.py`, so the Makefile, the git hooks, the Claude Code hooks and CI run the same code path. The tiers, their CPU-second budgets and the measured baseline are in [`docs/TESTING.md`](docs/TESTING.md); read it before changing a budget.

Without `make`, the same suite runs directly:

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements-phase0.txt pytest
python -m pytest -q
python -m randomness_lab --policy thompson --rounds 100 --seed 42
```

`pytest.ini` sets `pythonpath = .`, so the old `PYTHONPATH=.` prefix is no longer required. `pytest` collects both suites (`tests/` and `interop/tests/`) in one run. Use a focused module, such as `python -m pytest -q tests/test_r2.py`.

**Do not use `python -m unittest discover` to check your work.** It silently under-collects: `unittest` only finds `TestCase` subclasses, so the **162** module-level `test_*` functions spread across **17** files in `tests/` are invisible to it — roughly a tenth of the suite, reported as `OK` with no warning that anything was missed. `tests/test_documented_test_counts.py` re-measures both figures and the gap they explain, so this paragraph fails the suite if it drifts.

## Coding Style & Naming Conventions

Follow existing Python conventions: four-space indentation, type hints for public interfaces, and deterministic seeded experiments. Use `snake_case` for files/functions, `PascalCase` for classes, and uppercase constants. Keep CLI scripts runnable from the repository root. No formatter or linter is mandated; match nearby code and avoid unnecessary dependencies.

## Testing Guidelines

Tests primarily use `unittest`: files are `test_*.py`, classes end in `Tests`, and methods begin with `test_`. Add regression tests and deterministic fixtures. There is no numeric coverage threshold; run the relevant suite plus schema, self-test, and CLI checks mirrored in `.github/workflows/`.

## Branch Integration & Merge Safety

Never merge branch refs directly or bulk-merge stale branches. Follow `docs/planning/BRANCH_CONVERGENCE_POLICY.md`: open a bounded PR, review its exact diff, and require green checks and current evidence for the exact head SHA. Drafts and evidence-frozen branches remain blocked until their named gates pass. Prefer squash merge for ordinary short-lived work. After every merge, refresh `main` and re-evaluate the next PR; prior eligibility is stale. For diverged work, transplant only the useful delta onto a clean current-`main` branch. `main` is protected: `gate (3.11)` and `gate (3.13)` are required checks, and force-pushes and branch deletion are blocked. Protection does not enforce the rest of this section—it requires zero approving reviews, does not bind administrators, does not require a branch to be current with `main` before merging, and cannot judge whether evidence is current for the exact head SHA—so maintainers must still apply the review, evidence, and merge-order rules above manually.

## Commit & Pull Request Guidelines

Use concise, imperative subjects with useful prefixes such as `docs:`, `interop:`, `evidence:`, or `E015:`. Keep commits and PRs focused. Complete the PR template with motivation, verification, related issues, risks, Community Impact, and AI/tool provenance. Discuss large or costly changes in an issue/RFC first. Report vulnerabilities through `SECURITY.md`, never a public issue.
