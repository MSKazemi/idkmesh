# Task Decomposition: IDKGraph P0 Repository Observatory

**Parent research track:** [#20 — Implement P0 IDKGraph repository observatory](https://github.com/MSKazemi/idkmesh/issues/20)  
**Growth Seed:** [#28 — decompose one research track into 5 claimable microtasks](https://github.com/MSKazemi/idkmesh/issues/28)  
**Architecture:** [`docs/architecture/IDKGRAPH_TASK_AND_EVOLUTION_MODEL.md`](../../architecture/IDKGRAPH_TASK_AND_EVOLUTION_MODEL.md)  
**Schema:** [`schemas/idkgraph.schema.json`](../../../schemas/idkgraph.schema.json)  
**Decision:** [`docs/decisions/ADR-0005-idkgraph-and-guarded-self-evolution.md`](../../decisions/ADR-0005-idkgraph-and-guarded-self-evolution.md)

## Purpose

Issue #20 is intentionally broad: turn the repository into a deterministic structural/semantic graph, detect repository-health defects, emit a human-readable report, and preserve provenance. This decomposition tests whether that research track can become easier to enter without requiring a newcomer to understand the entire self-evolution architecture.

This document defines **exactly five** independently claimable microtasks. The first four can proceed in parallel against small fixtures. The fifth is the integration/reporting task and depends on the interfaces produced by the first four.

Existing work such as PR #36 (Repository Homeostasis Engine) and the GitHub collaboration observatory is useful context, but these microtasks do not require contributors to complete or redesign those efforts. The focus here is the missing deterministic P0 repository-graph path from #20.

## Dependency DAG

```text
T1 Stable document + heading identity ----\
T2 Internal-link diagnostics -------------+--> T5 Unified graph/report/replay command
T3 Typed IDKGraph mapping ----------------+
T4 Executable dependency-cycle check -----/
```

There are no dependency edges among T1–T4. Each can be implemented and reviewed independently with its own fixtures. T5 may begin with fixture/stub inputs before all four predecessors land, but final acceptance requires the four output contracts to be consumable together.

## Fast chooser

| Task | Best fit | Expected size | Parallel attempts? | Depends on |
| --- | --- | ---: | --- | --- |
| T1 | Python / Markdown parsing | small | yes | none |
| T2 | testing / Markdown links | small | yes | none |
| T3 | schema / docs / graph modeling | small | yes | none |
| T4 | Python / graph algorithms | small | yes | none |
| T5 | integration / CLI / reporting | medium | yes, with fixture inputs | T1–T4 |

---

## T1 — Deterministic Markdown document and heading identity

### Newcomer context

IDKGraph needs stable identities so a document or section can be referenced even when other parts of the repository are scanned in a different order. The full IDKGraph architecture is much larger, but this task is only about one deterministic input boundary: Markdown files and headings. A contributor does not need to understand scheduling, AI agents, community growth, or self-evolution to complete it.

### Objective

Build a deterministic extractor that enumerates repository Markdown documents and headings and assigns reproducible IDs using a documented rule. The rule must not depend on filesystem traversal order, wall-clock time, or random state.

### Expected artifact

A small standard-library implementation or focused module plus tests/fixtures that emits records containing at least:

- repository-relative document path;
- heading text;
- heading level;
- deterministic heading/document ID;
- source line where practical;
- enough information to distinguish repeated heading text in one document.

If an existing observatory module is the canonical location by implementation time, extend it rather than creating a competing full observatory.

### Maximum / expected scope

- Target roughly one parsing module/function and a compact fixture set.
- No Markdown renderer is required.
- No semantic NLP, embeddings, or LLM classification.
- Do not rewrite headings in repository documents merely to create IDs.

### Dependencies

None.

### Acceptance test / evidence

Provide deterministic fixture evidence covering at least:

1. two Markdown files with multiple heading levels;
2. repeated identical heading text in the same file;
3. headings containing punctuation or Unicode;
4. the same fixture scanned twice with identical output bytes or identical normalized records;
5. a changed heading/path producing a predictably changed identity according to the documented rule.

The PR should state the ID rule explicitly and include the exact test command.

### Helpful skills, not required

Python, Markdown syntax, deterministic data processing, basic testing.

### Are parallel attempts useful?

**Yes.** Alternative ID rules are useful to compare as long as each attempt documents stability trade-offs. Multiple attempts should not all be merged; they provide evidence for selecting the simplest adequate rule.

---

## T2 — Internal-link and missing-target diagnostic fixtures

### Newcomer context

A repository becomes difficult to navigate when links silently break. Issue #20 treats broken internal links and missing referenced files as deterministic health defects. This task isolates that behavior from every other graph feature: given Markdown files, determine whether repository-relative links and anchors resolve, and report failures precisely.

### Objective

Implement or strengthen a repository-internal link checker with explicit diagnostic categories. It should distinguish at least missing files from missing anchors instead of returning only one generic failure count.

### Expected artifact

A focused link-checking function/module plus a valid fixture tree and a deliberately broken fixture tree. Machine-readable findings should include at least:

- source document;
- raw/internal target;
- normalized target path;
- target anchor when present;
- finding category;
- severity (`error` for deterministic broken targets; warnings only when the condition is not provably broken).

### Maximum / expected scope

- Repository-local Markdown links only.
- No network requests and no external-URL availability checker.
- No attempt to judge whether a valid link is semantically useful.
- Keep parsing conservative; unsupported syntax should be reported or skipped explicitly rather than guessed.

### Dependencies

None. T2 may use its own tiny fixture path/heading index and can later adapt to T1's interface.

### Acceptance test / evidence

Fixtures must demonstrate observable outcomes for:

1. a valid relative file link;
2. a valid same-document anchor;
3. a valid cross-document anchor;
4. a missing target file;
5. an existing target file with a missing anchor;
6. a path containing spaces or URL-style escaping if the chosen parser supports it;
7. a valid fixture producing zero deterministic link errors.

The broken fixture must produce non-zero actionable findings with stable ordering.

### Helpful skills, not required

Testing, Markdown links, path normalization, Python standard library. This is intentionally accessible to contributors who are not familiar with the distributed-agent architecture.

### Are parallel attempts useful?

**Yes.** Parallel attempts can compare conservative parsers or fixture coverage. Prefer the implementation with clearer deterministic behavior over the one that recognizes the most syntax heuristically.

---

## T3 — Deterministic repository-to-IDKGraph type mapping and schema-gap fixture

### Newcomer context

The IDKGraph schema already defines node types such as `document`, `decision`, `work_unit`, `artifact`, and `concept`, plus typed relations such as `documents`, `implements`, `depends_on`, and `supersedes`. What is not yet fully specified is which repository facts can be mapped to those types **deterministically** without asking an AI model to infer meaning from prose. This task is primarily a modeling/schema exercise and is suitable for a contributor who prefers documentation, data modeling, or research over core implementation.

### Objective

Define and demonstrate the smallest deterministic mapping from explicit repository structures into valid `idkgraph.schema.json` nodes/hyperedges.

### Expected artifact

Add a short mapping specification plus one machine-readable example fixture. The mapping should cover at least:

- Markdown document -> `document` node;
- an explicitly identified architecture decision file -> `decision` node;
- a canonical Work Unit fixture -> `work_unit` node where the source format exposes a stable identifier;
- a repository artifact/schema/example -> `artifact` node;
- at least two deterministic relations sourced from explicit links/metadata.

The artifact must include a **schema-gap table**: if the current `idkgraph.schema.json` cannot represent a required deterministic fact cleanly, document the gap rather than silently inventing an incompatible field.

### Maximum / expected scope

- One mapping document and one or a few compact JSON/YAML examples/tests.
- Do not infer `concept`, `contradicts`, `duplicates`, or semantic `supports` relations from arbitrary prose.
- Do not redesign the full schema unless a minimal extension is separately justified.
- No GitHub API collection; this is repository-state mapping only.

### Dependencies

None. It can use hand-authored fixture records rather than waiting for T1/T2 extraction code.

### Acceptance test / evidence

The contribution is complete when:

1. the example graph validates against the current schema, **or** validation fails only at explicitly documented schema gaps with a minimal proposed extension;
2. every node/relation in the fixture has a traceable repository source;
3. a reviewer can tell whether each mapping is deterministic or heuristic;
4. no heuristic semantic inference is presented as deterministic truth;
5. at least one negative example explains a tempting mapping that should *not* be automated yet.

### Helpful skills, not required

JSON Schema, graph/data modeling, technical writing, repository architecture. Coding is optional.

### Are parallel attempts useful?

**Yes.** Competing mapping tables are useful research evidence, especially when they disagree about what can safely be inferred. The review should favor explicit, conservative semantics.

---

## T4 — Cycle detection for the executable WorkUnit projection

### Newcomer context

IDKGraph itself is allowed to contain cycles because knowledge can be contradictory or mutually referential. The **executable task projection** is different: unresolved prerequisite cycles can deadlock work. This task deliberately ignores the rest of the knowledge graph and checks only whether the WorkUnit dependency projection is executable as a DAG for the supported dependency relations.

### Objective

Implement a deterministic cycle checker for a small IDKGraph/WorkUnit fixture, restricted to executable dependency semantics.

### Expected artifact

A small graph-checking function/module and fixtures containing:

- an acyclic WorkUnit dependency graph;
- a direct two-node cycle;
- a longer cycle;
- a global knowledge-graph cycle that is intentionally **not** an executable dependency cycle.

The checker should emit a stable cycle witness/path rather than only `true/false` when a cycle exists.

### Maximum / expected scope

- Standard-library graph traversal is sufficient.
- Only explicitly supported WorkUnit dependency relations should enter the executable projection.
- No scheduler, Petri-net engine, critical-path optimizer, or distributed execution runtime.
- AND/OR execution semantics may be represented in fixtures/documentation, but full AND/OR readiness evaluation is not required for this microtask.

### Dependencies

None. Consume a minimal hand-authored graph fixture that already matches the IDKGraph schema or a clearly documented subset.

### Acceptance test / evidence

Tests must prove that:

1. an acyclic WorkUnit graph passes;
2. each seeded executable cycle fails and returns a stable witness;
3. non-WorkUnit/knowledge relations do not create false executable-cycle errors;
4. output is deterministic regardless of input node ordering;
5. the algorithm does not mutate the graph while checking it.

### Helpful skills, not required

Graph algorithms, Python, test design. A standard DFS/Kahn-style implementation is sufficient; no advanced graph library is required.

### Are parallel attempts useful?

**Yes.** DFS witness extraction and topological-sort approaches can be compared. Prefer clarity, deterministic diagnostics, and minimal dependencies over algorithmic novelty.

---

## T5 — One-command P0 graph/report/replay integration

### Newcomer context

The parent issue is only useful if contributors can run the observatory and understand what it found. This final microtask combines the already-defined deterministic boundaries into one user-facing command and report. It does not add autonomous repair. Its job is to make evidence reproducible: same repository snapshot, same tool version, same graph/report semantics.

### Objective

Integrate the P0 extraction/check interfaces into one local command that emits both a machine-readable IDKGraph artifact and a human-readable repository-health report with provenance.

### Expected artifact

A CLI/integration path plus tests that produce at least:

- IDKGraph JSON or a documented schema-compatible graph artifact;
- Markdown health report;
- repository/source revision used for the scan when available;
- tool/version identifier;
- deterministic finding counts grouped by severity/category;
- references from report findings back to source paths/IDs;
- a documented replay command.

If PR #36's observatory is the accepted canonical tool by implementation time, extend its interface instead of introducing a second competing repository scanner.

### Maximum / expected scope

- Integrate deterministic P0 evidence only.
- No automatic fix, file move, deletion, merge, issue creation, or policy rewrite.
- No LLM semantic contradiction/duplication detector.
- No GitHub collaboration/evidence API graph; that is a separate P1 surface.
- Report metrics as observations, not as proof that a higher/lower number is inherently better.

### Dependencies

Final acceptance depends on T1, T2, T3, and T4 contracts being consumable together. Implementation can start earlier with fixture/stub outputs.

### Acceptance test / evidence

The integration contribution is complete when one documented command can be run against:

1. a deliberately valid fixture/repository snapshot and produce zero seeded deterministic errors;
2. a deliberately broken fixture and produce non-zero actionable findings for at least two P0 defect classes;
3. the same fixed snapshot twice and produce semantically identical graph/findings (timestamps may be normalized or excluded from byte-for-byte comparison);
4. an output graph that validates against `schemas/idkgraph.schema.json`, except for any separately reviewed/documented minimal schema extension;
5. a report that clearly distinguishes deterministic errors, warnings, and research hypotheses.

The PR must include a short replay section with the exact command(s) and expected high-level result.

### Helpful skills, not required

CLI design, integration testing, technical writing, Python. Documentation/testing contributors can improve report clarity and replay instructions even if another contributor implements the plumbing.

### Are parallel attempts useful?

**Yes, before final selection.** Competing report layouts or CLI shapes can be tested with newcomers. Only one canonical integration path should ultimately remain.

---

## What this decomposition intentionally leaves out

The five microtasks stop at the deterministic P0 observatory boundary. They intentionally do **not** include:

- autonomous repository rewrites, moves, deletions, or merges;
- LLM-based contradiction, duplicate, or semantic-importance judgments;
- GitHub collaboration/evidence ingestion and the P1 union tracked elsewhere;
- community-growth scoring or ACE actuation;
- branch-protection administration;
- distributed scheduling or worker execution;
- a full Petri-net, e-graph, or provenance database implementation;
- proposal rules such as `ArchiveSuperseded` or `TaskDecomposition` themselves;
- bulk restructuring of the repository.

Those are valid follow-up research areas, but including them here would make the microtasks cease to be newcomer-sized and independently reviewable.

## Review test for this decomposition

A reviewer unfamiliar with the complete project should pick any one of T1–T4, read only that section plus its immediate links, and answer these questions:

- What artifact would I change or add?
- What is explicitly outside scope?
- What deterministic evidence proves completion?
- Can I start without completing the other four tasks?

For T5, the reviewer should additionally be able to identify its four predecessor interfaces from the DAG.

If those answers are not obvious, the decomposition should be refined before spawning descendant GitHub issues. The goal of #28 is not to manufacture five more tracker items; it is to reduce the activation energy for five genuinely bounded contributions.
