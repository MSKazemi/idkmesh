# Conversation record: Free Resource Mesh integration outcome

**Date:** 2026-08-28

## User direction

> Continue and do the best and create what we need to use free resource and free agents and free computing resource and how we can integrate the Git repository with those resource and agents.

## What was completed

### Free Resource Mesh v0 landed

PR #125 was created, verified, and squash-merged as:

`c7bf92d2c957c4204137b906daa1981619f87be2`

The PR added exactly eight focused files:

- `scripts/free_resource_planner.py`;
- `tests/test_free_resource_planner.py`;
- `schemas/resource-offer-registry-v0.1.schema.json`;
- `examples/resources/free-resource-registry-v0.1.json`;
- `examples/resources/task-public-code-analysis-v0.1.json`;
- `.github/workflows/free-resource-plan.yml`;
- `docs/architecture/FREE_RESOURCE_MESH.md`;
- the initial implementation conversation record.

Exact PR-head GitHub checks all passed:

- Free Resource Mesh Plan — run `33187652283` — success;
- Phase 0 schema check — run `33187652255` — success;
- randomness-lab — run `33187652162` — success;
- IDKMesh Evolution Loop — run `33187652175` — success.

The Free Resource Mesh Plan itself ran on a standard public GitHub-hosted runner, demonstrating the first immediate zero-project-cost compute use of the new layer.

### Hosted-agent activation issue converged

Existing issue #12 was updated rather than replaced with another issue.

It now tracks:

- optional Gemini free-tier manual advisory activation;
- immutable patched Gemini Action pinning;
- owner-managed `GEMINI_API_KEY` secret only;
- trusted-main/read-only/manual-first posture;
- Jules bounded manual delegation;
- quota/usefulness/human-attention measurements;
- explicit exclusion of retired GitHub Models.

No secret was created, requested, or committed by this turn.

### Volunteer local-agent activation issue converged

Existing issue #11 was updated rather than replaced.

It now tracks adapters behind the canonical `idkmesh-node` boundary:

1. Ollama local adapter;
2. goose + Ollama adapter;
3. optional later OpenHands adapter.

It explicitly forbids turning a normal contributor computer into an unrestricted public-repository self-hosted Actions runner.

The target is zero project-paid inference cost while preserving sandboxing, provenance, independent verification, and no worker integration authority.

## Important repository cross-check

After the Free Resource Mesh landed, the repository was re-inspected for existing compute infrastructure.

IDKMesh already has a more concrete **Opportunistic Compute Fabric**:

- `docs/architecture/OPPORTUNISTIC_COMPUTE_FABRIC.md`;
- `schemas/compute-offer-pool-v0.1.schema.json`;
- `config/compute-policy.json`;
- `experiments/local_compute_offer.py`;
- `experiments/free_compute_router.py`;
- ADR-0006 zero-project-spend compute.

Issue #52, local capability discovery, is already completed.

This changed the integration decision: the new Free Resource Mesh must **not** become a second Work Unit scheduler.

A bridge architecture was therefore added directly to `main`:

`docs/architecture/FREE_RESOURCE_MESH_COMPUTE_BRIDGE.md`

Commit:

`c7fb42a232fb5667a570029e8003075902d2a03e`

## Canonical combined architecture

```text
external services / free tiers / volunteer agent classes
                    |
                    v
          Free Resource Mesh
      freshness / terms / privacy /
       secret / human-consent gates
                    |
          +---------+---------+
          |                   |
          v                   v
  activated compute       hosted/manual
     resource class        agent lane
          |                   |
          v                   v
   live Compute Offer      candidate /
        Pool               advisory output
          |                   |
          v                   |
 repository compute policy   |
          |                   |
          v                   |
 free_compute_router.py       |
          |                   |
          v                   |
 selected concrete offer      |
          |                   |
          v                   |
 adapter / idkmesh-node <-----+
          |
          v
 ResultManifest + artifacts
          |
          v
 independent verifier / Evidence Report
          |
          v
 explicit human/governance decision
```

## Layer responsibilities

### Free Resource Mesh

External/resource-class discovery and admission:

- current provider/service existence;
- free-to-project status;
- source freshness;
- external processing;
- repository-secret need;
- human interaction;
- broad resource/agent capabilities.

It does not dispatch a Work Unit.

### Compute Offer Pool + Free Compute Router

Concrete live execution selection:

- current availability;
- capped CPU/RAM/disk/GPU;
- trust;
- capability match;
- resource requirements;
- expected wait;
- project financial policy;
- deterministic concrete offer selection.

### Adapter / canonical node

Actual execution only after a concrete offer has been selected and execution is authorized through the established worker boundary.

### Verifier/governance

Correctness and integration authority remain outside both resource layers.

## Current zero-cost resource portfolio

The resource registry now tracks these classes with expiring evidence:

- GitHub Actions public standard runners;
- Gemini Developer API free tier;
- Google Jules free plan;
- volunteer Ollama local inference;
- volunteer goose + Ollama agent loop;
- self-hosted OpenHands/Agent Canvas;
- contributor-owned GitHub Codespaces free allowance;
- a tiny Cloudflare Workers free control-plane option;
- GitHub Models retained only as an explicit retired/excluded record.

Free-tier values are not protocol constants. Expired source evidence causes planner ineligibility.

## Security decisions

### Public GitHub Actions

Use aggressively for legitimate repository CI, verification, reproducibility, benchmark shards, and deterministic experiments because this is currently the easiest real zero-project-cost compute lane.

Do not use it as a generic unrelated public supercomputer.

### Hosted LLM agents

Remain opt-in and advisory-first. Zero monetary cost does not justify secrets, write permissions, automatic untrusted triggers, or integration authority.

### Volunteer machines

Use:

```text
approved immutable Work Unit
 -> local policy + capped concrete offer
 -> disposable sandbox
 -> bounded adapter
 -> canonical evidence
 -> cleanup
```

Do not use:

```text
public fork/PR code
 -> unrestricted persistent self-hosted runner
 -> personal machine
```

## Durable optimization target

The project should optimize:

> **verified useful work per maintainer minute and per unit of donated/free compute, subject to project monetary spend = $0 and preserved trust boundaries.**

Raw free CPU-hours, agent count, comment volume, or model confidence are not success metrics.

## Immediate next gates

1. Keep using GitHub-hosted Actions for deterministic/free repository compute.
2. Human/reviewer completes the remaining canonical node integration gate on PR #91.
3. After that, implement the Ollama adapter behind the canonical node rather than creating another worker.
4. Optionally activate Gemini/Jules through issue #12 after explicit owner account/secret setup and fresh security review.
5. Once multiple real resource classes exist, let the existing Compute Offer Pool / free router select concrete Work Unit execution and measure verified outcomes.
