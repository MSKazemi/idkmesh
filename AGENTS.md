# Repository Guidelines

## Project Structure & Module Organization

Core prototypes live in `experiments/`, simulations in `randomness_lab/` and `sim/`, bindings in `interop/`, and utilities in `tools/` and `scripts/`. Put tests in `tests/` (or `interop/tests/`) and fixtures under `tests/fixtures/` or `verification/fixtures/`. JSON contracts belong in `schemas/`, samples in `examples/`, outputs in `results/`, policies/state in `config/` and `state/`, and rationale in `docs/`. Read `README.md`, `CONTRIBUTING.md`, and `PROJECT_RULES.md` first.

## Build, Test, and Development Commands

From the repository root:

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements-phase0.txt
python -m unittest discover -s tests -v
python -m unittest discover -s interop/tests -v
python -m randomness_lab --policy thompson --rounds 100 --seed 42
```

The commands run both suites. Use a focused module, such as `python -m unittest tests.test_r2 -v`. Some simulations use `pytest`; follow `sim/README.md` and the relevant workflow.

## Coding Style & Naming Conventions

Follow existing Python conventions: four-space indentation, type hints for public interfaces, and deterministic seeded experiments. Use `snake_case` for files/functions, `PascalCase` for classes, and uppercase constants. Keep CLI scripts runnable from the repository root. No formatter or linter is mandated; match nearby code and avoid unnecessary dependencies.

## Testing Guidelines

Tests primarily use `unittest`: files are `test_*.py`, classes end in `Tests`, and methods begin with `test_`. Add regression tests and deterministic fixtures. There is no numeric coverage threshold; run the relevant suite plus schema, self-test, and CLI checks mirrored in `.github/workflows/`.

## Branch Integration & Merge Safety

Never merge branch refs directly or bulk-merge stale branches. Follow `docs/planning/BRANCH_CONVERGENCE_POLICY.md`: open a bounded PR, review its exact diff, and require green checks and current evidence for the exact head SHA. Drafts and evidence-frozen branches remain blocked until their named gates pass. Prefer squash merge for ordinary short-lived work. After every merge, refresh `main` and re-evaluate the next PR; prior eligibility is stale. For diverged work, transplant only the useful delta onto a clean current-`main` branch. `main` is currently unprotected, so GitHub settings do not enforce these safeguards—maintainers must apply them manually until issue #35 is resolved.

## Commit & Pull Request Guidelines

Use concise, imperative subjects with useful prefixes such as `docs:`, `interop:`, `evidence:`, or `E015:`. Keep commits and PRs focused. Complete the PR template with motivation, verification, related issues, risks, Community Impact, and AI/tool provenance. Discuss large or costly changes in an issue/RFC first. Report vulnerabilities through `SECURITY.md`, never a public issue.
