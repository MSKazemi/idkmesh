# Agent and Model Connector Control Plane

**Status:** implementation target / architecture proposal  
**Date:** 2026-09-22  
**Scope:** productize the existing WorkUnit/WorkerAdapter/verification foundation into an easy-to-connect GitHub + agent + model platform.

## 1. Product objective

IDKMesh should become easy to use in two successive loops:

1. **Build IDKMesh with external agents and models.**
2. **Use IDKMesh itself to build and maintain other applications.**

The first loop is bootstrap. The second loop is the product proof.

The intended user experience is not "install ten bots and hand them repository tokens." It is:

```text
connect repository
 -> connect one or more agent/model providers
 -> test connections
 -> declare policy
 -> convert issue/spec into bounded WorkUnit
 -> dispatch to eligible worker
 -> collect canonical candidate evidence
 -> verify independently
 -> open/review PR
 -> explicit human integration decision
```

The current repository already has most of the semantic foundation:

- WorkUnit / ResultManifest / EvaluatorPlan / VerificationResult contracts;
- protocol-neutral `WorkerAdapter`;
- A2A/MCP bindings;
- independent verification and evidence/reporting machinery;
- free-resource discovery and zero-project-spend policy;
- GitHub-native issue/PR/workflow coordination;
- a protected `main` branch with required PR gates.

The missing product layer is a **Connector Control Plane**.

## 2. Design rule: model != agent != execution backend != GitHub

Do not collapse these concepts.

### Model provider

A model provider generates model responses. Examples:

- OpenAI-compatible endpoint;
- Gemini API;
- Ollama;
- vLLM;
- OpenRouter;
- a LiteLLM gateway;
- future native provider adapters.

A raw model should not receive repository authority by itself.

### Agent runner

An agent runner supplies the tool loop around one or more models. Examples:

- Google Jules;
- OpenHands;
- goose;
- Gemini CLI;
- mini-SWE-agent / SWE-agent;
- future coding agents speaking A2A/ACP/MCP or an HTTP API.

An agent receives a bounded task and returns a candidate result.

### Execution backend

The execution backend determines where and how a worker runs:

- hosted vendor sandbox;
- local process;
- disposable Docker sandbox;
- canonical `idkmesh-node`;
- GitHub Actions;
- remote A2A worker;
- future VM/microVM/WASI substrate.

### SCM/project connector

The SCM connector maps project events and candidate changes:

- GitHub App/webhooks;
- local Git checkout;
- future GitLab/other integrations.

This separation lets IDKMesh replace any one part without rewriting the coordinator.

## 3. Target architecture

```text
                         GitHub
          issues / PRs / webhooks / checks
                            |
                            v
                  +--------------------+
                  |  SCM Connector     |
                  |  GitHub adapter    |
                  +---------+----------+
                            |
                            v
                  +--------------------+
                  | Connector Control  |
                  | Plane              |
                  |                    |
                  | registry           |
                  | policy             |
                  | routing            |
                  | run state          |
                  | secret refs        |
                  +----+----------+----+
                       |          |
              +--------+          +-------------------+
              |                                       |
              v                                       v
    +-------------------+                  +---------------------+
    | Agent Connectors  |                  | Model Providers     |
    |                   |                  |                     |
    | Jules REST        |                  | OpenAI-compatible   |
    | OpenHands         |                  | Gemini-compatible   |
    | goose             |                  | Ollama              |
    | Gemini CLI        |                  | vLLM                |
    | mini-SWE-agent    |                  | OpenRouter          |
    | A2A/MCP workers   |                  | LiteLLM gateway     |
    +---------+---------+                  +----------+----------+
              |                                       |
              +------------------+--------------------+
                                 |
                                 v
                    +-------------------------+
                    | Execution Backends      |
                    | hosted / Docker / node  |
                    +------------+------------+
                                 |
                                 v
                      untrusted candidate
                                 |
                                 v
                  ResultManifest + artifacts
                                 |
                                 v
                independent verifier/evidence
                                 |
                                 v
                      explicit human merge
```

The control plane is a broker and normalizer. It does not become merge authority.

## 4. Connector kinds

Every configured integration should declare one of four connector kinds.

### `scm`

