# IDKGraph P0 Residual Health Checks

Status: experimental deterministic P0 rules  
Parent: issue #20  
Authority: warning-only observation

## Purpose

After T1–T5 landed, two original issue #20 health checks were still not represented in the canonical observatory:

1. unintentionally orphaned documents;
2. accepted decisions that are not linked from an affected canonical document when that relationship can be declared deterministically.

The phrase **unintentionally orphaned** contains semantic intent that cannot be derived safely from graph absence alone. The P0 implementation therefore reports **orphan document candidates**, not proven defects. Accepted-decision linkage is also warning-only because an accepted decision may intentionally affect only non-document artifacts.

Reference implementation: `tools/idkgraph_health_checks.py`.

## Rule 1 — orphan document candidate

A mapped T3 node becomes an `orphan_document_candidate` warning only when all of these deterministic conditions hold:

- node type is `document`;
- `attributes.repository_path` is below `docs/`;
- basename is neither `README.md` nor `index.md` (explicit directory entrypoint conventions);
- T2 has no resolved local Markdown link from a **different source document** to that path.

Self-links do not make a document discoverable and therefore do not count as inbound navigation.

The warning message explicitly states that lack of an inbound link is a navigation-review candidate, not proof of accidental orphaning.

## Rule 2 — accepted decision without document link

A mapped T3 `decision` node becomes an `accepted_decision_without_document_link` warning only when:

- its source ADR file has an explicit `Status:` field whose value begins with `Accepted`;
- no T3 `implements` hyperedge targets that decision from a mapped node of type `document`.

Accepted status is read only from an explicit field such as:

```markdown
Status: Accepted
```

or:

```markdown
- **Status:** Accepted
```

Prose containing words like “accepted”, “approved”, “implemented”, or “superseded” does not change the rule.

The relation side uses only T3's explicit `## Implementation references` mapping. Arbitrary Markdown links and semantic similarity do not become implementation evidence.

## Severity

Both rules are **warnings**, never hard errors in P0.

Rationale:

- a standalone research note may intentionally be unlinked;
- an ADR may intentionally affect only schemas/code/artifacts;
- absence of evidence is insufficient to infer author intent;
- P0 should surface inspectable deterministic conditions without pretending they are semantic truth.

## Integration

The unified `tools/idkgraph_observatory.py` now includes:

```json
"contracts": {
  "p0_residual_health": "idkgraph-health-checks-v0.1"
},
"residual_health": {
  "orphan_document_candidates": 0,
  "accepted_decisions_without_document_link": 0
}
```

Actual counts depend on the scanned repository snapshot. Individual warnings are included in the existing deterministic-warning list with source path, source ID, category, message, and derivation evidence.

The human-readable `repository-health.md` includes both aggregate counts in its deterministic summary.

## Expected negative acceptance fixtures

A repository-wide observatory scan also traverses its own committed acceptance fixtures. That is useful for graph/replay coverage, but a deliberately broken fixture must not be confused with a real repository-health defect.

The observatory therefore has one explicit, versioned expected-negative prefix:

```text
tests/fixtures/idkgraph_observatory/broken/
```

When the **repository root** is scanned, T2 findings whose `source_path` begins with that exact prefix are moved out of the active error/warning set into an `expected_negative_fixtures` evidence block. The block retains:

- the configured prefix;
- finding count;
- counts by original severity and category;
- source path, line, message, and raw target for every seeded finding.

This is accounting, not deletion. The expected evidence remains visible in `observatory.json` and `repository-health.md`.

Crucially, when the broken fixture directory is scanned **directly**, its source paths are simply `README.md` and `target.md`, so the prefix does not match and the fixture still fails closed. The acceptance test therefore continues to prove that missing-file and missing-anchor defects are detected.

No arbitrary test directory, `tests/` subtree, or user-supplied path is silently ignored.

## Reproducibility

The rules consume only:

- repository bytes;
- T2 resolved local-link evidence;
- T3 mapped nodes and explicit `implements` edges.

Expected-negative accounting also uses only the explicit repository-relative fixture prefix above and the deterministic T2 findings produced from the same bytes.

No timestamps, network calls, GitHub API state, embeddings, model calls, or human-maintained reputation values enter the calculation. A fixed repository snapshot therefore yields the same residual-health findings and the same expected-fixture evidence.

## Non-goals

- no semantic judgment of whether an orphan candidate is actually undesirable;
- no automatic link insertion;
- no automatic ADR implementation inference;
- no conversion of warnings into merge authority;
- no document deletion/archive action;
- no LLM/NLP classification;
- no blanket suppression of test fixtures or repository subtrees.

These rules complete the deterministic detection surface requested by issue #20 while preserving the project's uncertainty-first principle.
