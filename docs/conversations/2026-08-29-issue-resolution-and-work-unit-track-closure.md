# Conversation record — issue resolution and Work Unit track closure

**Date:** 2026-08-29  
**Repository:** `MSKazemi/idkmesh`

## User instruction

The project owner asked:

> Can you solve the issues and merge to the main branch?

## Live repository audit

The repository was re-read before making changes.

Observed state:

- `main` is now protected and requires the Phase 0 gate checks on Python 3.11 and 3.13;
- there were no open pull requests at the beginning of this pass;
- several open issues are intentionally human-, community-, or experiment-gated and cannot be truthfully closed by automation alone;
- historical canonical-node PR #159 is closed unmerged and its separate-human-review issue #138 remains open, so that worker boundary must not be bypassed;
- issue #15 remained open even though the repository already contains WorkUnit v0.1/v0.2, ResultManifest, VerificationResult, EvaluatorPlan, decomposition benchmark, graph, and provenance contracts.

## Selected bounded issue

Issue #15 — **Research Track 3: Define a formal Work Unit for composable distributed work** — was selected because its protocol-definition deliverables have materially converged while its remaining hypotheses are empirical research questions.

The change does not introduce another protocol. It records the current canonical boundary:

```text
Goal / project policy
  -> WorkUnit v0.2
  -> worker adapter
  -> ResultManifest v0.1
  -> verifier-owned EvaluatorPlan
  -> VerificationResult v0.1
  -> explicit integration decision
```

A2A, MCP, OpenHands, mini-SWE-agent, local nodes, and future adapters should map into this semantic contract rather than redefine it.

## Safety and governance boundaries preserved

This pass does **not**:

- pretend to provide the separate human review required by #138;
- activate ACE autonomous actuation;
- treat CI success as independent approval;
- create a new Work Unit schema merely to close an issue;
- merge stale branches wholesale;
- claim the remaining Work Unit hypotheses are empirically proven.

The closure map explicitly separates completed protocol-definition work from open empirical questions such as optimal granularity, uncertainty/rework effects, context/coordination trade-offs, and decomposition strategy performance.

## Integration procedure

A fresh branch was created from current protected `main`:

`closure/work-unit-research-track-15`

The branch adds:

- `docs/research/WORK_UNIT_RESEARCH_TRACK_COMPLETION.md`;
- this conversation record.

The intended integration path is a normal pull request against `main`, exact-head CI verification, and merge only if the required protected-main checks pass.
