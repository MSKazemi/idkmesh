# IDKGraph Repository Mapping v0.1

Status: experimental P0 mapping contract  
Parent: issue #20, decomposition #85 T3  
Authority: observation only; no repository or graph mutation

## Purpose

IDKGraph needs typed nodes and relations sourced from the repository without turning prose interpretation into asserted truth. This mapping defines a deliberately conservative first boundary:

> **Only explicit repository structure, identifiers, and convention-bound metadata become deterministic graph facts.**

If a fact requires semantic interpretation, it stays out of the deterministic P0 graph until a separately modeled evidence/inference layer exists.

The reference implementation is `tools/idkgraph_repository_mapping.py` and the traceable example is `examples/idkgraph.repository-mapping.example.json`.

## Deterministic node mapping

| Repository source | IDKGraph node type | Identity rule | Title rule | Why deterministic |
| --- | --- | --- | --- | --- |
| Markdown file not matching the ADR convention | `document` | canonical T1 `document_id(repository_relative_path)` | first T1 heading, otherwise filename stem | path and parsed heading are explicit repository bytes |
| `docs/decisions/ADR-NNNN-*.md` | `decision` | `decision:ADR-NNNN` | first T1 heading | directory + filename convention explicitly identifies an ADR |
| `*.work-unit.json` containing a non-empty JSON `id` | `work_unit` | `work_unit:<source id>` | explicit `objective`, otherwise source `id` | source object exposes a stable identifier |
| file under `schemas/` | `artifact` | `artifact:<repository path>` | repository path | path category is explicit |
| non-WorkUnit file under `examples/` | `artifact` | `artifact:<repository path>` | repository path | path category is explicit |

A source file maps to at most one P0 node. In particular, an ADR is a `decision` node rather than both a `document` and a `decision`; a Work Unit example is a `work_unit` rather than a second generic artifact node. The source file remains traceable in `attributes.repository_path` and `provenance.source`.

## Deterministic relation mapping

### ADR implementation references -> `implements`

A path is admitted only when it appears as a backtick-delimited bullet inside the exact Markdown section:

```markdown
## Implementation references

- `schemas/idkgraph.schema.json`
```

If that path already maps to a P0 node, the mapper emits:

```text
referenced node --implements--> decision node
```

The edge records the declaring ADR and declared path. Merely mentioning a path elsewhere in prose does not create this relation.

### Work Unit input locator -> `requires`

For a mapped canonical Work Unit, each string `inputs[].locator` is considered explicit dependency metadata. If the locator resolves to a repository path already mapped as a P0 node, the mapper emits:

```text
work_unit --requires--> referenced node
```

The mapper does not infer dependencies from the Work Unit objective, context summary, or natural-language policies.

## Determinism and ordering

- Repository paths are normalized as POSIX paths relative to the selected root.
- Node output is sorted by node ID.
- Hyperedge output is sorted by deterministic edge ID.
- Edge IDs are SHA-256-derived from relation + sorted sources + sorted targets.
- No current timestamp is emitted by this mapping layer.
- Running the mapper twice against the same bytes must produce byte-identical normalized JSON.
- Ordinary Markdown document identity is delegated to T1. T3 does not introduce a second document identity formula.

## Traceability requirements

Every mapped node includes:

- `attributes.repository_path`;
- `attributes.source_kind`;
- `attributes.mapping_method = deterministic_repository_structure`;
- `provenance.source`;
- `provenance.tool`.

Every mapped hyperedge includes:

- the deterministic mapping rule;
- the source file that declared the relation;
- the exact declared repository path;
- provenance identifying the declaring source and mapper version.

These fields make a mapping challengeable without requiring an AI model to explain why it asserted the fact.

## Schema-gap table

The current `schemas/idkgraph.schema.json` can represent this P0 example without extension because `attributes` and `provenance` allow the mapping evidence to be retained. However, several facts are only weakly typed today:

| Deterministic fact | Current representation | Gap / risk | Proposed future direction |
| --- | --- | --- | --- |
| canonical repository-relative source path | `attributes.repository_path` + free-form `provenance.source` | no schema-level source-locator type or normalization rule | consider a typed `source_locator` object if multiple extractors need interoperability |
| mapping/extraction rule version | `attributes.mapping_method` + `provenance.tool` | names are free-form strings | define a typed derivation/mapping provenance vocabulary only after multiple real mappers exist |
| one semantic entity represented by a source file | source path stored as attributes/provenance | no first-class `represented_by` relation to a repository-file entity when the source itself is typed as decision/work_unit | revisit only if T5 needs both file and semantic nodes simultaneously |
| relation declaration evidence | `attributes.declared_in` / `declared_path` | evidence fields are not schema-required for deterministic relation classes | consider relation-specific evidence requirements after P0 usage data |

T3 intentionally **does not change the schema** merely to make these fields more formal. The current representation is valid and inspectable; the table records where future interoperability may justify a minimal extension.

## Negative mappings: what must not be automated yet

The following are tempting but are explicitly **heuristic** and excluded from T3:

- prose containing “supports” -> `supports` edge;
- prose disagreeing with another document -> `contradicts` edge;
- similar filenames or embeddings -> `duplicates` edge;
- a capitalized technical phrase -> `concept` node;
- a link in arbitrary prose -> `implements` edge;
- a confidence-sounding sentence -> graph `confidence`;
- repository popularity/activity -> correctness or verification evidence.

The synthetic ADR fixture deliberately contains the words `support`, `contradict`, `duplicate`, and `concept`; none may create semantic nodes or relations.

## Example sources

`examples/idkgraph.repository-mapping.example.json` is a compact subset grounded in real repository facts:

- `docs/architecture/IDKGRAPH_TASK_AND_EVOLUTION_MODEL.md` -> `document` using the T1 ID;
- `docs/decisions/ADR-0005-idkgraph-and-guarded-self-evolution.md` -> `decision`;
- `examples/work-units/phase0-smoke.work-unit.json` -> `work_unit` using source id `phase0/smoke-work-unit`;
- `schemas/idkgraph.schema.json`, `examples/idkgraph.example.yaml`, and the Phase 0 manifest -> `artifact` nodes;
- ADR-0005's explicit implementation-reference list -> `implements` edges;
- the Phase 0 Work Unit input locator -> `requires` edge.

The example is required to validate against the current IDKGraph schema and to be reproducible as a subset of the full repository mapper output.

## Non-goals

- no GitHub API data;
- no comments/reviews/issues ingestion;
- no semantic/NLP/LLM classification;
- no repository rewriting;
- no autonomous graph edits;
- no attempt to map every possible repository file type;
- no replacement for T1 identity, T2 navigation evidence, or T4 executable-cycle checks.

T5 may combine these deterministic primitives after their interfaces are stable.
