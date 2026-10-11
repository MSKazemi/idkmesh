# ADR-0025 — Hardened End Anchors for Schema Patterns

**Status:** Accepted
**Date:** 2026-10-09

## Context

Python's `re` matches `$` before a trailing newline, and `jsonschema`
implements the `pattern` keyword with `re.search`. Every end-anchored
pattern in `schemas/` therefore accepted the intended value followed by a
newline: 180 patterns across 60 files, including identity fields such as
commit SHAs (`source_revision`), digests, and ids, where a trailing newline
can make two records that should compare equal differ, or let a value
through that a downstream exact-match check rejects.

That acceptance was never part of the contract. JSON Schema specifies
ECMA-262 regular-expression semantics, whose `$` matches only at the end of
the input; under those semantics `"value\n"` was already invalid against
`^...$`. Python validators were diverging from the specified meaning, and
the schemas were written for the specified meaning. Issue #963 (found while
reviewing #957) records the reproduction on jsonschema 4.26.0.

## Decision

Every end anchor in `schemas/` is written as `$` followed by the guard
`(?!\n)` — the JSON text is `"$(?!\n)"`, with the ordinary `\n` string
escape — and nothing else in the pattern changes. The guard:

- is valid ECMA-262 and a no-op there, because `$` already matches only at
  the end of the input;
- in Python, rejects exactly the strings the lenient `$` used to accept, so
  `P$` + guard behaves precisely as the specification reads `P$`.

Two catalog patterns deliberately match a prefix and carry no end anchor
(`^https://`, `^https://github.com/`); the leniency cannot occur there, and
they are recorded with reasons in `tests/test_schema_pattern_anchors.py`
rather than hardened.

`tools/schema_compat_check.py` recognizes exactly this one mechanical
transform — old pattern ending in an unescaped `$`, new pattern exactly the
old one plus the guard, nothing else in the subschema changed, at any depth
— as compatible. Every other pattern change remains breaking under
ADR-0020's rule.

## Alternatives considered

1. **`\Z`** (option 1 in #963): absolute end-of-input in Python, but
   invalid syntax in ECMA-262; non-Python validators would reject the
   schemas outright. Rejected: the fix must not break the specification's
   own regex dialect.
2. **The `(?!\n)` guard** (option 2 in #963): portable, and provably
   equivalent to what `$` means per the specification. Chosen.
3. **Reject control characters at ingestion only** (option 3): schemas
   would stay over-accepting for every consumer that validates them
   directly (examples, external tools, other runtimes), so the
   machine-readable truth would keep lying. Rejected as insufficient on its
   own; boundary checks may still exist elsewhere.
4. **A custom format checker for identifier families** (option 4): in JSON
   Schema 2020-12 `format` is annotation-only by default, so the leak
   would remain for anyone validating without format assertions. Rejected.

## Consequences

- Python validators now agree with the contract on every anchored pattern.
  `tests/test_schema_pattern_anchors.py` proves the rejection for every one
  of the 180 pattern occurrences — via stdlib `re` and `jsonschema`, and
  including a check that pins the guard as load-bearing (without it,
  Python's `$` accepts the trailing newline) — and fails when a new pattern
  arrives without the guard or without a recorded sample.
- A producer that relied on storing `"value\n"` in an anchored field loses
  acceptance. Those values were never valid under the specification's regex
  semantics and already failed downstream exact-match comparisons; the
  change closes that window rather than rejecting contract-valid data.
  Under `schemas/README.md`'s versioning rule this is therefore a
  validator-divergence repair, not a breaking contract change, and no
  schema file needed a new version.
- This is the one recognized narrowing in the compatibility gate, kept
  mechanically narrow (exact suffix, unescaped `$`, and no other change in
  the subschema — a hardening riding along with any other edit is still
  breaking) so it cannot launder any other pattern change. The review this
  requires is this ADR plus the tests pinning both directions.
- Follow-ups deliberately left out of scope: the `re.compile` anchors in
  `tools/`, `scripts/`, and `idkmesh/` carry the same `$` leniency at
  runtime (they are code-level checks, not schema contract); and the
  `^(?!/)(?!.*(?:^|/)\.\.(?:/|$)).+$` path pattern's internal `$` sits
  inside a negative lookahead, where the leniency can only over-reject,
  never over-accept.
