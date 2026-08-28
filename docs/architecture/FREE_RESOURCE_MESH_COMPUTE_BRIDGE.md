# Free Resource Mesh ↔ Opportunistic Compute Fabric Bridge

**Status:** canonical integration boundary  
**Date:** 2026-08-28

IDKMesh has two related zero-project-cost mechanisms. They are **layers of one pipeline**, not competing schedulers.

## Canonical separation of responsibilities

### Free Resource Mesh

Files:

- `docs/architecture/FREE_RESOURCE_MESH.md`
- `schemas/resource-offer-registry-v0.1.schema.json`
- `examples/resources/free-resource-registry-v0.1.json`
- `scripts/free_resource_planner.py`

Responsibility:

> Discover and admit volatile **resource classes and agent services** using current external evidence, security/privacy constraints, explicit user consent, and source-freshness deadlines.

It answers questions such as:

- Is this provider/service still available?
- Is it currently free to the project?
- Is it a compute resource, hosted agent, volunteer local agent, contributor environment, or control-plane service?
- Does it require a repository secret?
- Does public task data leave IDKMesh/GitHub?
- Is human interaction required?
- Is the external evidence fresh enough to use?

It does **not** select a machine for a canonical Work Unit and does not dispatch work.

### Opportunistic Compute Fabric

Files:

- `docs/architecture/OPPORTUNISTIC_COMPUTE_FABRIC.md`
- `schemas/compute-offer-pool-v0.1.schema.json`
- `config/compute-policy.json`
- `experiments/local_compute_offer.py`
- `experiments/free_compute_router.py`

Responsibility:

> Select a concrete **live execution offer** for a canonical Work Unit under repository financial, resource, capability, and trust policy.

It answers questions such as:

- Which exact offer has enough CPU/RAM/disk/GPU?
- Is the offer available now?
- Does it meet the Work Unit capability and trust requirements?
- Does it satisfy the repository's hard `$0` project-spend ceiling?
- Which eligible concrete offer should be selected deterministically?

The router performs selection only; a separately trusted adapter performs execution.

## One pipeline

```text
external/public ecosystem
        |
        v
Free Resource Mesh registry
  current evidence + freshness
  privacy/secret/human-consent gates
        |
        +---------------- hosted/manual agent lane ----------------+
        |                                                          |
        v                                                          v
activated compute resource                                  bounded agent task
        |                                                          |
        v                                                          v
live Compute Offer Pool                                      candidate/advice
        |                                                          |
        v                                                          |
repository compute policy                                          |
        |                                                          |
        v                                                          |
free_compute_router.py                                             |
        |                                                          |
        v                                                          |
selected concrete offer                                            |
        |                                                          |
        v                                                          |
trusted adapter / idkmesh-node <-----------------------------------+
        |
        v
ResultManifest + candidate artifacts
        |
        v
independent verifier / Evidence Report
        |
        v
explicit human/governance integration decision
```

## Promotion rule: resource class → concrete offer

A registry entry is **not automatically a compute offer**.

Promotion requires runtime-local evidence unavailable from a public provider page, for example:

- current availability;
- actual capped CPU/RAM/disk/GPU;
- current queue/wait estimate;
- task-specific success history;
- trust level;
- independence group;
- explicit donor/user opt-in;
- provider-specific terms eligibility for the intended workload.

Only after those facts exist should an adapter emit `compute-offer-pool-v0.1` data.

This prevents a website saying “free tier” from becoming execution authority.

## Current mappings

| Free Resource Mesh entry | Concrete execution representation | Current posture |
| --- | --- | --- |
| `github-actions-public-standard` | `github-public-ci` / provider `github-actions` in the compute-offer pool | usable for legitimate public-project CI; no generic compute abuse |
| `volunteer-ollama-local` | local/donated `idkmesh-node` offer plus Ollama adapter capability | adapter staged behind canonical node integration |
| `volunteer-goose-ollama` | local/donated `idkmesh-node` offer plus goose/Ollama agent capability | adapter staged behind canonical node integration |
| `volunteer-openhands-agent-canvas` | local/donated compute offer plus OpenHands adapter | later/heavier adapter; not a separate scheduler |
| `gemini-api-free` | hosted agent adapter, not a raw compute offer | opt-in manual advisory first; secret/external-processing gates |
| `google-jules-free` | hosted/manual agent contribution path | opt-in delegation; normal verification afterwards |
| `github-codespaces-personal-free` | contributor-owned development environment | human contribution capacity, not project scheduler capacity |
| `cloudflare-workers-free-control-plane` | optional broker/control-plane service | metadata/routing only; not coding-agent compute |
| `github-models-retired` | none | excluded |

## Local donor path already available

`experiments/local_compute_offer.py` already performs conservative local capability discovery and emits a schema-valid zero-project-cost concrete offer. It does not execute or register a machine remotely.

`experiments/free_compute_router.py` already consumes Work Unit + offer pool + repository compute policy and fails closed when no zero-project-cost compatible offer exists.

Therefore the volunteer roadmap should extend these surfaces rather than create a new capacity schema.

Target flow:

```text
local_compute_offer.py
 -> donor applies explicit caps / opt-in
 -> compute-offer-pool-v0.1
 -> free_compute_router.py
 -> canonical idkmesh-node
 -> Ollama / goose / OpenHands adapter
 -> ResultManifest
 -> independent verification
```

## Authority invariant

Neither layer can grant integration authority.

```text
Resource Mesh admission != task correctness
Compute Fabric selection != task correctness
worker success           != acceptance
free price               != trust
agent confidence          != evidence
```

Only the established verification/governance path can support an integration decision.

## Convergence rule

Future work should extend one of these layers rather than introduce another scheduler:

- external provider/service facts, quota freshness, privacy, secret, agent class → **Free Resource Mesh**;
- live CPU/GPU/RAM/disk/trust/availability offer → **Compute Offer Pool**;
- Work Unit → concrete offer selection → **Free Compute Router**;
- execution framework/model/provider → **adapter behind canonical `idkmesh-node`**;
- correctness → **independent verifier**;
- integration → **human/governance authority**.
