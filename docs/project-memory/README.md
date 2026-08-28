# IDKMesh Project Memory

IDKMesh treats the public repository as the durable project memory.

The purpose of this directory is to make that rule **auditable**, not merely aspirational.

`PROJECT_RULES.md` already requires substantive project conversations, decisions, findings, experiments, formulas, code, and plans to be preserved in the repository. This directory adds a coverage layer so contributors and agents can answer:

> What project knowledge exists, where is its canonical home, and what has not yet been promoted from conversation into durable project structure?

## Memory layers

IDKMesh uses several complementary memory layers.

| Layer | Canonical location | Purpose |
| --- | --- | --- |
| Conversation record | `docs/conversations/` | Preserve project questions, interpretations, decisions, open questions, and action context. |
| Decisions | `DECISIONS.md`, `docs/decisions/` | Preserve durable choices, alternatives, consequences, and revisit conditions. |
| Findings | `docs/findings/` | Preserve research and external/experimental findings. |
| Architecture | `ARCHITECTURE.md`, `docs/architecture/` | Preserve system structure and architectural hypotheses. |
| Research | `docs/research/`, foundation documents | Preserve hypotheses, formulas, experimental plans, and negative results. |
| Specifications | `docs/specifications/`, `schemas/` | Preserve executable/protocol contracts. |
| Experiments/results | `experiments/`, `results/` or experiment artifacts | Preserve reproducible evidence. |
| Community/governance | `COMMUNITY.md`, `GOVERNANCE.md`, `docs/community/` | Preserve contributor and governance mechanisms. |
| Project-memory ledger | this directory | Track whether important project threads have a durable repository representation. |

## Memory coverage invariant

For each substantive project turn, aim to create at least one public-safe durable record before considering the turn complete:

`conversation -> {conversation_record, decision, finding, issue, code, experiment, specification, architecture}`

A turn may produce several of these.

A raw conversation archive alone is **not sufficient** when the turn changes a canonical project assumption. Important conclusions should be promoted into the relevant durable artifact.

Conversely, a code/architecture change without the reason and provenance needed to understand it is also incomplete.

## Completeness states

Each important thread can be classified as:

- **captured** — a public-safe conversation record exists;
- **promoted** — durable conclusions also exist in canonical project artifacts;
- **executable** — the conclusion has a schema, code path, experiment, test, or workflow;
- **verified** — independent/reproducible evidence exists;
- **superseded** — a newer artifact explicitly replaces it while history remains accessible.

These states are deliberately not a single maturity score.

## What “put everything in the repository” means

It means preserving all useful public-safe project substance, including:

- questions and uncertain ideas;
- assistant/user-visible proposals and conclusions;
- accepted and rejected decisions;
- mathematical and physical models;
- algorithms and pseudocode;
- implementation artifacts;
- experimental evidence and negative results;
- security/community/governance constraints;
- unresolved disagreement and uncertainty.

It does **not** mean committing secrets, private credentials, sensitive personal data, third-party restricted material, or private model chain-of-thought.

## Audit rule

Periodically audit project memory together with repository homeostasis:

1. enumerate substantive conversation records;
2. identify decisions/findings that have not been promoted;
3. identify canonical documents with no provenance/context link;
4. identify duplicate or superseded knowledge;
5. create bounded issues/PRs for missing promotion or consolidation;
6. never silently delete contradictory or negative evidence.

The long-term IDKGraph observatory should model these as typed relationships such as:

`conversation -> motivates -> decision`

`decision -> constrains -> specification`

`hypothesis -> tested_by -> experiment`

`experiment -> produces -> evidence`

`evidence -> supports/challenges -> hypothesis`

This turns the repository from a pile of files into an inspectable knowledge graph.