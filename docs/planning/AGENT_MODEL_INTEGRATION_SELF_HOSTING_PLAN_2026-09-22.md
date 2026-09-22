# IDKMesh Agent/Model Integration and Self-Hosting Plan

**Date:** 2026-09-22  
**Status:** execution plan for the Connector Control Plane  
**Primary architecture:** [Agent and Model Connector Control Plane](../architecture/AGENT_MODEL_CONNECTOR_CONTROL_PLANE.md)

## 1. Outcome

The project should move through two deliberately separate loops.

### Loop A — develop IDKMesh

Use existing external and local agents to finish the IDKMesh product:

```text
GitHub issue
 -> bounded WorkUnit
 -> Jules / OpenHands / local agent
 -> candidate PR/artifacts
 -> IDKMesh verification
 -> human integration
```

This loop builds the connector/control-plane product itself.

### Loop B — use IDKMesh

Once Loop A is stable enough, use IDKMesh as the orchestration layer for another repository:

```text
new application specification
 -> IDKMesh project profile
 -> backlog + WorkUnits
 -> heterogeneous agents/models
 -> candidate PRs
 -> verification/evidence
 -> human product decisions
 -> releases
```

The second loop is the first meaningful product proof. The new application must not receive a special integration path that bypasses the same contracts used by IDKMesh itself.

## 2. Current foundation

Do not restart from zero.

Already available on current `main`:

- canonical WorkUnit/ResultManifest/EvaluatorPlan/VerificationResult contracts;
- protocol-neutral `WorkerAdapter`;
- A2A/MCP bindings;
- deterministic independent-verification/evidence tooling;
- two-attempt and replay/reporting research;
- Free Resource Mesh and zero-project-spend planning;
- GitHub-native automation and a live Jules path;
- protected `main` required checks;
- an installable `idkmesh` package whose existing `gate-audit` surface must remain dependency-free.

Relevant live work:

- issue #11 — volunteer local-model compute;
- issue #12 — hosted zero-cost agent lanes;
- issue #461 — always-on agent swarm / repository development loop;
- PR #568 — free development automation resource catalog.

The plan below should converge those efforts into one product surface instead of introducing parallel schedulers.

## 3. Architecture decision

Create one **Connector Control Plane** with four plugin boundaries:

1. SCM/project connector;
2. agent connector;
3. model provider;
4. execution backend.

All dispatch still terminates in existing canonical WorkUnit/result/verification semantics.

First implementation choices:

- **remote agent:** Jules REST API;
- **generic model provider:** OpenAI-compatible HTTP;
- **local model:** Ollama through the common model interface;
- **local agent:** goose or Gemini CLI through a bounded CLI/sandbox adapter;
- **SCM:** GitHub;
- **persistence:** GitHub + local SQLite control metadata;
- **secrets:** secret references, initially environment/GitHub Actions secrets;
- **backend API:** optional service over the same Python service layer as the CLI.

## 4. Milestone graph

```text
M0 architecture/API contract
        |
        v
M1 connector kernel + config + doctor
        |
        +-------------------------+
        |                         |
        v                         v
M2 Jules REST connector       M3 model provider layer
        |                         |
        +------------+------------+
                     |
                     v
M4 bounded local agent runner
                     |
                     v
M5 GitHub issue/webhook dispatcher
                     |
                     v
M6 result/PR normalization + verification
                     |
                     v
M7 user-facing CLI + optional HTTP control service
                     |
                     v
M8 IDKMesh self-hosting pilot
                     |
                     v
M9 external/new-application pilot
                     |
                     v
M10 evidence-based expansion
```

M2 and M3 can proceed in parallel after M1.

## 5. M0 — freeze the connector contracts

### Deliverables

- architecture document;
- connector API/data specification;
- explicit distinction between model, agent, execution, and SCM;
- run state machine;
- failure taxonomy;
- secret-reference contract;
- compatibility mapping to existing `interop/`, Free Resource Mesh and verification layers.

### Acceptance

- no new WorkUnit/result schema invented;
- no new merge authority;
- no secret values in tracked config;
- current `gate-audit` dependency-free product remains unaffected;
- architecture/index links pass repository link checks.

### Why first

Without this, every new provider risks creating a provider-specific branch in the coordinator.

## 6. M1 — connector kernel

### Scope

Implement the provider-neutral core before live providers.

Suggested package layout:

```text
idkmesh/
  connectors/
    __init__.py
    types.py
    registry.py
    policy.py
    secrets.py
    routing.py
    errors.py
  control/
    service.py
    store.py
```