Project/repository integration.

Initial driver:

- `github`

Later:

- local Git;
- GitLab if demanded by evidence/users.

### `agent`

A complete task-execution agent.

Initial drivers:

- `jules` — remote REST API;
- `github-native` — trigger agents that are controlled through labels/comments/actions;
- `cli` — allowlisted local agent executable inside a bounded sandbox;
- `a2a` — protocol transport;
- `mcp-worker` — MCP tool/task adapter when semantics fit.

Concrete presets can map to OpenHands, goose, Gemini CLI, mini-SWE-agent, and similar systems without adding coordinator branches.

### `model`

Model inference provider for local/self-hosted agent loops.

Initial driver:

- `openai-compatible`

This one interface can cover several useful providers and local servers by changing base URL, model and secret reference. Native provider drivers should be added only when required features cannot be represented faithfully.

### `execution`

Worker runtime/sandbox.

Initial drivers:

- `local-docker`;
- `idkmesh-node`;
- `github-actions` for appropriate deterministic jobs.

Hosted agents such as Jules own their execution substrate internally; the IDKMesh connector records that fact rather than pretending the local control plane owns the sandbox.

## 5. Why Jules should be the first remote API connector

As of 2026-09-22, Jules provides an alpha REST API with:

- API-key authentication;
- connected GitHub repository Sources;
- Session creation;
- plan approval controls;
- Activities/progress;
- messaging into a running session.

Primary documentation:

- https://jules.google/docs/api/reference/
- https://jules.google/docs/api/reference/overview
- https://jules.google/docs/api/reference/sources/

This is a strong first connector because IDKMesh already uses Jules in the repository, but current integration is mostly GitHub-label based.

The first implementation should default to:

```json
{
  "requirePlanApproval": true
}
```

until bounded real-task evidence supports wider automation.

The Jules source itself must still be connected through the Jules web/GitHub installation flow; the API can list/use sources but does not currently create them.

## 6. OpenHands and GitHub-native agents

OpenHands currently documents a GitHub Action flow triggered by:

- a `fix-me` label; or
- a comment beginning with `@openhands-agent`.

Reference:

- https://docs.openhands.dev/openhands/usage/run-openhands/github-action

That should initially be represented as a **GitHub-native agent connector**, not forced into a fake synchronous HTTP API.

Generic connector mode:

```text
submit WorkUnit
 -> add configured label/comment through constrained SCM connector
 -> observe issue/PR events
 -> bind resulting PR/head SHA to the run
 -> collect candidate patch + metadata
 -> normalize to ResultManifest
```

The same mode can later cover other GitHub-native coding agents.

## 7. Local agent connectors

goose currently exposes desktop, CLI and API surfaces and supports multiple model providers plus MCP extensions.

Reference:

- https://block.github.io/goose/

The local agent path should use a generic allowlisted executable adapter behind the canonical sandbox/node boundary:

```text
WorkUnit
 -> disposable workspace at exact source SHA
 -> allowlisted agent driver
 -> configured model connection
 -> patch / logs / test evidence
 -> ResultManifest
 -> cleanup
```

Initial local presets:

- `goose`;
- `gemini-cli`;
- `mini-swe-agent`.

Do not let issue text choose the executable, shell template, secret reference, network policy, or filesystem mounts.

## 8. Model-provider strategy

### 8.1 OpenAI-compatible driver first

The minimum useful model interface should be an OpenAI-compatible HTTP client.

That immediately supports or can support:

- Gemini's documented OpenAI compatibility endpoint;
- Ollama's OpenAI-compatible endpoint;
- vLLM's OpenAI-compatible server;
- OpenRouter;
- LiteLLM Proxy;
- OpenAI itself;
- other compatible gateways.

Relevant current references:

- Gemini compatibility: https://ai.google.dev/gemini-api/docs/openai
- Ollama API: https://docs.ollama.com/
- vLLM server: https://docs.vllm.ai/en/stable/serving/openai_compatible_server/
- OpenRouter: https://openrouter.ai/developers
- LiteLLM: https://docs.litellm.ai/

### 8.2 Native adapters only when needed

Compatibility APIs do not expose every provider-specific feature. Add a native provider driver only when a concrete product requirement cannot be expressed with the common interface.

