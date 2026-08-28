# Free Resource Mesh

**Status:** v0 integration architecture  
**Date:** 2026-08-28  
**Project cost target:** USD 0 for the bootstrap path

## Goal

Connect IDKMesh to useful free compute and free/volunteer agents without coupling the project to one provider and without giving an external worker repository authority.

The resource layer is deliberately split into two independent concerns:

```text
resource discovery / planning
             |
             v
      bounded Work Unit
             |
             v
  worker or compute offer
             |
             v
       candidate result
             |
             v
 independent verification
             |
             v
 human / governance decision
```

A free resource is **capacity**, not authority.

## Why a registry instead of hard-coded providers

Free tiers change, services disappear, quotas move, and volunteer machines are intermittent. IDKMesh therefore models every external resource as an **expiring evidence-backed offer**.

Each offer records:

- what task classes it can perform;
- capabilities;
- whether it needs a repository secret;
- whether task data leaves the local/GitHub environment;
- human setup cost;
- scarcity / availability;
- security risk;
- activation method;
- source URL;
- date checked and maximum evidence age;
- hard `repo_write_authority=false` and `merge_authority=false` in v0.

`examples/resources/free-resource-registry-v0.1.json` is the current registry. `scripts/free_resource_planner.py` fails closed when an offer is stale or incompatible.

## Bootstrap topology

```text
                          GitHub
                             |
                +------------+------------+
                |                         |
                v                         v
      Free Resource Planner        canonical Work Unit
      (read-only Actions)                  |
                |                          |
                +------------+-------------+
                             |
             +---------------+------------------+
             |               |                  |
             v               v                  v
      GitHub Actions     hosted agent      volunteer node
      free public CI     (opt-in)          (opt-in)
             |               |                  |
      deterministic       Jules /          Ollama / goose /
      compute/tests       Gemini            OpenHands / future
             |               |                  |
             +---------------+------------------+
                             |
                             v
                   untrusted candidate/evidence
                             |
                             v
              canonical independent verification
                             |
                             v
                   explicit human decision
```

## Resource lanes

### Lane A — GitHub Actions: use now

For a public repository, standard GitHub-hosted runners are the best bootstrap compute pool because they can run deterministic CI, tests, simulations, schema checks, benchmark shards, and evidence tooling without project-paid compute.

IDKMesh should use this lane aggressively for **verification and deterministic compute**, not for burning LLM tokens.

Current integration:

- `.github/workflows/free-resource-plan.yml`;
- `permissions: contents: read`;
- pinned checkout/setup action SHAs;
- no secrets;
- no external dispatch;
- no repository mutation;
- no merge/approval authority.

### Lane B — Gemini Developer API / Gemini CLI Action: opt-in advisory

The Gemini Developer API currently exposes a free tier for some models. Treat the quota as opportunistic, not guaranteed infrastructure.

If the repository owner wants this lane:

1. create a Gemini API key outside the repository;
2. add it only as GitHub Actions secret `GEMINI_API_KEY`;
3. use a **manual `workflow_dispatch` advisory workflow first**;
4. check out trusted `main`, not untrusted PR-head code;
5. use `contents: read`, do not persist checkout credentials;
6. pin `google-github-actions/run-gemini-cli` to reviewed immutable SHA `f77273f4c914e4bf38440cf36a0369cb64a37489` (v0.1.22 at time of review);
7. identify output as untrusted advisory evidence;
8. do not let it push, merge, approve, change settings, or handle sensitive/private data;
9. re-review upstream security advisories/issues before widening permissions or triggers.

The action is intentionally **not activated automatically in v0**. Zero price is not a reason to weaken the trust boundary.

### Lane C — Google Jules: opt-in human delegation

Jules can be connected to GitHub and currently provides a bounded free plan. Use it as a contributor-like coding lane:

```text
issue / Work Unit
 -> human selects bounded task
 -> Jules works in its environment
 -> proposed diff / PR
 -> normal IDKMesh verification
```

Do not encode Jules quotas as a permanent architectural constant. The registry carries a freshness deadline for this reason.

### Lane D — volunteer Ollama / goose: after canonical node integration

This is the most important path for genuinely distributed zero-project-cost AI compute.

A contributor can donate idle CPU/GPU and electricity while the project supplies only bounded public Work Units.

Recommended stack:

```text
idkmesh-node
  -> disposable sandbox
  -> exact repository revision
  -> goose adapter
  -> Ollama local tool-calling model
  -> ResultManifest + patch/log evidence
  -> independent verifier
```

Ollama keeps model inference local. goose provides an agent loop above the model. Neither worker receives GitHub merge authority.

This lane should wait for the canonical `idkmesh-node` PR #91 to receive its required independent human review/integration rather than creating a second worker implementation.

