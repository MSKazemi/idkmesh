# IDKGraph P0 Observatory v0.1

Status: experimental integrated P0 observatory  
Parent: issue #20, decomposition #85 T5  
Authority: read-only evidence generation

## Purpose

T1–T4 establish deterministic primitives. T5 composes them into one local command that a contributor can run against a fixed repository snapshot and inspect without granting the observatory any repair or integration authority.

Canonical command:

```bash
python tools/idkgraph_observatory.py . \
  --output-dir /tmp/idkgraph-observatory \
  --pretty
```

The output directory must be outside the scanned repository tree. This is a correctness rule, not a convenience preference: allowing generated reports inside the scan root would make the observatory observe its own previous output and break clean replay semantics.

## Composed contracts

The observatory imports rather than reimplements:

- T1 Markdown identity, transitively consumed by T2 and T3;
- T2 `tools/idkgraph_link_check.py` for local Markdown integrity and canonical source/target IDs;
- T3 `tools/idkgraph_repository_mapping.py` for the schema-compatible typed repository graph;
- T4 `tools/idkgraph_workunit_cycles.py` for executable WorkUnit dependency-cycle checking.

No second document identity, Markdown parser, repository type mapper, or executable-cycle algorithm is introduced in T5.

## Output artifacts

One run emits exactly these canonical artifacts:

### `idkgraph.json`

The T3 graph artifact. It must validate against `schemas/idkgraph.schema.json` for the current P0 mapping contract.

### `observatory.json`

A deterministic evidence summary containing:

- tool/contract versions;
- immutable source revision when available;
- graph node/hyperedge counts and node-type counts;
- SHA-256 of the canonical normalized graph JSON;
- T2 navigation summary;
- T4 executable-projection summary and cycle witness when applicable;
- deterministic findings grouped by severity and category;
- source path plus mapped graph ID when available;
- an explicit empty `research_hypotheses` list in P0;
- an explicit read-only authority declaration.

### `repository-health.md`

A human-readable rendering of the same evidence. It separates:

1. deterministic errors;
2. deterministic warnings;
3. research hypotheses.

The third section intentionally states that deterministic P0 emits no research hypotheses automatically. Semantic contradiction, duplication, importance, or “health value” judgments remain outside this layer.

## Provenance

When the selected scan root is itself a Git worktree root, the observatory records exact `HEAD` as `source_revision` with method `git_head`.

When scanning an extracted/non-Git fixture or archive, callers may bind provenance explicitly:

```bash
python tools/idkgraph_observatory.py snapshot/ \
  --output-dir /tmp/idkgraph-snapshot \
  --source-revision sha256:EXTERNAL_SNAPSHOT_DIGEST
```

T5 emits no current timestamp. A fixed tree plus fixed source revision and tool version should therefore replay deterministically.

## Integrated finding model

T2 findings are normalized without changing their original category or severity. T5 adds the mapped T3 `source_id` when the source path has a deterministic graph node.

If T4 reports an executable cycle, T5 emits one additional deterministic error:

`executable_workunit_cycle`

with the stable T4 cycle witness preserved as evidence.

T5 does not convert T4 `ignored_hyperedges` into errors merely because they are outside the executable projection. They remain inspectable execution metadata.

## Acceptance fixtures

### Clean fixture

`tests/fixtures/idkgraph_observatory/valid/`

Contains two Markdown documents with one valid anchored local link and one canonical WorkUnit. Expected high-level result:

- zero deterministic errors;
- zero deterministic warnings;
- one executable WorkUnit;
- no executable cycle;
- graph validates current schema.

### Broken fixture

`tests/fixtures/idkgraph_observatory/broken/`

Seeds two independent P0 defects:

- missing Markdown file;
- existing Markdown file with missing anchor.

Expected high-level result: two deterministic errors in two separate actionable categories. The command still writes evidence before returning non-zero when `--fail-on-errors` is requested.

## Replay protocol

For a fixed snapshot, run twice into different external directories:

```bash
python tools/idkgraph_observatory.py . --output-dir /tmp/idkgraph-a --pretty
python tools/idkgraph_observatory.py . --output-dir /tmp/idkgraph-b --pretty

cmp /tmp/idkgraph-a/idkgraph.json /tmp/idkgraph-b/idkgraph.json
cmp /tmp/idkgraph-a/observatory.json /tmp/idkgraph-b/observatory.json
cmp /tmp/idkgraph-a/repository-health.md /tmp/idkgraph-b/repository-health.md
```

All three artifacts should be byte-identical when repository bytes, tool version, source revision, and formatting mode are unchanged.

## Failure behavior

`--fail-on-errors` changes only the process exit status. Evidence artifacts are written first so failed runs remain inspectable.

The default remains observational because an existing repository may contain historical deterministic debt that should be measured before it becomes a merge gate. A future policy may decide where fail-closed enforcement belongs, but that policy is not hidden inside the P0 observer.

## Non-goals

- no automatic repair;
- no file move/delete/archive action;
- no issue/PR creation;
- no GitHub API mutation;
- no semantic contradiction/duplicate detector;
- no P1 GitHub collaboration graph ingestion;
- no scheduler or task execution;
- no claim that repository-health counts are themselves optimization objectives;
- no autonomous approval, push, merge, or governance change.

T5 completes the deterministic P0 observatory integration boundary. Any future actuator should consume its evidence through a separately reviewed policy and authorization layer.