Do not assume the exact filenames are permanent; the boundary is more important than names.

### Required behavior

- load a versioned connector profile;
- validate connector kind/driver/settings;
- reject inline secrets;
- resolve only approved `secret_ref` schemes;
- register connectors;
- enable/disable;
- probe health through a driver;
- list capabilities;
- deterministic routing dry-run;
- standardized connector failures;
- SQLite-backed local run/connection metadata or an equally simple stdlib store.

### CLI slice

```bash
idkmesh connections list
idkmesh connections validate <profile>
idkmesh connections probe
idkmesh doctor
```

### Tests

- unknown driver fails closed;
- malformed config rejected;
- raw obvious secret field rejected;
- missing secret reference produces explicit error;
- disabled connector never routes;
- risk/task-class capability mismatch is denied;
- deterministic routing explanation is stable;
- no network required for unit tests.

### Exit gate

A fake connector can pass the complete configure -> probe -> route lifecycle.

## 7. M2 — Jules REST connector

Jules is the first real remote connector because:

- the repository already uses it;
- its GitHub integration is already understood;
- the current alpha REST API exposes source/session/activity primitives.

Current primary references:

- https://jules.google/docs/api/reference/
- https://jules.google/docs/api/reference/overview
- https://jules.google/docs/api/reference/sources/

### Scope

Driver:

```text
agent/jules
```

### Required behavior

- `JULES_API_KEY` referenced via secret resolver;
- list/resolve configured Source;
- verify the expected GitHub repository;
- create Session from a bounded WorkUnit;
- use exact starting branch/source context;
- default `requirePlanApproval=true`;
- store external session ID;
- inspect Activities;
- send feedback when explicitly requested;
- cancel/stop if API semantics support safe cancellation at implementation time;
- normalize completion into canonical run/result state;
- bind any resulting branch/PR/head SHA;
- never map Jules completion to acceptance.

### Safety

- API key never enters prompt/task payload;
- issue text cannot choose source or starting repository;
- no automatic plan approval in the first live cohort;
- no automatic merge;
- one active project-operated Jules task initially, consistent with current repository policy.

### Contract tests

Mock the HTTP boundary and cover:

- 401/auth;
- 404/source missing;
- 429/rate limit;
- provider 5xx;
- incomplete session;
- successful plan/activity lifecycle;
- foreign/unexpected source;
- malformed activity payload.

### Live acceptance

One low-risk public IDKMesh issue:

```text
issue -> WorkUnit -> Jules Session -> candidate PR -> verification -> human decision
```

Retain exact source SHA and session provenance.

## 8. M3 — common model-provider layer

### First driver

```text
model/openai-compatible
```

### First tested providers

1. local Ollama;
2. Gemini OpenAI-compatibility endpoint.

Then add coverage/examples for:

- vLLM;
- OpenRouter;
- LiteLLM proxy.

### Required behavior

- base URL allow/configuration;
- model allowlist;
- auth through secret reference;
- health/model probe;
- request timeout;
- structured response normalization;
- provider/model identity;
- token/usage fields when available;
- no raw key logging;
- external-processing policy flag;
- project-spend policy flag.

### Important boundary

M3 does not dispatch GitHub coding work by itself. It provides a model to a local agent runner.

### Why compatibility first

Gemini officially supports the OpenAI client/schema path, and Ollama/vLLM/OpenRouter/LiteLLM can expose compatible APIs. That gives broad provider coverage without importing every vendor SDK into the core.

### Native adapters

Do not add Anthropic/Gemini/OpenAI native drivers until a concrete feature requires semantics not preserved by the common interface.

## 9. M4 — bounded local agent runner

### Goal

Make one local agent consume an IDKMesh WorkUnit through the same control plane as Jules.

Initial candidate:

- goose;

acceptable alternate:

- Gemini CLI.

Later:

- mini-SWE-agent.

### Generic execution design

```text
WorkUnit
 -> exact repo SHA
 -> disposable workspace/sandbox
 -> local agent preset
 -> configured model provider
 -> candidate patch/log/test artifacts
 -> canonical AdapterExecution/ResultManifest
 -> cleanup
```

### Hard restrictions

- executable comes from an admin-defined allowlist/preset;
- task content cannot construct the shell command;
- no host home mount;
- no SSH/cloud/browser credentials;
- network off unless policy explicitly permits;
- no Docker socket in candidate environment;
- CPU/RAM/disk/wall limits;
- result capture outside worker authority;
- local model endpoint remains local where configured.

### Exit gate

