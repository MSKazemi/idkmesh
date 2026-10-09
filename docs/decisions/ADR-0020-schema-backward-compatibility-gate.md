---
description: "Accepted ADR: a published IDKMesh JSON schema may never change to reject previously valid data; a breaking change needs a new versioned schema file."
---
# ADR-0020 — Schema Backward-Compatibility Gate

**Status:** Accepted
**Date:** 2026-09-27

## Context

Issue #737 (API-2, "complete public API schema catalog and add compatibility
CI") lists six CI requirements. Five already hold on `main`: every schema
resolves, `tests/test_example_contract_coverage.py` validates documented
examples, `tests/test_control_tower.py` and its siblings validate real
runtime responses against their advertised schemas, `additionalProperties:
false` is used throughout where intended, and `tests/test_schema_identity.py`
enforces unique `$id`/`title`. The sixth -- "backwards-compatibility diff
check for stable v1 objects" and "breaking changes require explicit version
bump/migration note" -- did not exist: nothing stopped an in-place edit of an
already-shipped `schemas/*.json` file from silently rejecting or reinterpreting
data a prior version of that same file accepted.

This is not hypothetical. `schemas/work-unit-v0.2.schema.json` and
`schemas/evaluator-plan-v0.2.schema.json` were each mutated in place after
their initial commit in exactly this way -- a nested object gained new
`required` fields, and a property lost required status, respectively --
before this ADR existed to catch it. Both predate this decision and are not
being retroactively treated as violations; they are the evidence that
motivated it.

An open pull request (#892) separately claims to add "automated schema
backwards-compatibility CI gate" for this same issue, but comes from an
11-day-old account, uses a mutable-tag GitHub Action, and is one of several
cross-repository near-identical PRs with cryptocurrency-payment-service
ties -- flagged as likely supply-chain-adjacent spam and left for Mohsen's
own decision, not merged or otherwise acted on by this session. This ADR and
its implementation are independent, originally-authored work; #892's
existence is noted here only so a future reader does not wonder why two
things with the same description exist.

## Decision

Every file under `schemas/` is versioned in its own filename
(`-v0.1.schema.json`, `-v0.2.schema.json`, ...). Once a schema file exists,
its content must never change in a way that could reject data a prior
version of the *same file* accepted, or silently reinterpret what a client
validating against it can rely on. The only sanctioned way to make a
breaking change is to add a new, separately versioned file -- exactly what
`work-unit-v0.1.schema.json` -> `work-unit-v0.2.schema.json` already did
correctly -- and to land it with an explicit migration note in the
`Schema migrations` section of `schemas/README.md` naming the exact file it
supersedes. `tools/schema_compat_check.py` enforces the version bump;
`tools/schema_migration_note_check.py` enforces the note (issue #737's
"migration note" half), against a ledger that already documents every
successor in the tree.

`tools/schema_compat_check.py` enforces this mechanically. It walks both the
old (at a `--base` git ref, default the merge-base of `HEAD` and
`origin/main`) and new (working tree) content of every schema file that
exists in both, and flags:

- a property removed from `properties`, at any nesting depth;
- any change to a `required` array (gain or loss, symmetric — both change
  the contract);
- any change to `additionalProperties`;
- a leaf property's subschema changing at all, **except** two recognized
  widenings: an `enum` gaining values (all old values still present) and a
  `type` gaining alternatives (all old types still accepted). Both are
  drawn from real precedent already on `main`
  (`search-visibility-observation-v0.1.schema.json`'s search-surface enum
  has already grown twice in place).

Everything else — new optional properties, description/title wording,
`$defs` additions, whitespace — is compatible and unflagged.

The tool's own module docstring records its one known v0.1 limitation:
`allOf`/`oneOf` branches and cross-file `$ref` targets are not resolved, so
a change hidden purely inside one would not be caught today. No schema in
this repository as of this ADR uses either, so nothing is currently blind;
the docstring exists so the tool is extended before being trusted for a
future schema that does.

Verification before trusting this as a required gate: run against every
historical multi-commit schema file's full git history (not just synthetic
fixtures). It correctly flagged the two known real breaking edits above and
raised nothing else — no false positive across the repository's actual
schema history.

## Consequences

### Positive

- issue #737's sixth, previously-unmet CI requirement is now enforced;
- the two historical in-place breaking edits this ADR cites can no longer
  happen silently; the same edit today fails `gate (3.11)`/`gate (3.13)`
  with the exact property/path that broke;
- a legitimate widening (enum growth, type widening) still lands without a
  new file, matching this repository's own established practice rather
  than forcing unnecessary version churn.

### Costs

- a genuinely intended breaking change to a schema now always means adding
  a new versioned file, even for a schema with few or no real external
  consumers yet — the cost of the mechanical rule not knowing which schemas
  are load-bearing;
- the tool's `allOf`/`oneOf`/cross-file-`$ref` blind spot (documented above)
  must be closed before any future schema relies on those constructs to
  express its evolution.

## Alternatives considered

### A general-purpose JSON Schema diff library

Rejected for v0.1. No such library ships in `requirements-phase0.txt`, and
this repository's schemas use a narrow, consistent subset of Draft 2020-12
(flat and nested `properties`/`required`/`additionalProperties`, `const`,
`enum`, `type`, `$ref` only to local `#/$defs`) — a purpose-built, ~150-line
comparator covering exactly that subset is easier to audit and to extend
than adopting a general dependency whose own compatibility semantics would
need auditing in turn.

### Require a version bump on *any* schema content change, even additive ones

Rejected. This repository has already, correctly, evolved schemas in place
by adding optional properties or widening an enum (the search-visibility
example). Forcing a new file for every such change would produce version
churn with no compatibility benefit and would make the genuinely breaking
cases (this ADR's actual target) harder to spot among routine additive
ones.

## Implementation ownership

- Issue #737 (API-2) is the owning issue; this ADR closes its sixth,
  previously unmet CI requirement.
- `tools/schema_compat_check.py` and `tests/test_schema_compat_check.py`
  are the implementation and its test suite.
- `tools/schema_migration_note_check.py` and
  `tests/test_schema_migration_notes.py` enforce the migration-note half
  against the `Schema migrations` ledger in `schemas/README.md`.
- `.github/workflows/pr-gate.yml`'s `gate` job runs both as required steps
  alongside the existing unit tier and Markdown-link check.

## Revisit conditions

Revisit this ADR if:

- a future schema needs `allOf`/`oneOf` or a cross-file `$ref` to express
  its own evolution — extend the tool's node walker before trusting it for
  that file, per its module docstring;
- the two-widening allowlist (`enum` growth, `type` widening) proves too
  narrow or too permissive in practice — evidence from an actual missed or
  falsely-flagged change, not speculation, should drive any change to it.