Examples of possible later native drivers:

- Anthropic;
- Gemini native tools/files/grounding;
- OpenAI Responses/Agents-specific features.

The common model API is therefore a portability baseline, not a claim that every provider is semantically identical.

### 8.3 LiteLLM is optional infrastructure

LiteLLM can expose many providers through one OpenAI-style gateway and provides routing, rate limiting and budget controls.

It should be supported as an optional deployment component, **not imported into the dependency-free IDKMesh core**.

This keeps the policy boundary clear:

```text
IDKMesh owns:
  task authority
  connector eligibility
  WorkUnit semantics
  verification
  provenance
  human integration

Optional gateway owns:
  provider request translation
  provider retry/fallback
  provider-level rate/cost plumbing
```

## 9. Dependency boundary

The current installable `idkmesh` package intentionally keeps `gate-audit` dependency-free.

Preserve that.

Recommended packaging:

```text
idkmesh core
  stdlib-only connector contracts/config validation where practical
  gate-audit remains dependency-free

idkmesh[connectors]
  HTTP client/runtime dependencies required by live connectors

idkmesh[control]
  optional HTTP service dependencies

idkmesh[verify]
  existing verification dependency
```

Do not make a user install a web server, SDKs, Docker client, or provider SDK merely to run `idkmesh gate-audit`.

## 10. Core interfaces

The control-plane implementation should converge on small interfaces.

### 10.1 Agent connector

Conceptual Python contract:

```python
class AgentConnector(Protocol):
    connector_id: str
    connector_version: str

    def capabilities(self) -> AgentCapabilities: ...
    def probe(self) -> ConnectionProbe: ...
    def submit(self, work_unit: dict, context: DispatchContext) -> RunHandle: ...
    def inspect(self, run_id: str) -> AgentRunSnapshot: ...
    def cancel(self, run_id: str) -> AgentRunSnapshot: ...
    def collect(self, run_id: str) -> AdapterExecution: ...
```

The returned `AdapterExecution` should feed the existing `run_with_adapter()` normalization path or a direct successor of that contract.

### 10.2 Model provider

```python
class ModelProvider(Protocol):
    provider_id: str

    def probe(self) -> ConnectionProbe: ...
    def list_models(self) -> tuple[ModelDescriptor, ...]: ...
    def generate(self, request: ModelRequest) -> ModelResponse: ...
```

The model interface is used by local agent runners; GitHub issue dispatch should normally target an `AgentConnector`, not `ModelProvider.generate()` directly.

### 10.3 SCM connector

```python
class SCMConnector(Protocol):
    def repository_snapshot(self, project_id: str) -> RepositorySnapshot: ...
    def issue_to_work_unit(self, issue_ref: str) -> dict: ...
    def publish_candidate(self, candidate: CandidateChange) -> CandidateRef: ...
    def observe_candidate(self, candidate_ref: CandidateRef) -> CandidateState: ...
```

### 10.4 Secret resolver

```python
class SecretResolver(Protocol):
    def resolve(self, ref: str) -> SecretValue: ...
```

Initial accepted references:

- `env:NAME`;
- GitHub Actions secret injection into process environment.

Future optional resolvers can support Vault/1Password/cloud secret managers without changing connection records.

## 11. Configuration contract

Configuration must contain **references to secrets, never secret values**.

Proposed project-local configuration:

```yaml
api_version: idkmesh.io/v1alpha1
kind: ConnectorProfile

project:
  repository: MSKazemi/idkmesh

connections:
  - id: github-main
    kind: scm
    driver: github
    settings:
      repository: MSKazemi/idkmesh

  - id: jules-main
    kind: agent
    driver: jules
    auth:
      secret_ref: env:JULES_API_KEY
    settings:
      source: sources/github/MSKazemi/idkmesh
      starting_branch: main
      require_plan_approval: true
    policy:
      task_classes: [coder]
      max_concurrency: 1
      allowed_risk: [low]

  - id: gemini-openai
    kind: model
    driver: openai-compatible
    auth:
      secret_ref: env:GEMINI_API_KEY
    settings:
      base_url: https://generativelanguage.googleapis.com/v1beta/openai/
      model: <configured-model>
    policy:
      external_processing: true
      project_spend_usd_max: 0

  - id: ollama-local
    kind: model
    driver: openai-compatible
    settings:
      base_url: http://127.0.0.1:11434/v1
      model: <allowlisted-local-model>
    policy:
      external_processing: false
      project_spend_usd_max: 0
```

