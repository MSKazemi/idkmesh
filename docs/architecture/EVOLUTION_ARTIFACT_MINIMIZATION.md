# Evolution Artifact Minimization

**Status:** post-#148 hardening  
**Date:** 2026-08-28

## Principle

IDKMesh should retain the **minimum evidence necessary to reproduce and review a decision**, not every raw input used transiently to compute it.

This is especially important for repository-wide observers because GitHub issue and pull-request bodies are untrusted natural-language input. They may be useful ephemerally for deterministic classification or same-repository reference extraction, but retaining them in every checkpoint is unnecessary unless a specific reproducibility requirement justifies it.

## Portfolio boundary

The Repository Mathematical Portfolio needs issue/PR text while it computes deterministic task features.

The correct boundary is:

```text
public GitHub issue/PR text
 -> ephemeral /tmp snapshot
 -> deterministic portfolio calculation
 -> derived portfolio state/output/report
 -> raw snapshot discarded with runner
```

The uploaded checkpoint contains only:

- `repository-portfolio-state.json`;
- `repository-portfolio.json`;
- `REPOSITORY_PORTFOLIO.md`;
- `repository-portfolio-policy.json`.

It must **not** contain the transient `repository-snapshot.json` with raw issue/PR bodies.

The workflow enforces this with an explicit negative assertion before upload.

## Relationship to the live observatory

The canonical Repository Evolution Observatory already follows a stricter collection model: its persisted snapshot does not store issue, PR, or comment bodies at all. It retains bounded structural metadata such as labels, age, references, reviewer coverage, and participant counts.

The portfolio and observatory therefore use different transient inputs but converge on the same evidence-minimization principle.

## Why this matters

Artifact minimization improves:

- privacy and contributor expectations;
- prompt-injection containment;
- artifact size and reviewability;
- reproducibility by emphasizing derived evidence contracts rather than uncontrolled text archives;
- future schema/version migrations.

It also narrows what a downstream consumer must treat as untrusted text.

## Non-goals

This rule does not claim public GitHub text is secret; the source objects remain public. The purpose is to avoid unnecessary durable duplication inside IDKMesh artifacts and to keep the retained evidence surface bounded.

It does not remove the project requirement to preserve **useful project-chat decisions** in `docs/conversations/`. Those records are deliberate curated project memory, not indiscriminate copies of arbitrary GitHub input.

## Future extension

If raw text is ever required for a reproducible experiment, use an explicit versioned evidence contract with:

- purpose;
- bounded scope;
- content hashing/provenance;
- retention policy;
- untrusted-text marker;
- independent review of why derived features are insufficient.