The same trivial WorkUnit is run once through Jules and once through the local agent interface without changing coordinator logic.

## 10. M5 — GitHub dispatcher

### Bootstrap mode

Keep GitHub as the human-visible coordination surface.

Recommended labels:

- `idkmesh:ready`;
- `idkmesh:auto`;
- `agent:jules`;
- `agent:openhands`;
- `agent:local`;
- `risk:low`;
- `risk:medium`;
- `risk:high`;
- `needs-human-review`.

### Event flow

```text
issue opened/edited/labeled
 -> webhook/action event
 -> verify sender/event signature
 -> de-duplicate delivery
 -> load repository policy
 -> issue -> WorkUnit preview
 -> admission
 -> explicit route or auto route
 -> create run
 -> connector submit
 -> post concise run reference to issue
```

### Initial triggers

Use manual or label-based dispatch first.

Do not automatically dispatch on every new issue.

### GitHub App target

Build toward a least-privilege GitHub App for hosted mode.

Bootstrap can use existing authenticated GitHub/Actions context, but do not design the product around a permanent broad PAT.

### Webhook requirements

- signature verification;
- delivery ID idempotency;
- replay protection/store;
- event allowlist;
- untrusted payload handling;
- no secret echo;
- no branch/settings/merge authority in normal mode.

## 11. M6 — candidate/result normalization

This milestone turns vendor-specific results into IDKMesh evidence.

### Required candidate sources

- Jules-created branch/PR;
- GitHub-native agent PR;
- local patch bundle.

### Normalize into

- exact WorkUnit binding;
- worker/connector identity;
- source SHA;
- candidate artifacts;
- artifact digests;
- logs/status evidence where safe;
- ResultManifest;
- verification request.

### Verification flow

```text
agent completion
 -> candidate_ready
 -> canonical ResultManifest
 -> evaluator-owned plan
 -> independent verification
 -> VerificationResult
 -> Evidence Report
 -> awaiting_human_decision
```

### No hidden selection

When multiple agents produce candidates, the system can report evidence and differences. It must not silently merge/select based on model confidence.

## 12. M7 — product API and UX

### CLI

Minimum end-to-end commands:

```bash
idkmesh project add OWNER/REPO
idkmesh connect ...
idkmesh connections probe
idkmesh doctor
idkmesh work preview --issue N
idkmesh run --issue N --agent CONNECTOR
idkmesh run status RUN_ID
idkmesh run cancel RUN_ID
idkmesh evidence show RUN_ID
```

### Optional HTTP service

Expose the connector API defined in the architecture/spec over an optional install extra.

The HTTP service should contain almost no business logic; CLI and server call the same service classes.

### Minimal UI after API

Do not begin with a broad frontend.

The first UI can be a thin connection/run/evidence dashboard after the API is proven.

## 13. M8 — use IDKMesh to develop IDKMesh

This is the self-hosting graduation cohort.

### Entry conditions

- M1–M7 functional;
- required repository CI healthy;
- at least two materially different agent connectors usable;
- no unresolved critical secret/authority bug;
- human integration boundary preserved.

### Cohort

Run **10 bounded real repository tasks** across at least two agent connectors.

Suggested task classes:

- focused tests;
- narrow bug fixes;
- documentation consistency;
- CLI error handling;
- small DX changes;
- bounded refactors with explicit paths.

Exclude initially:

- security policy changes;
- GitHub permission/ruleset changes;
- secret handling changes;
- release signing;
- governance/constitutional changes;
- changes to verification authority;
- broad architecture rewrites.

### Measure every run

- connector/agent/model;
- exact source SHA;
- success/failure;
- verification result;
- CI result;
- reviewer minutes;
- rework;
- wall time;
- quota/cost;
- escaped regression if later observed;
- whether another agent failed the same way.

### Graduation gates

Before claiming successful self-hosting:

- >=10 real bounded runs retained;
- >=2 heterogeneous agent connectors represented;
- every integrated change went through normal PR/human authority;
- zero secret leakage incidents;
- zero worker direct merges;
- failures preserved rather than deleted;
- result/verification provenance inspectable;
- at least one run reproduced/replayed;
- documentation sufficient for another contributor to repeat a run.

The exact success rate is measured, not predeclared as proof.

## 14. M9 — use IDKMesh to build a new application

After M8, select one small non-safety-critical reference application.

The project choice should have:

- a clear product brief;
- automated tests;
- bounded modules;
- no production credentials needed to develop;
- no high-stakes domain;
- enough work for multiple agent types;
- a simple deployable demo.