This is a proposed control-plane profile, not a replacement for WorkUnit, compute-offer, or Free Resource Mesh schemas.

## 12. Connection lifecycle

Every connection has explicit state:

```text
configured
 -> probe_pending
 -> healthy | degraded | unavailable
 -> disabled
```

A connection probe records:

- connector driver/version;
- checked time;
- endpoint/source identity;
- authentication present/missing without exposing it;
- capabilities observed;
- quota/rate-limit metadata if safely available;
- terms/evidence freshness where relevant;
- failure class;
- no correctness or merge authority.

The dispatcher uses only healthy/eligible connections.

## 13. Proposed backend API

The first HTTP API should be thin over the same Python control-plane services used by the CLI.

### Service

- `GET /health`

### Projects

- `GET /v1/projects`
- `POST /v1/projects`
- `GET /v1/projects/{project_id}`

### Connections

- `GET /v1/connections`
- `POST /v1/connections`
- `GET /v1/connections/{connection_id}`
- `POST /v1/connections/{connection_id}:probe`
- `POST /v1/connections/{connection_id}:enable`
- `POST /v1/connections/{connection_id}:disable`

### Routing

- `POST /v1/routes:resolve` — dry-run eligibility/routing explanation.

### Work

- `POST /v1/work-units:preview` — convert an SCM issue/spec into canonical WorkUnit without dispatch.
- `POST /v1/runs` — dispatch an already-authorized WorkUnit.
- `GET /v1/runs/{run_id}`
- `GET /v1/runs/{run_id}/events`
- `POST /v1/runs/{run_id}:cancel`

### Results

- `GET /v1/results/{result_id}`
- `GET /v1/verifications/{verification_id}`

### GitHub ingress

- `POST /v1/webhooks/github`

The webhook endpoint must verify GitHub signatures and event replay/idempotency before touching project state.

## 14. Run state machine

Use an explicit state model:

```text
created
 -> admitted
 -> dispatched
 -> waiting_for_agent
 -> candidate_ready
 -> verification_pending
 -> verified | verification_failed
 -> awaiting_human_decision
 -> integrated | rejected | cancelled | failed
```

Important:

- `verified` still does not mean `integrated`;
- an external agent's "completed" status maps to candidate readiness, not acceptance;
- a PR being open is a candidate locator, not proof of correctness.

## 15. GitHub-native control surface

GitHub remains the first public project UI.

Recommended labels:

```text
idkmesh:ready
idkmesh:auto
agent:jules
agent:openhands
agent:local
agent:research
risk:low
risk:medium
risk:high
needs-human-review
```

Rules:

- an explicit agent label wins over `idkmesh:auto`;
- `idkmesh:auto` is allowed only for low-risk task classes initially;
- high-risk labels always require a human to select/approve the route;
- labels select policy intent, not raw credentials or commands;
- issue text cannot elevate permissions.

## 16. Routing policy

Routing should begin deterministic and explainable.

Eligibility example:

```text
eligible(connection, work_unit) =
    connection.healthy
AND connection.supports(task_class)
AND work_unit.risk in connection.allowed_risk
AND data_egress_policy_allows(connection)
AND cost_policy_allows(connection)
AND concurrency_available(connection)
AND required_capabilities_subset(connection.capabilities)
AND secret_requirements_satisfied
AND no_authority_conflict
```

Ranking can later use measured evidence such as:

- historical verified success for similar tasks;
- verifier/human minutes;
- wall time;
- failure correlation;
- quota scarcity;
- reproducibility.

Do not optimize on raw model confidence or number of commits.

## 17. GitHub App model

Long term, the easiest hosted setup is an IDKMesh GitHub App.

Minimum principle:

- read repository metadata/issues;
- receive issue/PR/check events;
- create comments/checks;
- create/update an IDKMesh-owned candidate branch/PR only when policy explicitly grants that action;
- never receive merge/settings/administration authority for normal operation.

