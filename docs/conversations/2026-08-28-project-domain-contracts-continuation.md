# ProjectManifest / DomainPack continuation

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`  
**Tracking issue:** #6

## User direction

The project owner asked the assistant to continue improving IDKMesh and to preserve substantive work in the public repository.

This continuation first inspected the live repository rather than creating more speculative machinery. It found that several major remaining boundaries were external or human:

- `main` still reports `protected: false` and the repository rulesets collection is empty, so issue #35 remains an administrator-owned P0;
- PR #159 still has no submitted human review and issue #138 explicitly requires a genuinely separate human witness;
- IDKGraph warning issue #152 already completed its deterministic sample/classification/correction and now waits on trustworthy independent reviewer-attention evidence.

The next internally solvable P0 was therefore issue #6: make the architectural boundary `Core -> DomainPack -> Project` executable rather than only conceptual.

## Design decision

Implement a small declarative v0.1 contract instead of a plugin framework.

```text
IDKMesh Core
    |
    v
DomainPack
    |
    v
ProjectManifest
```

The important property is **policy composition without executable authority**.

A ProjectManifest can select/narrow domain rules. A DomainPack can require verification/evidence/adapters. Neither document can dynamically import code, grant a worker acceptance authority, merge a pull request, configure GitHub protection, resolve a secret, or execute project-supplied commands.

## Added contracts

### ProjectManifest

`schemas/project-manifest.schema.json`

The manifest declares:

- project identity/version;
- exact Core/WorkUnit compatibility;
- roots and Goal entrypoints;
- exact DomainPack references;
- allowed Work Unit kinds;
- verification and risk policy;
- integration/governance policy;
- metrics;
- worker capability constraints;
- storage/provenance roots;
- enabled adapter IDs.

### DomainPack

`schemas/domain-pack.schema.json`

The pack declares:

- domain identity/version;
- exact Core/WorkUnit compatibility;
- supported Work Unit kinds;
- verification requirements;
- worker roles/capabilities;
- risk classes;
- adapter interface IDs, discovery mode, and trust boundary;
- default metrics;
- explicit compatibility/breaking-change policy.

## Software-engineering reference pack

`examples/domain-packs/software-engineering-v0.1.domain-pack.json`

The pack remains forge/model/vendor neutral. It describes capabilities such as repository read/edit, test execution, and deterministic execution rather than naming a particular model provider.

Its reusable policies distinguish coding/testing/review/benchmark/documentation/research/integration paths and preserve the core trust rule:

```text
worker success != acceptance
verification evidence != merge authority
```

Required adapters include a repository interface and metadata verifier. The sandbox worker is optional at the DomainPack level because projects may be evidence-only/read-only.

## Two distinct projects on the same Core

Two ProjectManifests deliberately bind to the same Core API `0.1`, WorkUnit schema `0.2`, and software-engineering DomainPack `0.1.0`.

### `project.idkmesh-self-improvement`

Allows bounded coding/testing/review/benchmarking/documentation/research/integration. Default code-change verification requires an independent verifier. Integration is protected-PR/human-decision based. Automatic merge is false and autonomous risk is capped at low.

### `project.idkmesh-research-replication`

Uses the same Core/DomainPack but is repository-read-only, proposal-only, and permits only research/benchmark/documentation/review Work Units. Maximum autonomous risk is `none` and repository write/merge authority is explicitly forbidden.

This gives a concrete test of the framework claim:

```text
same Core + same domain rules
        |
        +-- project policy A: bounded self-improvement
        +-- project policy B: read-only research replication
```

## Compatibility decision

v0.1 uses exact matching:

```text
Core API       == 0.1
WorkUnit schema == 0.2
Project compatibility == every referenced DomainPack compatibility
DomainPack ref id/version == loaded document id/version
```

There is intentionally no semver range solving, best-effort downgrade, or remote pack fetching yet.

Historical evidence is bound to exact contract versions; changed semantics require explicit versioning/rebinding rather than silently inheriting acceptance.

## Multi-pack behavior

The validator permits future multi-DomainPack projects but fails closed on ambiguity:

- duplicate pack IDs fail;
- same verification-policy ID with different definitions fails;
- same adapter ID with different definitions fails;
- required adapters from every pack remain required;
- project Work Unit/risk choices must be supplied by the referenced packs.

Load order therefore cannot become hidden policy authority.

## Adapter discovery boundary

A DomainPack declares stable adapter IDs and interface IDs such as:

```text
software.metadata-verifier
idkmesh.adapter.verifier/v0.1
```

The manifest enables adapter IDs only.

`experiments/project_contracts.py` never dynamically imports an adapter name or treats it as a package/module/command/URL. Future runtime resolution must be a separately governed Core mechanism with allowlists, provenance, capabilities, and security controls.

Key invariant:

```text
configuration reference != executable authority
```

## Deterministic validation

Added `experiments/project_contracts.py` and `tests/test_project_contracts.py`.

Positive validation proves two distinct projects load against one Core/DomainPack boundary.

Negative validation rejects:

- unsupported Work Unit kinds;
- omitted required adapters;
- weakened independent-verifier minimums;
- unsupported Core API versions;
- silent DomainPack version rebinding;
- repository-escaping DomainPack paths.

A dedicated read-only workflow, `.github/workflows/project-domain-contracts-check.yml`, runs compile/validation/self-test/unit-test on Python 3.11 and 3.13 with pinned checkout/setup actions and no write/secret/merge authority.

## Why a separate contract check

The existing Phase 0 harness is already an important and rapidly evolving integration surface, and PR #195 also touches the Phase 0 workflow for the active-compute offer self-test.

Rather than create an unnecessary conflict, issue #6 uses an isolated deterministic contract workflow. The new schemas remain compatible with the same `requirements-phase0.txt` JSON Schema dependency but do not alter worker execution, evaluator routing, or coordinator behavior.

## Non-goals in this turn

- no dynamic plugin loader;
- no remote DomainPack registry;
- no model-provider selection;
- no forge-specific Core API;
- no Work Unit execution from ProjectManifest data;
- no merge/approval authority;
- no new secrets;
- no branch-protection mutation;
- no automatic integration of this PR by the proposing assistant.

## Next evidence

Open the implementation as a draft against current `main`, run the dedicated contract CI and existing repository checks, correct any concrete contract/test defect, then mark review-ready only if the exact head is green and mergeable.

Issue #6 should close only after the reviewed implementation actually lands.
