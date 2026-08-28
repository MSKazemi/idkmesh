# IDKGraph P0 Repository Observatory — Implementation Turn

Date: 2026-08-28

## Project-owner instruction

> Continue.

This continued the prior design work on IDKGraph, repository self-observation, and guarded self-evolution.

## Repository state inspected

Issue #20 already had three important follow-ups:

1. a proposal-first Repository Homeostasis Engine had been explored in PR #36, but that PR was closed without merge;
2. a GitHub collaboration/evidence observatory had been explored in PR #43, also closed without merge;
3. merged PR #85 had decomposed the remaining deterministic P0 observatory into five bounded tasks:
   - T1 stable Markdown/document identity;
   - T2 internal-link diagnostics;
   - T3 deterministic repository→IDKGraph mapping;
   - T4 executable WorkUnit dependency-cycle detection;
   - T5 unified graph/report/replay integration.

The implementation therefore continued the accepted decomposition instead of creating another observatory architecture.

## Implementation created

A feature branch `feature/idkgraph-p0-observatory` and PR #130 were created.

### `tools/idkgraph_observatory.py`

The new observation-only tool provides:

- deterministic Markdown document enumeration;
- deterministic ATX heading records and IDs;
- duplicate-heading anchor disambiguation;
- internal Markdown link extraction outside fenced code blocks;
- distinct deterministic findings for missing files and missing anchors;
- orphan-document warnings;
- explicit repository→IDKGraph mapping for:
  - Markdown documents;
  - ADR decision files;
  - files under `schemas/` and `examples/` as artifacts;
  - explicit `*.workunit.json` WorkUnits;
  - explicit WorkUnit dependencies;
- an executable dependency projection restricted to WorkUnits and executable dependency relations;
- deterministic cycle witnesses;
- deliberate allowance for cycles in non-executable knowledge relations;
- machine-readable graph JSON;
- human-readable Markdown health reports;
- commit/tool provenance and replay command;
- optional validation against `schemas/idkgraph.schema.json` using the existing Phase 0 `jsonschema` dependency.

The tool is intentionally conservative and does not infer contradiction, duplication, support, implementation, or supersession from prose.

### Tests

`tests/test_idkgraph_observatory.py` covers:

- repeated headings and Unicode heading identity;
- deterministic repeated scans;
- valid internal links;
- missing-file vs missing-anchor diagnostics;
- deterministic document/decision/artifact mapping;
- stable executable-cycle witnesses independent of input ordering;
- the key distinction that knowledge cycles do not become executable WorkUnit cycle failures;
- explicit WorkUnit JSON driving dependency-cycle detection.

### Mapping contract

`docs/architecture/IDKGRAPH_P0_DETERMINISTIC_MAPPING.md` records what may be mapped deterministically, current schema gaps, stable-ID rules, and negative examples of semantic relations that must not be guessed.

### CI

`.github/workflows/idkgraph-p0-observatory.yml` runs the deterministic test suite, validates emitted graph output against the IDKGraph JSON Schema, runs a repository scan, prints the report, and uploads graph/report artifacts. It has `contents: read` only and does not mutate the repository.

The first GitHub run of the new `IDKGraph P0 observatory` workflow completed successfully. The other visible PR check runs inspected also completed successfully, with no observed failed check run. GitHub reported PR #130 as mergeable.

## Integration decision

PR #130 was **not self-merged** by the same ChatGPT/GitHub actor that authored it.

Reason: Issue #35 and the repository's self-evolution architecture state the invariant:

> No autonomous actor may propose, approve, and merge the same protected change by itself.

The repository currently exposes no repository rulesets through the public rulesets endpoint, and Issue #35 still tracks external GitHub branch/ruleset protection as incomplete. Automated tests provide deterministic verification, but they are not an independent human authorization for a new self-observation/control-plane component.

Therefore the safe next integration step is independent maintainer review/authorization of PR #130, followed by merge through the repository's normal integration path.

## Next engineering steps after PR #130

If PR #130 is independently accepted, the next bounded work should be:

1. baseline the repository-health report and classify current deterministic findings;
2. promote only selected stable defect classes to required CI failures;
3. add explicit missing-WorkUnit-target diagnostics and a canonical WorkUnit source contract;
4. integrate repository structural graph output with the separate GitHub collaboration/evidence graph only after their evidence semantics are reconciled;
5. implement proposal-only graph rewrite candidates such as `AddMissingLink` and `GenerateIndex`, with before/after health vectors and no autonomous merge authority;
6. complete Issue #35's external `main` protection/ruleset configuration before increasing autonomous write capability.

## Public artifacts

- PR #130 — deterministic IDKGraph P0 repository observatory
- Issue #20 — parent repository-observatory research track
- Issue #35 — external protected-integration gate