During bootstrap, a local/Actions token can be used through environment injection, but the product target should be GitHub App installation tokens with least privilege and short lifetime.

## 18. Credentials and secrets

Hard rules:

1. Never store raw API keys in tracked config, WorkUnit, ResultManifest, logs, issue bodies, PR bodies, or run artifacts.
2. Connection records store only `secret_ref`.
3. Resolve the secret only in the control plane or agent runtime that needs it.
4. Do not pass a provider key into an unrelated worker sandbox.
5. Redact headers/env values from logs.
6. Treat external provider responses as untrusted data.
7. Add secret-provider plugins later instead of creating a home-grown vault.

Bootstrap:

```text
local development -> environment variables
GitHub Actions     -> repository/environment secrets
hosted control     -> dedicated secret manager via SecretResolver
```

## 19. Persistence

Start small.

### Bootstrap persistence

Use:

- GitHub as canonical issue/PR/repository state;
- SQLite for local control-plane connection metadata, run state and idempotency;
- immutable files/artifacts for canonical evidence bundles where current IDKMesh tooling expects them.

SQLite is available in the Python standard library and avoids requiring a database service during the first product loop.

### Scale-out persistence

Only after the local/hosted control plane proves useful:

- move run/event metadata to a service database;
- retain canonical object IDs/digests and exportable evidence;
- avoid making the database the only copy of integration-critical evidence.

## 20. Observability contract

Every run should retain:

- run ID;
- WorkUnit ID/version/digest;
- exact source repository + SHA;
- selected connector ID/driver/version;
- execution backend;
- model provider/model identity when known;
- external session/job ID;
- timestamps and wall time;
- quota/cost observations when available;
- candidate artifact IDs/digests;
- PR/branch locator if one exists;
- ResultManifest;
- VerificationResult(s);
- final human decision;
- failure category.

Never log secret values.

## 21. Failure taxonomy

Connector errors should be classified, not flattened into "agent failed."

Minimum classes:

- `configuration_error`;
- `authentication_error`;
- `authorization_error`;
- `rate_limited`;
- `quota_exhausted`;
- `provider_unavailable`;
- `source_not_connected`;
- `sandbox_failure`;
- `agent_failed`;
- `timeout`;
- `cancelled`;
- `result_normalization_error`;
- `policy_denied`;
- `verification_failed`.

This supports routing/retry decisions without letting a retry mutate authority.

## 22. User-facing CLI target

The CLI should eventually make connection setup understandable without requiring architecture knowledge.

Example target:

```bash
idkmesh project add MSKazemi/idkmesh

idkmesh connect agent jules \
  --secret-ref env:JULES_API_KEY \
  --source sources/github/MSKazemi/idkmesh

idkmesh connect model gemini \
  --driver openai-compatible \
  --base-url https://generativelanguage.googleapis.com/v1beta/openai/ \
  --secret-ref env:GEMINI_API_KEY \
  --model <model>

idkmesh connect model ollama \
  --driver openai-compatible \
  --base-url http://127.0.0.1:11434/v1 \
  --model <model>

idkmesh connections probe
idkmesh doctor

idkmesh work preview --issue 123
idkmesh run --issue 123 --agent jules
idkmesh run status <run-id>
```

CLI and HTTP API must call the same service layer.

## 23. Web UI target

A dashboard is useful only after the connector kernel works.

Minimum screens:

1. **Projects** — repository and policy.
2. **Connections** — add/test/enable/disable agent/model connections.
3. **Runs** — status, source SHA, agent, result, verification.
4. **Queue** — ready/blocked work and routing explanation.
5. **Evidence** — candidate vs verification vs human decision.
6. **Usage** — quotas/cost where available, without making spend telemetry authority.

Do not block the first self-hosting milestone on a large frontend.

## 24. Self-hosting boundary

IDKMesh should become its own first user only after the connector kernel is independently usable.

Self-hosting means:

```text
IDKMesh issue
 -> IDKMesh Connector Control Plane
 -> external/local agent
 -> candidate PR
 -> existing IDKMesh CI/verifier
 -> human merge decision
```

It does **not** mean:

