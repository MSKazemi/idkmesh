# Conversation record: Free Resource Mesh v0

**Date:** 2026-08-28

## User direction

> Continue and do the best and create what we need to use free resource and free agents and free computing resource and how we can integrate the Git repository with those resource and agents.

## Interpretation

Build a concrete, provider-neutral zero-project-cost resource layer for IDKMesh rather than only documenting a list of free services.

The implementation must preserve the project's trust model:

- workers receive bounded Work Units;
- workers do not receive repository write/merge authority;
- external free tiers are volatile evidence, not guaranteed infrastructure;
- volunteer machines must be protected from public-repository code;
- candidate output still requires independent verification and an explicit integration decision.

## Current external findings

Checked against current public documentation on 2026-08-28:

- standard GitHub-hosted Actions runners are a strong free compute bootstrap for public repositories;
- GitHub Models was fully retired on 2026-07-30 and must not be used as a current architecture dependency;
- Gemini Developer API has a model-dependent free tier, but quotas can change and external processing/credential boundaries must be explicit;
- Google Jules currently has a bounded free plan and can act as a manually delegated GitHub coding agent;
- Ollama supports local model execution and is appropriate for volunteer-owned compute;
- goose can use Ollama as a local provider and is a candidate node adapter;
- OpenHands/Agent Canvas can be self-hosted but should remain behind the bounded worker interface;
- personal GitHub Free accounts include a Codespaces allowance, which is contributor-owned rather than project-guaranteed capacity;
- Cloudflare Workers Free can support a small future broker/control-plane front door but is not coding-agent compute;
- GitHub explicitly warns against using ordinary self-hosted runners with public repositories because untrusted fork/PR code can persistently compromise the host.

## Implementation

Created one canonical branch, `feature/free-resource-mesh-v0`, with:

1. `scripts/free_resource_planner.py`
   - deterministic zero-cost resource eligibility and ranking;
   - public-data/read-only task boundary;
   - source freshness enforcement;
   - explicit consent gates for repository secrets and external processing;
   - no dispatch or GitHub mutation.
2. `tests/test_free_resource_planner.py`
   - policy regression suite.
3. `schemas/resource-offer-registry-v0.1.schema.json`
   - versioned registry contract.
4. `examples/resources/free-resource-registry-v0.1.json`
   - current evidence-backed resource offers and one explicit retired service exclusion.
5. `examples/resources/task-public-code-analysis-v0.1.json`
   - sample bounded zero-cost public task request.
6. `.github/workflows/free-resource-plan.yml`
   - read-only, zero-secret public Actions validation/planning workflow.
7. `docs/architecture/FREE_RESOURCE_MESH.md`
   - staged integration architecture.

## Verification before publication

Local implementation verification completed before publishing the branch:

- 7 planner policy tests passed;
- Python compile passed;
- registry semantic validation passed;
- the registry also validated against its JSON Schema;
- a deterministic verifier task selected GitHub Actions as eligible free compute;
- an LLM task rejected external providers when external processing was not explicitly allowed;
- GitHub Models remained ineligible because it is retired;
- stale source evidence became ineligible automatically.

One initial test failure was useful: a deterministic-verification fixture accidentally retained an `llm` capability requirement from the sample research task, correctly causing GitHub Actions to be rejected. The fixture was corrected rather than weakening planner eligibility rules.

## Agent activation decision

The first merged layer should be resource **planning and deterministic compute**, not automatic hosted-agent execution.

Reasons:

- `main` is still unprotected at the time of this turn;
- a hosted agent requires either external account connection or repository secret;
- Gemini CLI / GitHub Action had security-sensitive workspace/headless issues fixed in 2026 and still merits explicit upstream-security review before widening automation;
- zero price is not evidence that an integration is safe.

Therefore:

- GitHub Actions lane: executable now, read-only/no secret;
- Gemini lane: documented opt-in manual advisory first;
- Jules lane: documented manual delegation;
- Ollama/goose/OpenHands lanes: staged behind the canonical `idkmesh-node` Work Unit / sandbox / ResultManifest boundary after PR #91's required independent human integration review.

## Durable rule

```text
free resource != trusted resource
free agent != autonomous authority
free compute -> bounded work -> evidence -> independent verification -> human decision
```

The registry's job is to make zero-cost capacity discoverable and replaceable without letting provider-specific quotas or agent frameworks become the architecture.
