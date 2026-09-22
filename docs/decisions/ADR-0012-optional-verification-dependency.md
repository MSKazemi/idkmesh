# ADR-0012 — Real Schema Verification Is an Optional Extra, Not a Base Dependency

**Status:** Accepted

**Date:** 2026-09-21

## Context

ROADMAP.md §4 ("R1 — Finish one real local product loop") names independent
verification as a required pipeline stage: bounded task -> WorkUnit -> 2+
isolated attempts -> candidate bundle -> **independent verification** ->
evidence report -> exact replay -> human decision.

`experiments/local_verifier.py` is the module that actually performs that
verification against the `ResultManifest`/`VerificationResult` contracts: it
loads `schemas/*.schema.json` and validates real instances against them with
`jsonschema.Draft202012Validator`. It is exercised by
`tests/test_patch_evaluator_safety.py`,
`tests/test_evaluator_plan_v03_semantics.py`,
`tests/test_patch_evaluator_transition_v04.py`, several `tools/*calibration*`
and `tools/phase_b2_*` scripts, and is central to the "Evaluator Sovereignty"
line of decisions (`docs/decisions/ADR-0008-evaluator-sovereignty.md`,
`docs/decisions/ADR-0009-evaluator-sovereignty.md`).

The installable `idkmesh` package (`pyproject.toml`, entry point
`idkmesh.cli:main`) is, by contrast, deliberately dependency-free:

```toml
# Deliberately dependency-free: the audit is pure stdlib so it can run inside
# any CI job without a resolver step.
dependencies = []
```

`idkmesh/cli.py` currently exposes exactly one subcommand, `gate-audit`,
which consumes a verdict matrix that was *already collected* and computes
per-verifier accuracy, correlation, effective votes, and probe-breach rate —
all pure stdlib (`argparse`, `json`, `statistics`). It performs no schema
validation of `ResultManifest`/`VerificationResult` documents and never runs a
gate. `README.md` frames this as deliberate: "The first installable tool cut
from this research is `idkmesh gate-audit`" — one narrow, zero-resolver-step
capability, not the whole research tree.

This creates a genuine tension rather than incidental plumbing. Real
independent verification — the R1 pipeline stage — is not reachable from the
`idkmesh` package at all today; it only exists as a repository-internal
research script that assumes `jsonschema` is already on `sys.path`
(`requirements-phase0.txt` pins `jsonschema>=4.18,<5` for repository
development and CI, and several workflows install `jsonschema` directly).
That split is invisible to anyone who only does `pip install idkmesh`: they
get `gate-audit` and nothing that can verify a WorkUnit result.

Repository search found no prior issue or ADR settling this specifically
(`gh issue list --search "jsonschema dependency"` and `--search "dependency
policy"` returned no matches), and `CONTRIBUTING.md`'s "Code quality" section
states only the general principle "no unnecessary dependencies" — it does not
say the installable package must stay dependency-free forever, nor does it
say a real capability may never gain a dependency. It does not resolve which
side of this specific tension wins.

## Options considered

### A. Stay dependency-free forever; real verification never joins the CLI

Keep `dependencies = []` permanent and leave `experiments/local_verifier.py`
a research-only script, never exposed through `idkmesh.cli`.

Rejected. This would freeze the R1 pipeline's independent-verification stage
out of the one product surface this project has actually shipped
(`idkmesh gate-audit`), permanently. `gate-audit` audits verdicts that were
already collected by some other means; nothing installable would ever be able
to produce a real, schema-checked `VerificationResult` for a WorkUnit. That
directly blocks ROADMAP.md §4's stated goal of a pipeline "runnable end-to-end
on a real task" from ever using an installed `idkmesh`, not just from using an
unfinished one.

### B. Add `jsonschema` as a hard base dependency

Move `jsonschema` into `dependencies` unconditionally.

Rejected. It breaks the one property `dependencies = []` was written to
guarantee — that `pip install idkmesh` and `idkmesh gate-audit` need no
resolver step and no network access in any CI job, which is exactly the
zero-friction path README.md's "Try it in five minutes" section demonstrates
and issue #16 ("Ship the local Git-native Verified Swarm Runner") depends on
for adoption. A user who only wants `gate-audit` — the only capability the
package ships today — would pay a dependency they never asked for, and the
"pure stdlib" comment in `pyproject.toml` would become false for 100% of
installs, not just the ones that need real verification.

### C. Vendor a minimal stdlib-only schema-subset validator

Hand-write a small validator inside `idkmesh` covering only the subset of
JSON Schema draft 2020-12 the three project schemas
(`work-unit-v0.2`, `result-manifest-v0.1`, `verification-result-v0.1`) use,
avoiding `jsonschema` entirely.

