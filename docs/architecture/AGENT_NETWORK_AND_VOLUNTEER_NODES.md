# Agent Network and Volunteer Nodes

**Status:** Working architecture proposal  
**Date:** 2026-08-28

## Goal

Allow humans, cloud agents, local agents, and volunteer computers to contribute to IDKMesh continuously or intermittently without granting broad trust to any worker.

The design should work from one laptop to many machines and should remain useful even when participants use different agent frameworks or models.

## Core principle

**Workers receive bounded Work Units; they do not receive authority over the project.**

A worker may propose code, evidence, reports, tests, benchmarks, or reviews. Acceptance is a separate verification/integration decision.

## Initial topology

```text
                    GitHub
     issues / PRs / labels / repository state
                       |
                       v
               Work Unit broker
                       |
        +--------------+--------------+
        |              |              |
        v              v              v
 GitHub-hosted     local node      remote node
 agent/action      on laptop       on server
        |              |              |
        v              v              v
 Gemini/etc.      agent adapter    agent adapter
                  + local model     + model/provider
        |              |              |
        +--------------+--------------+
                       |
                       v
                candidate results
                       |
                       v
       tests / security / peer verification
                       |
                       v
              review + integration
```

## Worker classes

A node can expose one or more capabilities rather than pretending all agents are interchangeable.

### Observer

Read-only tasks:

- issue classification;
- documentation drift detection;
- summarization;
- dependency/repository inspection;
- provenance collection.

### Researcher

Produces evidence and hypotheses:

- reference discovery;
- literature maps;
- comparison reports;
- reproduction plans;
- experiment proposals.

### Coder

Produces candidate patches in an isolated workspace:

- small issue fixes;
- tests;
- prototypes;
- refactors within explicit scope;
- documentation changes.

### Verifier

Independently examines candidate work:

- unit/integration tests;
- fuzzing;
- static analysis;
- security checks;
- independent reproduction;
- adversarial critique;
- alternate model review.

### Compute worker

Runs deterministic or numerical work that may not need an LLM:

- simulations;
- benchmark shards;
- search/optimization;
- compilation/test matrices;
- experiment repetitions.

## Work Unit schema — first draft

Every distributed task should eventually be serializable as a Work Unit. A minimal conceptual schema:

```yaml
id: wu-...
type: coder | verifier | researcher | compute | observer
repository: MSKazemi/idkmesh
input_revision: <immutable commit sha>
goal: <bounded task description>
allowed_paths:
  - src/...
forbidden_paths:
  - .github/workflows/...
required_capabilities:
  - python
  - docker
resource_budget:
  wall_time_seconds: 1800
  cpu_cores: 4
  memory_mb: 8192
  network: restricted
model_policy:
  local_allowed: true
  remote_allowed: false
verification:
  required:
    - tests
    - independent-review
submission:
  artifact_types:
    - patch
    - report
    - test-results
```

The exact format is not settled. The important properties are bounded scope, immutable inputs, explicit permissions, resource budgets, and declared verification requirements.

## Proposed `idkmesh-node`

`idkmesh-node` should be a small open-source application installed on a participant's computer.

The ideal participant experience is eventually close to:

```text
install IDKMesh Node
choose resource limits
choose allowed capabilities/models
join the public mesh
```

The node should then idle cheaply and request work only when resources are available.

### Responsibilities

1. **Register capability metadata** without exposing unnecessary personal information.
2. **Request eligible Work Units** rather than accepting arbitrary remote shell commands.
3. **Verify task signature / origin / policy** before execution.
4. **Create a disposable sandbox** for each task.
5. **Materialize an exact repository revision**.
6. **Launch a configured adapter**, such as goose, OpenHands, SWE-agent, Gemini CLI, a local script, or a deterministic compute job.
7. **Enforce CPU/RAM/time/network/disk budgets**.
8. **Collect provenance**, tool versions, model identity where available, logs, hashes, and test results.
9. **Return candidate artifacts** to a gateway or GitHub contribution path.
10. **Destroy the workspace** after completion unless explicitly retained for debugging.

## Adapter architecture

Do not hard-code IDKMesh to one agent company or framework.

```text
idkmesh-node
   |
   +-- adapter: command
   +-- adapter: goose
   +-- adapter: OpenHands
   +-- adapter: SWE-agent
   +-- adapter: Gemini CLI
   +-- adapter: future agent
   +-- adapter: deterministic compute
```

An adapter should translate a Work Unit into the tool's execution format and normalize the result back into IDKMesh artifacts/evidence.