### Bootstrap flow

```text
1. create/connect new GitHub repository
2. add IDKMesh project profile
3. declare coding/testing/security/product policies
4. connect the same agent/model profile
5. turn product brief into issue backlog
6. approve first bounded WorkUnits
7. dispatch heterogeneous attempts
8. verify candidates
9. human integrates
10. release a small usable application
```

### Critical experiment

Do not special-case the new repository.

If IDKMesh requires repository-specific coordinator code to work on the second application, that is evidence the product abstraction is incomplete.

### Product evidence to retain

- backlog -> WorkUnit lineage;
- agent attempts;
- candidate PRs;
- verification;
- human decisions;
- build/release evidence;
- reviewer attention;
- defects/rework;
- connector portability.

## 15. M10 — expansion only after evidence

After the first second-project application:

- add OpenHands as a direct/native connector if GitHub-native mode is insufficient;
- add mini-SWE-agent;
- add vLLM/volunteer GPU nodes;
- add optional LiteLLM gateway deployment recipe;
- add native model drivers where features justify them;
- add stronger isolation backend;
- add multi-machine scheduling;
- add UI improvements;
- add organization/multi-project tenancy;
- add external secret-manager integrations;
- add A2A remote live-worker deployment.

Do not integrate "all models" by writing one adapter per marketing name. Integrate stable interface families and add native adapters only for real semantic gaps.

## 16. Proposed implementation issues

Create or converge work into these bounded tasks rather than one giant PR.

### C1 — Connector kernel and profile validation

Files likely touched:

- `idkmesh/connectors/*`;
- tests;
- connector profile schema/spec;
- CLI registration.

Acceptance: fake connectors support configure/probe/route with no live network.

### C2 — Jules REST driver

Acceptance: mocked contract tests + one live bounded public run.

### C3 — OpenAI-compatible model driver

Acceptance: local fake server tests + Ollama smoke + optional Gemini smoke when owner supplies credential.

### C4 — Local agent sandbox preset

Acceptance: one bounded goose/Gemini-CLI attempt normalized into canonical result.

### C5 — GitHub dispatch bridge

Acceptance: explicit issue label creates exactly one idempotent run; replayed webhook creates none.

### C6 — Candidate PR/result normalizer

Acceptance: Jules PR and local patch both produce canonical evidence.

### C7 — Control API/CLI

Acceptance: newcomer can configure, probe, dispatch and inspect without editing Python.

### C8 — Self-hosting cohort

Acceptance: retained 10-task evidence set.

### C9 — second-project pilot

Acceptance: one new application reaches a reproducible release through IDKMesh-managed work/evidence paths.

Existing issues #11 and #12 should absorb or be linked to the local-model/hosted-agent portions rather than being duplicated.

## 17. Recommended PR sequence

Keep PRs small enough to verify.

```text
PR-A docs/spec only
PR-B connector types + registry + config validation
PR-C doctor/probe + fake connector tests
PR-D Jules REST connector
PR-E OpenAI-compatible model provider
PR-F local agent execution preset
PR-G GitHub dispatch
PR-H result/PR normalization
PR-I optional control HTTP API
PR-J thin dashboard
```

Do not put all providers into one PR.

## 18. Parallelism

Safe parallel tracks after M1:

```text
Track A: Jules remote connector
Track B: model-provider interface
Track C: GitHub event/label design
Track D: documentation/UX examples
Track E: security/adversarial tests
```

Avoid parallel modification of the central registry/routing contracts until those are stable.

## 19. Definition of "easy to connect"

A provider integration is not easy merely because its Python class exists.

Target onboarding:

```text
1. choose preset
2. provide secret reference if required
3. run probe
4. see green/degraded/error with actionable message
5. assign allowed task/risk classes
6. dispatch a test task
```

No user should need to:

- edit coordinator source code;
- paste API keys into YAML committed to Git;
- understand provider-specific response JSON;
- manually construct ResultManifest;
- manually map an agent's "done" status into IDKMesh states.

## 20. Definition of done for the two-loop objective

### Loop A complete enough

IDKMesh can use its own connector control plane to route real repository tasks to at least two heterogeneous agent paths and retain verification evidence.

### Loop B demonstrated

A second GitHub repository can use the same installed IDKMesh product/configuration model to develop and release a new application without coordinator-core changes.

At that point, IDKMesh has crossed the important boundary from:

```text
research repository about agent coordination
```

to:

```text
a usable coordination product that has developed itself
and then developed another product using the same interfaces
```

That is the milestone the implementation should optimize for.
