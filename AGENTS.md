# Repository Guidelines

## Project Structure & Module Organization

Core prototypes live in `experiments/`, simulations in `randomness_lab/` and `sim/`, bindings in `interop/`, and utilities in `tools/` and `scripts/`. Put tests in `tests/` (or `interop/tests/`) and fixtures under `tests/fixtures/` or `verification/fixtures/`. JSON contracts belong in `schemas/`, samples in `examples/`, outputs in `results/`, policies/state in `config/` and `state/`, and rationale in `docs/`. Read `README.md`, `CONTRIBUTING.md`, and `PROJECT_RULES.md` first. Use `ARCHITECTURE.md` for the current system map, `ROADMAP.md` for evidence-gated future work, and `docs/README.md` for deeper subsystem/research indexes.

## Build, Test, and Development Commands

The supported local entry points now live in the repository and delegate to the same `scripts/testkit.py` tiers used by the documented development workflow:

```bash
make setup          # create .venv and install core test dependencies
make smoke          # tests affected by the current working-tree change
make gate           # cheapest complete tier for the current change
make test           # full non-simulation/unit tier
make integration    # unit + schema/link integration gates
```

`make setup` and the Makefile targets are intended for POSIX-style development environments. The direct Python path remains supported and is the portable fallback:

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements-phase0.txt pytest
python -m pytest -q
python -m randomness_lab --policy thompson --rounds 100 --seed 42
```

`pytest.ini` sets the repository root on `pythonpath`, so `PYTHONPATH=.` is no longer required for pytest on current `main`. See `docs/TESTING.md` for tier budgets, caching, hooks, CI parity, and Windows-specific guidance. Use a focused module, such as `python -m pytest -q tests/test_r2.py`, while iterating.

**Do not use `python -m unittest discover` to check your work.** It silently under-collects: `unittest` only finds `TestCase` subclasses, so the **166** module-level `test_*` functions spread across **18** files in `tests/` are invisible to it — roughly a tenth of the suite, reported as `OK` with no warning that anything was missed. `tests/test_documented_test_counts.py` re-measures both figures and the gap they explain, so this paragraph fails the suite if it drifts.

## Agent Contribution Loop

Autonomous agents should treat current repository state as evidence, not memory. Before changing code or docs:

1. refresh from current `main` and note the exact base revision;
2. inspect relevant open issues and pull requests so work is not duplicated;
3. distinguish code already on `main` from PR-only, proposed, historical, or experimental behavior;
4. keep public documentation in the same bounded change when commands, interfaces, architecture, or evidence boundaries change;
5. run the smallest useful feedback loop while editing, then the repository gate appropriate to the final diff;
6. report the commands actually run, their actual result, remaining uncertainty, and AI/tool provenance;
7. never represent owner-controlled automation as independent human or external-agent review.

Prefer one reviewable outcome per branch/PR over broad speculative rewrites. If a requested feature depends on a human-only evidence gate or missing authority, document the blocker instead of manufacturing evidence.

## Coding Style & Naming Conventions

Follow existing Python conventions: four-space indentation, type hints for public interfaces, and deterministic seeded experiments. Use `snake_case` for files/functions, `PascalCase` for classes, and uppercase constants. Keep CLI scripts runnable from the repository root. No formatter or linter is mandated; match nearby code and avoid unnecessary dependencies.

## Testing Guidelines

`pytest` is the canonical runner. The suite intentionally contains both `unittest.TestCase`-style tests and module-level pytest `test_*` functions, so do not infer collection from one style alone. Add regression tests and deterministic fixtures. There is no numeric coverage threshold; run the relevant focused tests while editing and the appropriate `scripts/testkit.py`/Makefile tier before proposing integration. Schema, link, workflow, self-test, CLI, and simulation checks are mirrored by repository workflows as documented in `docs/TESTING.md` and `.github/workflows/`.

## Branch Integration & Merge Safety

Never merge branch refs directly or bulk-merge stale branches. Follow `docs/planning/BRANCH_CONVERGENCE_POLICY.md`: open a bounded PR, review its exact diff, and require green checks and current evidence for the exact head SHA. Drafts and evidence-frozen branches remain blocked until their named gates pass. Prefer squash merge for ordinary short-lived work. After every merge, refresh `main` and re-evaluate the next PR; prior eligibility is stale. For diverged work, transplant only the useful delta onto a clean current-`main` branch. `main` is protected: `gate (3.11)` and `gate (3.13)` are required checks, and force-pushes and branch deletion are blocked. Protection does not enforce the rest of this section—it requires zero approving reviews, does not bind administrators, does not require a branch to be current with `main` before merging, and cannot judge whether evidence is current for the exact head SHA—so maintainers must still apply the review, evidence, and merge-order rules above manually.

## Commit & Pull Request Guidelines

Use concise, imperative subjects with useful prefixes such as `docs:`, `interop:`, `evidence:`, or `E015:`. Keep commits and PRs focused. Complete the PR template with motivation, verification, related issues, risks, Community Impact, and AI/tool provenance. Discuss large or costly changes in an issue/RFC first. Report vulnerabilities through `SECURITY.md`, never a public issue.