## Local models

A volunteer node can use local open-weight models through a runtime such as Ollama. This provides a path where API cost is zero for the project and the volunteer contributes the hardware/electricity.

This should be treated as one worker class, not assumed to have the same quality as frontier hosted models. The scheduler should learn which task types each configuration handles well.

## Continuous operation model

IDKMesh should avoid 24/7 token-burning loops.

Continuous operation means a hierarchy of triggers:

- repository event;
- scheduled sweep;
- explicit task label;
- idle volunteer resource;
- failed verification;
- unresolved disagreement;
- experiment demand.

Workers sleep when no useful Work Unit exists.

## Security boundary

Volunteer nodes are untrusted **and** the public task stream is untrusted from the volunteer's perspective.

Therefore security is bidirectional.

### Protect the project from workers

- workers cannot merge directly;
- immutable input commit;
- provenance for output;
- independent verification;
- scoped identities/tokens;
- reputation based on verified history, not self-report;
- duplicate/independent execution for important work;
- deterministic validators where possible.

### Protect volunteers from tasks

- do not register normal personal machines as unrestricted self-hosted GitHub runners for the public repository;
- disposable container/VM/sandbox per task;
- no host filesystem access except explicitly mounted workspace;
- no personal SSH keys, browser profiles, cloud credentials, or home directories in the sandbox;
- restricted/default-off network access;
- signed/approved Work Units;
- resource caps and emergency stop;
- visible task before execution where practical;
- opt-in capability classes;
- automatic cleanup.

## Trust levels

Potential staged model:

- **L0 anonymous/untrusted:** public read-only research or deterministic tasks; output treated as hints.
- **L1 registered node:** bounded sandboxed tasks; all output independently verified.
- **L2 proven node:** verified history allows more expensive tasks, still no direct merge.
- **L3 trusted infrastructure:** project-managed machines may execute sensitive verification/CI jobs.

Trust should be task-specific and evidence-based rather than a universal score.

## GitHub as bootstrap control plane

Before IDKMesh builds a distributed broker, GitHub can provide a workable first coordination layer:

- issues = Work Unit candidates;
- labels = readiness/capability/risk/verification metadata;
- comments = public task/evidence history;
- branches/PRs = candidate code artifacts;
- Actions = event/schedule orchestration and trusted CI;
- CodeQL/tests = independent verification;
- GitHub identities = initial contribution provenance.

This allows the protocol to be learned from real community activity before building a separate service.

## Suggested labels

Future useful labels may include:

- `agent-ready`
- `agent:research`
- `agent:code`
- `agent:verify`
- `compute-ready`
- `risk:low`
- `risk:medium`
- `risk:high`
- `needs-independent-verification`
- `human-review-required`

Do not create a complicated label taxonomy until actual workflows need it.

## Phase plan

### Phase A — repository agents

Use GitHub-hosted, event-driven automation for low-risk triage/review/research tasks. Keep merge decisions human-controlled.

### Phase B — one-machine node prototype

Build `idkmesh-node` with:

- one Work Unit JSON/YAML input;
- Docker sandbox;
- one generic command adapter;
- goose + Ollama as the first optional local-agent adapter;
- normalized result bundle;
- no networked scheduler yet.

### Phase C — GitHub-backed task pickup

Allow a node to discover explicitly approved issues/Work Units and submit results through a safe gateway/PR mechanism.

### Phase D — multiple independent nodes

Dispatch the same or related Work Units to heterogeneous agents/nodes. Measure quality, error correlation, verification cost, latency, and useful output.

### Phase E — native broker/federation

Only after the earlier experiments reveal actual requirements, build the distributed task broker, discovery, reputation, federation, and work-stealing layers.

## Success metrics

Raw agent activity is not success. Measure:

- verified useful tasks completed;
- hidden-test/security success;
- human review minutes per accepted artifact;
- compute/API cost per accepted artifact;
- wall-clock latency;
- independent error correlation;
- regression rate;
- contributor onboarding friction;
- percentage of submitted work that is reproducible;
- node safety incidents;
- percentage of tasks successfully matched to heterogeneous hardware/models.

## Community impact

A safe one-command node could turn spare laptops, desktops, servers, local models, and human expertise into visible contribution channels. It also lets non-maintainers participate without receiving repository write authority. The project should make resource use explicit, provide easy pause/stop controls, publish task/result provenance, and never imply that volunteers must donate compute to be valued contributors.
