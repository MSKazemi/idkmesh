# Repository-wide code/documentation correctness audit

**Date:** 2026-08-29  
**Baseline:** `649df7b77ac7ab690f15f88e8eac2d4291d1edb8`  
**Scope:** repository tree, primary code/contract surfaces, public README, architecture/roadmap/navigation documentation, live issue references, and protected-main validation.

## User instruction

The project owner asked to check the repository's code/files broadly and improve/correct the README and documentation.

## Audit method

This was a repository-wide structural/correctness pass rather than an attempt to rewrite every historical record.

The audit:

1. pinned the current protected `main` revision;
2. inventoried the full Git tree and top-level responsibility areas;
3. inspected the public README and primary canonical documents;
4. compared old roadmap/architecture claims with current schema, interop, simulation, experiment, script, test, and workflow surfaces;
5. checked live status for README-linked contribution issues;
6. inspected the stable protected-main PR gate to align local verification instructions with CI;
7. preserved historical evidence instead of rewriting archival conversations/findings merely because terminology evolved;
8. changed current canonical navigation/status documents where the repository had materially outgrown their wording.

Final correctness is also delegated to the repository's deterministic full test suite and Markdown link-integrity check on the exact pull-request head.

## Repository surfaces inspected

### Integration and CI

- protected `main` metadata and required checks;
- `.github/workflows/` inventory;
- stable `.github/workflows/pr-gate.yml` behavior;
- GitHub-native ACE, IDKGraph, CI shadow, benchmark, evidence, and evolution workflows.

### Executable research/control code

- `scripts/` repository/community/evolution control and analysis inventory;
- `sim/` simulation/analysis inventory;
- `experiments/` experiment definitions and executable tooling inventory;
- `tests/` regression/contract test inventory;
- `tools/` role through the documented PR gate/link checks.

### Protocol and interoperability

- `schemas/` inventory and `schemas/README.md`;
- current WorkUnit v0.2 / ResultManifest / VerificationResult semantics;
- `interop/` inventory;
- `interop/adapters.py` coordinator-facing `WorkerAdapter`, local adapter, A2A mock lifecycle, ResultManifest normalization, and acceptance boundary;
- A2A/MCP mapping/conformance surfaces.

### Project/documentation structure

- root README and primary project documents;
- `docs/` category inventory;
- `docs/README.md`;
- architecture index;
- project identity document;
- current roadmap/evolution/iteration vocabulary relationship;
- live starter/review issue references.

## Findings

### F1 — README understated the executable foundation

The README described the repository mainly as an exploration/early-community phase even though `main` now contains a large executable schema, simulation, experiment, interop, observability, CI/evolution, and community-control foundation.

**Correction:** describe the current state as an executable research foundation while explicitly stating that the end-user Verified Swarm Runner and distributed mesh remain incomplete.

### F2 — README mixed target architecture with current product capability

The target runner lifecycle was phrased in a way that could be read as an already packaged multi-worker product.

**Correction:** separate `already present on main` from `not yet a finished capability`, and present the runner flow as the reference-product target.

### F3 — root issue links used inappropriate relative paths

The root README used `../../issues/...` paths for live GitHub issues. Root-level repository Markdown should not rely on those directory-relative paths.

**Correction:** use explicit repository issue URLs for live contribution/observatory references.

### F4 — `ARCHITECTURE.md` was materially stale

The old architecture document ended by saying the first prototype should start with a single-machine simulation. The repository has already progressed through substantial schema, verification, simulation, interoperability, repository-evolution, and GitHub-native implementation work.

**Correction:** replace the old provisional sketch with a current high-level architecture map that preserves the authority boundary:

```text
WorkUnit
 -> worker candidate/ResultManifest
 -> verifier-owned EvaluatorPlan
 -> independent VerificationResult
 -> evidence/reporting
 -> explicit integration decision
```

### F5 — `ROADMAP.md` contained an obsolete immediate backlog and proposed tree

The previous roadmap still listed creation of first WorkUnit/ResultManifest/Goal Graph schemas, simulator, scheduler primitives, etc. as immediate next artifacts, and proposed a `src/...` tree that does not match the evolved repository.

**Correction:** rebase the roadmap on the implemented foundation and make current gates about real execution evidence, heterogeneous adapters, controlled benchmark runs, reproducible release UX, independent review, and later earned scale.

### F6 — documentation lacked a sufficiently explicit authority hierarchy

The repository intentionally retains large historical/audit/conversation collections. Without an authority map, a newcomer can mistake an old plan, experiment note, or conversation for current behavior.

**Correction:** make `docs/README.md` explain which surfaces are current protocol truth, current architecture, research evidence, audits, findings, decisions, and append-only history.

### F7 — `docs/WHAT_IS_IDKMESH.md` used future tense for self-hosting that is already happening

The project identity document said the first practical project “should be” IDKMesh improving IDKMesh and described the implementation as future-focused, while the repository already contains self-observation/evolution/community experiments.

**Correction:** update the document to distinguish the existing self-hosting experiment from the still-unfinished general framework/product.

## What was deliberately not changed

- historical conversation records were not rewritten to match current terminology;
- old findings/audits were not edited merely because later work superseded them;
- research hypotheses were not promoted into conclusions;
- no production-scale claim was added;
- no code authority or integration behavior was changed in this documentation pass;
- no independent-human-review requirement was replaced by automated evidence.

## Documentation rules established by this pass

1. **Current contracts beat historical plans.** Machine-readable schemas and current specifications define protocol behavior.
2. **Implementation is not scientific proof.** Synthetic fixtures/simulations must remain distinguishable from observed evidence.
3. **Target product is not present capability.** Reference-product flows must say when they are targets or partial implementations.
4. **Archive is evidence, not current authority.** Preserve history but route newcomers through curated canonical surfaces.
5. **Scale claims require scale evidence.** Small/synthetic results cannot become Internet-scale guarantees by documentation wording.
6. **Generators/verifiers do not self-promote authority.** Worker success, CI, statistical scores, and verifier recommendations remain separate from independent review/governance/integration decisions.
7. **Docs follow code and gates.** When current behavior changes, update the smallest canonical current document and leave historical evidence intact.

## Files changed by this audit

- `README.md`
- `ARCHITECTURE.md`
- `ROADMAP.md`
- `docs/README.md`
- `docs/WHAT_IS_IDKMESH.md`
- this audit record

## Acceptance gate

The change is documentation-focused but still requires the exact same protected-main validation as code changes:

```text
PR gate Python 3.11
AND PR gate Python 3.13
AND deterministic Markdown link integrity
```

Additional repository observatory/evolution workflows should also remain green where they apply. A failing check is evidence to correct the documentation rather than a reason to bypass the gate.
