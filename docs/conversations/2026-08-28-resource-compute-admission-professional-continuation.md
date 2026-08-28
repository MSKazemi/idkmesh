# Conversation record: professional continuation — Resource → Compute Admission

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## User direction

> Continue in a very professional way, like a full professor and 10 years experience engineer and CEO, CTO of a big company.

## Executive interpretation

Continue the zero-project-cost resource/agent program by improving **system architecture and integration discipline**, not by increasing agent count or creating another scheduler.

The highest-value next step was identified as making the existing boundary between:

1. the **Free Resource Mesh** (volatile external resource/service discovery), and
2. the **Opportunistic Compute Fabric** (concrete Work Unit compute selection)

machine-enforceable.

## Architectural decision

The bridge is **subtractive, not generative**.

A provider page or resource registry entry must never invent executable compute capacity.

The accepted architecture is:

```text
Free Resource Mesh evidence
        +
checked-in expiring project binding
        +
already-concrete live Compute Offer
        |
        v
Resource → Compute Admission
        |
        v
smaller admitted Compute Offer Pool
        |
        v
existing free_compute_router.py
        |
        v
separately trusted adapter / canonical idkmesh-node
        |
        v
ResultManifest -> independent verification -> human/governance decision
```

## Two-key temporal gate

A concrete offer can survive only when both of these are current:

### External key

The Free Resource Mesh entry must be:

- zero-project-cost;
- a direct compute class;
- not excluded/manual-only;
- backed by fresh external evidence;
- unable to write the repository;
- unable to merge.

### Local project key

A checked-in binding must explicitly and freshly authorize:

- resource class;
- provider identifier;
- cost class;
- capability allowlist;
- current terms eligibility;
- authorization scope;
- review date and expiration.

This prevents provider drift and local configuration drift from becoming silent execution authority.

## Implementation created

Branch:

`integration/resource-compute-admission-v0`

Files added:

- `scripts/resource_compute_admission.py`
- `tests/test_resource_compute_admission.py`
- `schemas/resource-compute-bindings-v0.1.schema.json`
- `config/resource-compute-bindings.json`
- `docs/architecture/RESOURCE_COMPUTE_ADMISSION.md`

Workflow updated:

- `.github/workflows/free-resource-plan.yml`

## Current binding

The v0 binding authorizes only the already-existing public-project GitHub Actions compute path:

```text
github-actions-public-standard
 -> github-public-ci-v0 binding
 -> provider github-actions
 -> cost class public_project_ci
 -> existing concrete offer github-public-ci
```

Scope is restricted to legitimate public-repository CI, testing, verification, reproducibility, and bounded repository experiments.

The binding does **not** authorize generic unrelated compute.

## Intentionally not bound yet

The following are not promoted to direct compute through this bridge:

- Gemini hosted agent;
- Jules hosted/manual agent;
- volunteer Ollama;
- goose + Ollama;
- OpenHands;
- contributor Codespaces;
- Cloudflare control-plane capacity.

Volunteer/local-model resource classes should remain unbound until the canonical node/adapter path can provide explicit donor opt-in, capped concrete resources, safe sandboxing, and verifiable ResultManifest output.

This preserves the still-pending separate human-review gate on canonical node PR #91 rather than routing around it.

## Local verification completed before publication

Eight deterministic unit tests passed:

1. fresh bound zero-cost offer admitted;
2. stale external evidence fails closed;
3. stale local binding review fails closed;
4. capability expansion fails closed;
5. unavailable concrete offer fails closed;
6. hosted agent cannot masquerade as direct compute;
7. ambiguous matching bindings fail closed;
8. malformed binding fails validation.

Python compilation also passed.

## CI design

The updated Free Resource Mesh workflow now proves the full integration chain on a zero-project-cost public GitHub-hosted runner:

```text
validate Resource Mesh registry
 -> validate binding schema/config
 -> run planner tests
 -> run admission tests
 -> filter existing compute-offer pool
 -> assert only explicitly bound github-public-ci survives
 -> run existing free_compute_router.py
 -> assert Phase 0 Work Unit selects github-public-ci at project cost $0
```

The workflow remains:

- `contents: read` only;
- no repository secrets;
- no external agent dispatch;
- no issue/PR/branch mutation;
- no code-selection authority;
- no merge/approval authority.

## Governance observation

During this turn `main` advanced concurrently with additional real-node evidence work. The latest live branch query still reported:

```text
protected = false
```

Therefore this execution-admission policy is being proposed through a PR and CI rather than treating automation as both proposer and final authority.

This is consistent with the repository's own guarded-evolution architecture: system-level autonomy should not expand while the canonical branch lacks machine-enforced protection.

## Management-level conclusion

The project now has a clearer platform decomposition:

```text
resource/service discovery      -> Free Resource Mesh
resource admission              -> Resource → Compute Admission
live machine/runtime facts      -> Compute Offer Pool
Work Unit routing               -> free_compute_router.py
execution                       -> trusted adapter / canonical node
candidate evidence              -> ResultManifest
correctness                     -> independent verifier / Evidence Report
integration authority           -> human/governance
```

This is preferable to a monolithic autonomous agent because every layer has a narrow responsibility, an explicit authority ceiling, deterministic failure semantics, and a measurable interface.

## Next professional milestones

1. Obtain CI evidence for this bridge PR against current `main`.
2. Protect `main` with ruleset/branch protection (#35).
3. Complete the genuinely separate human/reviewer gate for canonical node PR #91.
4. Only then add the first volunteer Ollama binding/adapter behind the canonical node.
5. Measure verified useful work per maintainer minute and donated/free compute unit before adding more providers.
