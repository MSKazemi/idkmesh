# Issue #15 Work Unit composability implementation

**Date:** 2026-08-29
**Issue:** <https://github.com/MSKazemi/idkmesh/issues/15>

## Request

The project owner requested parallel, professional resolution of ten unclaimed
issues, including remote branches, pull requests, verification, and eventual
integration. This workstream was assigned issue #15 and was explicitly limited
to opening a non-draft pull request rather than merging it directly.

## Repository audit

Current `main` already contained WorkUnit v0.2, historical v0.1, worker result
and independent verification contracts, deterministic validators, A2A/MCP
lossless round-trip bindings, and a protocol mapping matrix. Replacing or
expanding those schemas would have duplicated accepted semantics and risked
breaking historical artifacts.

The missing bounded delta was:

- a runnable versioned five-strategy decomposition benchmark;
- exact definitions for the primary issue #15 metrics;
- a canonical example DAG spanning coding, testing, research, and review;
- fail-closed cross-document validation of formal WorkUnit dependencies and
  evidence requirements.

## Implementation decision

Keep WorkUnit v0.1 and v0.2 unchanged. Add a separate v0.1 benchmark contract,
a deterministic read-only validator/aggregator, four v0.2 examples, focused
tests, documentation, and CI coverage.

The committed fixture is labeled `synthetic_fixture`. Its observations prove
only that validation and aggregation are reproducible; they do not support a
claim about which decomposition strategy performs best. Real controlled worker
runs must use `evidence_class: observed` and preserve raw observations and
provenance.

## Safety and authority

The validator resolves referenced files only within the repository, validates
formal units against WorkUnit v0.2, rejects unknown dependencies and cycles,
and never executes declared commands. It has no dispatch, acceptance, write,
push, or integration authority.

## Community impact

The change gives contributors a small, inspectable way to add comparable real
runs and shows four common roles without requiring them to infer the full
repository architecture. The evidence label is designed to prevent example
numbers from being mistaken for scientific findings.

## Open research work

Run the five arms with independently assigned workers, controlled context,
shared hidden tests, preregistered assignment, and recorded human integration
time. Replicate across multiple task classes before changing the WorkUnit core.