Rejected for this decision. It would keep the base install dependency-free,
but at real cost: reimplementing and then permanently maintaining a partial,
project-specific reimplementation of `jsonschema`'s `Draft202012Validator`
(including its `format` checks, e.g. `date-time` — already used via
`FormatChecker()` in `local_verifier.py`) — divergence risk against the real
draft, a second thing to keep correct as schemas evolve, and it would not
match what `experiments/local_verifier.py`, its tests, and the Evaluator
Sovereignty ADRs already exercise against real `jsonschema`. A
schema-validator reimplementation is exactly the kind of "unnecessary
dependenc[y]" surface CONTRIBUTING.md's code-quality bar warns against
creating for its own sake — it would trade one dependency for a larger,
harder-to-keep-correct one. Nothing in this decision forecloses reconsidering
this later if `jsonschema`'s footprint ever becomes a real problem, but no
evidence of that exists today (`jsonschema` is a pure-Python, small,
widely-used package with no further runtime dependencies beyond its own
`jsonschema-specifications`/`referencing`/`rpds-py` stack, already pinned and
installed for the rest of the repository's test suite).

### D. Optional extra: `pip install idkmesh[verify]` (chosen)

Add `[project.optional-dependencies]` with a `verify` extra pulling in
`jsonschema`, leave `dependencies = []` untouched, and make
`experiments/local_verifier.py` fail with a clear, actionable message instead
of a bare `ImportError` traceback when the extra is not installed.

Accepted. See Decision.

## Decision

Real schema-based verification becomes reachable as an **optional extra**,
not a base dependency:

```toml
[project.optional-dependencies]
verify = ["jsonschema>=4.26,<5"]
```

`dependencies = []` in `pyproject.toml` is unchanged: `pip install idkmesh`
and `idkmesh gate-audit` remain exactly as dependency-free as before this
ADR.

A user or CI job that needs real verification opts in explicitly:

```bash
pip install -e '.[verify]'      # repository checkout
pip install idkmesh[verify]     # released idkmesh package
```

`experiments/local_verifier.py` now guards its `jsonschema` import and raises
an `ImportError` with the exact install commands above (and the
`requirements-phase0.txt` alternative already used elsewhere in this
repository) when the extra is missing, rather than letting an unhandled
`ImportError` surface at an arbitrary internal line.

The version bound (`>=4.26,<5`) is the current stable `jsonschema` release as
of this decision (2026-09-21), per this project's "always latest stable"
dependency rule; `<5` bounds the next major release, which is not yet out and
could change the API.

This decision does not change `idkmesh.cli`: it does not add a verification
subcommand today. It only removes the packaging obstacle, so that when a CLI
verification subcommand is added it can declare `jsonschema` as an extra
instead of forcing the choice this ADR already settles.

## Rationale

A base install and an opt-in capability are different promises, and this
project already makes exactly that distinction operationally:
`requirements-phase0.txt` is a separate, explicit install step from the base
package for repository development, and `requirements-interoperability.txt`
layers further optional SDKs (`a2a-sdk`, `mcp`) on top of it for interop
testing. `pyproject.toml`'s own `[project.optional-dependencies]` mechanism is
the standard way to express that same distinction for the *installable
package* rather than only for repository-internal development — a user typing
`pip install idkmesh[verify]` gets exactly the same explicitness and the same
"you asked for this" property that `requirements-phase0.txt` already gives
repository contributors.

This also resolves the tension in the terms the project already uses:
"zero-resolver-step for gate-audit" (Option B breaks this) and "real,
schema-checked verification reachable from an install" (Option A never
delivers this) are not actually in conflict — they only look like a
dependency-free-forever-vs-hard-dependency choice if the base install and the
optional capability are forced to share one dependency list.

## Consequences

### Positive

- `pip install idkmesh` and `idkmesh gate-audit` remain stdlib-only, exactly
  as `pyproject.toml`'s existing comment promises; no existing install gains
  a new dependency.
- Real independent verification (`experiments/local_verifier.py`) becomes
  installable, not only runnable from a full repository checkout with
  `requirements-phase0.txt` manually applied — closing the packaging gap
  ROADMAP.md §4's pipeline needs.
- A missing `jsonschema` now fails with the exact install command, not a
  bare traceback pointing at an internal `from jsonschema import ...` line.
- The extra's name (`verify`) and pin (`jsonschema>=4.26,<5`) are available
  for a future `idkmesh.cli` verification subcommand to declare, without
  reopening this decision.

### Costs / risks

- The package now carries two dependency states (`dependencies = []` vs.
  `.[verify]`) that a contributor must keep in mind; `pyproject.toml`'s
  comments and this ADR are the record of why.
- `experiments/local_verifier.py` itself is still not part of the shipped
  `idkmesh` wheel (`[tool.setuptools] packages = ["idkmesh"]`) — the `verify`
  extra makes `jsonschema` installable, not `local_verifier.py` importable
  from outside a repository checkout. Exposing real verification through
  `idkmesh.cli` itself remains future work, tracked by ROADMAP.md §4, not by
  this ADR.
- `jsonschema`'s own transitive dependencies (`jsonschema-specifications`,
  `referencing`, `rpds-py`) become new dependencies for anyone who does
  install the extra.

## Revisit conditions

Revisit if `idkmesh.cli` gains a verification subcommand (this ADR's `verify`
extra name and pin should be reused, not re-decided) or if evidence emerges
that a stdlib-only schema-subset validator (Option C) is worth the
maintenance cost after all — for example if `jsonschema`'s dependency chain
becomes a real adoption barrier for `gate-audit` users who do not want
`verify` at all (it currently does not, since `verify` is opt-in and does not
touch their install).

## Implementation references

- `pyproject.toml` — `[project.optional-dependencies]` `verify` extra
- `experiments/local_verifier.py` — guarded `jsonschema` import with an
  actionable error message
- `tests/test_local_verifier_missing_jsonschema.py` — regression test for the
  error message
- `requirements-phase0.txt` — the pre-existing repository-development pin
  this extra parallels

## References

- `ROADMAP.md` §4 — "R1 — Finish one real local product loop"
- `docs/decisions/ADR-0008-evaluator-sovereignty.md`
- `docs/decisions/ADR-0009-evaluator-sovereignty.md`
- `CONTRIBUTING.md` — "Code quality": "no unnecessary dependencies"
- `README.md` — "Try it in five minutes: audit a review gate"