```text
IDKMesh generates task
 -> IDKMesh selects its own output
 -> IDKMesh approves itself
 -> IDKMesh merges itself
```

Self-hosting tests orchestration and evidence. It must preserve the external integration boundary.

## 25. New-application bootstrap

After self-hosting evidence exists, IDKMesh should support a second repository.

Target:

```text
product brief / requirements
 -> project manifest
 -> GitHub backlog
 -> bounded WorkUnits
 -> heterogeneous agent attempts
 -> tests / verification
 -> PRs
 -> human product decisions
 -> releases
```

A new application should use the same connector profile mechanism. No code path should be special-cased for the `idkmesh` repository.

Proposed future command:

```bash
idkmesh project init --repo OWNER/NEW_APP --profile profiles/default-safe.yaml
```

This should create/configure project metadata and suggested GitHub control surfaces. It should not silently grant workers merge authority.

## 26. Compatibility with current repository architecture

This control plane extends, rather than replaces:

- `interop/adapters.py` — coordinator-facing worker/result normalization;
- `interop/bindings.py` — A2A/MCP semantic transport;
- `docs/architecture/FREE_RESOURCE_MESH.md` — provider/resource discovery;
- `scripts/free_resource_planner.py` — fail-closed zero-cost candidate planning;
- compute-offer/free-compute routing — execution resource admission;
- WorkUnit/ResultManifest/EvaluatorPlan/VerificationResult schemas;
- existing two-attempt/evidence/replay work.

Layer ownership:

```text
Free Resource Mesh         -> what external capacity might exist
Connector Control Plane    -> how a configured provider/agent is contacted
Compute Offer/Router       -> what concrete runtime resource may execute
WorkerAdapter              -> coordinator-facing execution semantics
Verification               -> whether candidate evidence satisfies checks
GitHub/human governance    -> whether canonical state changes
```

Do not create a second WorkUnit, a second verification contract, or a second scheduler.

## 27. Initial connector matrix

| Connection | Mode | First milestone | Notes |
| --- | --- | --- | --- |
| Jules | REST API | **P0** | First production remote-agent connector; plan approval on by default. |
| OpenHands | GitHub-native | **P1** | Observe label/comment-triggered work and normalize resulting PR. |
| goose | local CLI/API | **P1** | Run inside bounded sandbox/node; can use local or remote models. |
| Gemini CLI | local CLI | **P1** | Headless auth must use supported non-interactive credentials. |
| mini-SWE-agent | local CLI | **P2** | Useful heterogeneous software-engineering worker. |
| A2A | protocol | existing/extend | Keep canonical semantic mapping. |
| MCP worker | protocol/tool | existing/extend | Use only where task semantics survive. |
| Gemini model | OpenAI-compatible | **P0** | One common model-driver path. |
| Ollama model | OpenAI-compatible/local | **P0** | Zero-project-spend local inference. |
| vLLM model | OpenAI-compatible/local | **P1** | Useful for self-hosted GPU nodes. |
| OpenRouter | OpenAI-compatible | **P1** | Broad provider access; cost/data policy still applies. |
| LiteLLM | OpenAI-compatible gateway | **P1 optional** | External gateway, not core dependency. |
| OpenAI/Anthropic native | native later | **P2** | Add only for required native features. |

## 28. Security invariants

No connector is considered complete unless it preserves:

- immutable input revision;
- bounded WorkUnit scope;
- explicit path/resource/network policy;
- no merge authority for workers;
- no self-approval;
- secrets separated from task content;
- webhook verification and idempotency;
- candidate output treated as untrusted;
- exact connector/model/runtime provenance where available;
- independent verification;
- human/governance integration;
- fail-closed behavior for unknown versions and unsupported capabilities.

## 29. Product success criteria

The Connector Control Plane is ready for the next stage when a newcomer can:

1. install the relevant IDKMesh product extra;
2. connect one GitHub repository;
3. connect Jules or one local agent;
4. connect/test one model provider where required;
5. preview an issue as a WorkUnit;
6. dispatch one low-risk task;
7. see the candidate and its provenance;
8. see independent verification separately;
9. make the integration decision manually;
10. replay/inspect the run without provider-specific knowledge.

That is the bridge from research infrastructure to a usable development platform.
