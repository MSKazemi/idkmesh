# IDKGraph P0 Deterministic Repository Mapping

Date: 2026-08-28
Status: implementation contract for Issue #20

## Rule

The P0 observatory maps only facts that are explicit in repository structure or explicit machine-readable metadata. It must not infer semantic truth from prose.

## Deterministic mapping table

| Repository fact | IDKGraph representation | Evidence source | P0 confidence |
| --- | --- | --- | --- |
| Markdown file | `document` node | repository-relative path + parsed title | deterministic |
| Heading in Markdown | stored document heading record with deterministic ID | file path + GitHub-style anchor occurrence | deterministic within this parser contract |
| `docs/decisions/ADR-*.md` | `decision` node | explicit path convention | deterministic |
| ADR file describing its decision node | `documents` hyperedge | path convention | deterministic |
| File below `schemas/` or `examples/` | `artifact` node | repository-relative path | deterministic |
| Resolved internal Markdown link from document to mapped document/artifact | `mentions` hyperedge | explicit Markdown link | deterministic syntactic relation only |
| `*.workunit.json` with `type: work_unit`, explicit `id`, and `title` | `work_unit` node | explicit machine-readable metadata | deterministic |
| `depends_on` / `requires_all` in an explicit WorkUnit file | `depends_on` hyperedge | explicit machine-readable metadata | deterministic |

## Stable identity rule

P0 generated IDs use a namespaced SHA-256 digest truncated to 20 hexadecimal characters:

`id = namespace + ':' + sha256(canonical_parts_joined_with_unit_separator)[0:20]`

Examples of canonical parts:

- document: repository-relative POSIX path;
- heading: document path + resolved heading anchor;
- generated relation: source ID + relation + target ID + explicit source-location discriminator where needed.

This rule is deterministic, independent of filesystem traversal order, wall-clock time, or random state. A document move intentionally changes its generated structural ID in P0. Long-lived semantic IDs for concepts that must survive moves should be explicit metadata in a later layer rather than hidden heuristics.

## Markdown heading boundary

The implementation recognizes ATX headings (`#` through `######`) outside fenced code blocks. It uses a conservative GitHub-style slug approximation, retaining Unicode alphanumeric characters and applying duplicate suffixes (`-1`, `-2`, ...).

This is an explicit parser contract, not a claim to implement every CommonMark/GFM edge case. Unsupported syntax should become a documented limitation or warning rather than guessed semantics.

## Link semantics

A syntactically resolved Markdown link means only:

> this document explicitly references this repository object.

It does **not** mean:

- supports;
- verifies;
- implements;
- contradicts;
- supersedes;
- duplicates.

Those stronger relation types require explicit metadata or a separately reviewed evidence rule.

## Schema-gap table

| Desired fact | Current schema status | P0 decision |
| --- | --- | --- |
| Document headings as first-class nodes | Node type could use `concept`, but that would assert semantics | keep headings in document `attributes` for P0 |
| Stable semantic identity across file moves | schema permits explicit IDs but repository lacks universal metadata | generated path identity now; later explicit semantic IDs |
| Exact source line on provenance | provenance object permits additional fields but no canonical `line` property | store source line in relation/document attributes |
| Link relation that means only syntactic hyperlink | no `links_to` relation exists | use conservative `mentions`; consider `links_to` in a later schema revision |
| WorkUnit OR prerequisites | schema can encode hyperedges but WorkUnit source contract is not standardized yet | P0 loads `depends_on` / `requires_all`; OR readiness remains out of scope |
| Explicit document-to-decision declaration independent of path | schema can represent it; source metadata convention is missing | use ADR path convention in P0 and define metadata later |

## Negative examples

The P0 observatory must **not** infer the following from prose similarity or filenames:

- two documents discuss the same concept -> `duplicates`;
- one document cites another -> `supports`;
- an issue/ADR mentions code -> `implements`;
- two statements disagree linguistically -> `contradicts`;
- an old-looking file -> `superseded`.

Those are semantic judgments. They may later be proposed by agents, but they cannot enter the deterministic evidence layer without explicit verification.

## Executable projection rule

IDKGraph itself may contain cycles. The P0 executable cycle checker projects only `work_unit` nodes and explicitly executable prerequisite relations (`depends_on`, `requires`). Knowledge relations such as `contradicts` do not participate in the executable DAG check.

## Implementation

Canonical P0 implementation:

- `tools/idkgraph_observatory.py`
- `tests/test_idkgraph_observatory.py`

Replay:

```bash
python -m unittest tests.test_idkgraph_observatory -v
python tools/idkgraph_observatory.py \
  --root . \
  --graph-out results/idkgraph/graph.json \
  --report-out results/idkgraph/report.md \
  --schema schemas/idkgraph.schema.json
```

The observatory is read-only with respect to repository/GitHub state. It emits evidence; it does not repair, move, delete, merge, or authorize changes.