### Lane E — OpenHands / Agent Canvas: optional heavier volunteer orchestrator

Self-hosted OpenHands/Agent Canvas can run coding agents on contributor-controlled infrastructure. It is useful for volunteers with a dedicated machine or VM, but it has a larger attack surface and setup cost than a minimal node adapter.

IDKMesh should integrate it as an adapter behind the same Work Unit / ResultManifest boundary, never as an all-powerful repository bot.

### Lane F — contributor Codespaces: human-owned free development capacity

Personal GitHub Free accounts currently include a monthly Codespaces allowance. This is useful for onboarding contributors who do not want to configure a local environment.

It is a **personal quota**, not a project compute pool. IDKMesh must not automate quota farming or treat personal free allowances as guaranteed project infrastructure.

### Lane G — tiny free control plane

A serverless free tier such as Cloudflare Workers can eventually provide a small HTTP ingress, capability directory, or broker front door. Its free CPU budget is appropriate for routing/metadata, not coding-agent execution.

Do not add a separate broker service until GitHub-backed Work Unit pickup proves that one is needed.

## Explicit exclusions

### GitHub Models

GitHub Models was retired on 2026-07-30. It remains in the registry as `excluded` so future contributors do not accidentally revive stale architecture around it.

### Public self-hosted runners on personal machines

Do **not** expose normal volunteer laptops/desktops as unrestricted self-hosted Actions runners for this public repository.

The safe distinction is:

```text
UNSAFE default
public GitHub event -> arbitrary repository code -> volunteer runner host

IDKMesh design
approved immutable Work Unit -> disposable sandbox -> bounded task -> evidence -> cleanup
```

A volunteer computer must distrust the task stream just as IDKMesh distrusts worker output.

### Free-tier abuse

The project must not evade quotas, create accounts to multiply free allowances, mine cryptocurrency, run unrelated workloads, or disguise automated workloads as interactive use. A resource disappears from the eligible registry when its terms, quota, security, or availability no longer fit.

## Planning algorithm

`free_resource_planner.py` first applies hard gates:

```text
eligible(r, t) =
  zero_project_cost
  AND source_evidence_fresh
  AND task_class_supported
  AND required_capabilities_present
  AND public_data_only
  AND no_repo_write_required
  AND user_consented_to_secret_if_needed
  AND user_consented_to_external_processing_if_needed
  AND no_merge_authority
```

Only eligible offers are ranked. The v0 score rewards availability, capability fit, independence, and low credential/external-processing exposure while penalizing setup burden, scarcity, and security risk.

The score is scheduling advice, never correctness evidence.

## Repository integration sequence

### Stage 0 — landed by this PR

- versioned free-resource registry;
- JSON Schema;
- deterministic fail-closed planner;
- policy tests;
- free public GitHub Actions validation/planning workflow;
- current integration architecture.

### Stage 1 — immediate zero-secret work

Use GitHub Actions to shard:

- schemas/tests;
- deterministic simulations;
- benchmark verification;
- reproducibility checks;
- static/security checks;
- evidence replay.

### Stage 2 — optional hosted agents

After explicit owner setup:

- manual Gemini read-only advisory;
- manually delegated Jules tasks;
- outputs enter the same candidate/evidence path as human contributions.

Do not activate repository writes simply because a hosted agent is free.

### Stage 3 — volunteer compute

After canonical node integration:

- Ollama adapter;
- goose + Ollama adapter;
- OpenHands adapter;
- capability advertisement;
- opt-in idle scheduling;
- disposable sandbox per Work Unit;
- exact input revision and normalized result provenance.

### Stage 4 — GitHub-backed broker experiment

Use GitHub as the first broker:

```text
approved issue / checked-in Work Unit
 -> read-only discovery
 -> node claims lease
 -> executes locally
 -> uploads candidate through a constrained contribution path
 -> verifier evaluates
 -> human integrates or rejects
```

Only if this becomes a bottleneck should IDKMesh add a native broker/service.

## Success metrics

Do not measure success by number of agents or free CPU-hours consumed. Measure:

- verified useful results per project dollar (target denominator can be zero);
- verified useful results per maintainer minute;
- verifier backlog;
- task success by resource/adapter class;
- escaped defect rate;
- independent failure correlation;
- reproducibility;
- volunteer setup/cleanup friction;
- resource safety incidents;
- external-provider dependency concentration;
- percentage of useful work executable with no project-held secret.

## Current decision

The shortest safe path is:

```text
GitHub Actions (now)
 + optional hosted advisory agents
 + canonical idkmesh-node
 + volunteer local-model adapters
 + independent verifier
 = Free Resource Mesh
```

The system should grow by adding **resource offers and adapters**, not by granting more authority to workers.
