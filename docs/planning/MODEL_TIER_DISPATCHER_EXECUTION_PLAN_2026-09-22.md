# Model-Tier Dispatcher and Connector Routing Execution Plan

**Date:** 2026-09-22  
**Status:** implementation-grade execution plan  
**Parent:** [#570 — connector control plane and self-hosting](https://github.com/MSKazemi/idkmesh/issues/570)  
**Primary implementation:** [#574 — connector kernel, profile validation, probes, and routing](https://github.com/MSKazemi/idkmesh/issues/574)  
**Dispatch bridge:** [#578](https://github.com/MSKazemi/idkmesh/issues/578)  
**Durable state:** [#597](https://github.com/MSKazemi/idkmesh/issues/597)  
**Multi-user authority:** [#598](https://github.com/MSKazemi/idkmesh/issues/598)

## 1. Objective

IDKMesh needs one auditable answer to this question:

> Given a GitHub issue or canonical WorkUnit, which class of agent/model is allowed to attempt it, which configured connectors are eligible, and what evidence or human authority is required before the result can progress?

The answer must be:

- deterministic from repository-visible policy and current connector state;
- provider-neutral;
- cheap-first without becoming risk-blind;
- separate from merge/integration authority;
- explainable to humans and agents;
- safe in a GitHub-only/no-server deployment;
- reusable by the CLI, HTTP API, GitHub Actions, and GUI;
- capable of escalating from small models to stronger models without replacing a required human gate.

This plan converges the issue/model-router idea into the connector kernel instead of creating a second scheduler.

## 2. One-router rule

There must be exactly one canonical routing service in the product layer.

Do **not** build these as separate decision engines:

- a GitHub label router;
- a Jules router;
- an OpenAI/Gemini router;
- a local-model router;
- a GUI router;
- a self-hosted-server router.

All of them should call the same deterministic route resolver.

The intended flow is:

```text
GitHub issue / product task
          |
          v
WorkUnit preview / canonical task facts
          |
          v
RoutingDecision
  - required capability tier
  - authority mode
  - risk class
  - task classes
  - tool/runtime requirements
  - external-processing policy
  - spend ceiling
  - independence requirement
  - escalation policy
          |
          v
Connector admission
  - enabled?
  - healthy?
  - secrets available?
  - task class supported?
  - risk allowed?
  - capability sufficient?
  - runtime/tool fit?
  - external processing allowed?
  - project spend allowed?
  - capacity available?
          |
          v
EligibleConnector[]
          |
          v
deterministic selection or explicit human choice
          |
          v
Run / attempt
          |
          v
candidate -> normalization -> verification
          |
          v
escalate / stop / human decision
```

## 3. Capability and authority are different axes

A model can be technically capable of a task without having authority to satisfy the task.

Examples:

- a peak model can explain an independent audit, but cannot count as the required independent human witness;
- a small model may be capable of adding a focused unit test and may be eligible for automatic dispatch;
- a strong model may implement a release tool, while release approval remains human;
- deterministic CI may maintain an observatory issue without any LLM.

The route resolver therefore returns both:

```text
required_capability_tier
authority_mode
```

Neither field may be inferred from the other.

## 4. Capability tiers

The architecture uses stable tier semantics, not permanent marketing model names.

| Tier | Name | Intended work | Default dispatch posture |
| --- | --- | --- | --- |
| T0 | deterministic | script/CI-maintained state, validation, mechanical generation | no LLM |
| T1 | small | narrow tests, tiny fixes, low-ambiguity docs, one-module changes | cheap/free agent eligible |
| T2 | standard | bounded multi-file tooling/features with explicit acceptance tests | standard coding agent |
| T3 | strong | architecture-aware work, cross-cutting implementation, migrations, broad synthesis | strong model/agent |
| T4 | peak | core orchestration, statistical/research methodology, security/release/governance-sensitive implementation | peak model plus independent review |

Provider/model names belong in dated connector configuration/evidence, not in tier semantics.

A connector declares what tiers it can serve. The router declares what tier a task requires.

## 5. Authority modes

The first version should support:

| Authority mode | Meaning |
| --- | --- |
| `deterministic` | no agent dispatch should occur |
| `agent_candidate` | an agent may produce a candidate; normal verification/integration still applies |
| `human_gate_then_agent` | a named human/governance gate must be satisfied before or alongside dispatch |
| `human_required` | the acceptance evidence itself must come from a human/external actor; an owner-controlled agent cannot satisfy the issue |

Hard rule:

```text
required model capability never upgrades repository authority
```

A T4 route is still only a candidate-generation recommendation unless project policy says otherwise.

## 6. Canonical RoutingDecision object

#574 should introduce one versioned internal/product object similar to:

```json
{
  "api_version": "idkmesh.io/v1alpha1",
  "routing_id": "route-...",
  "project_id": "MSKazemi/idkmesh",
  "source": {
    "type": "github_issue",
    "number": 564,
    "revision": "<issue-updated-at-or-event-id>"
  },
  "work_unit": {
    "id": "wu-...",
    "digest": "sha256:..."
  },
  "policy_version": "routing-policy-v0.1",
  "required_capability_tier": "T2",
  "authority_mode": "agent_candidate",
  "risk_class": "low",
  "task_classes": ["coder", "tooling"],
  "requirements": {
    "git_write_candidate": true,
    "network": "optional",
    "sandbox": "required",
    "tools": ["git", "python", "pytest"],
    "min_context_class": "repository-bounded"
  },
  "constraints": {
    "external_processing": true,
    "project_spend_usd_max": 0,
    "human_dispatch_approval_required": false,
    "independent_reviewer_required": false
  },
  "escalation": {
    "max_tier": "T4",
    "max_attempts_per_tier": 1,
    "switch_family_after_correlated_failure": true
  },
  "explanation": [
    "bounded multi-file generator change",
    "explicit deterministic acceptance checks",
    "no security/governance/release authority",
    "standard tier sufficient"
  ]
}
```

The exact schema can evolve, but the semantic separation should remain.

## 7. Connector capability declaration

Each configured agent/model path needs machine-readable capability evidence.

Example normalized capability view:

```json
{
  "connection_id": "jules-main",
  "kind": "agent",
  "driver": "jules",
  "enabled": true,
  "health": "healthy",
  "capabilities": {
    "tiers": ["T1", "T2"],
    "task_classes": ["coder", "tests", "docs"],
    "tools": ["git", "tests", "remote_sandbox"],
    "candidate_types": ["github_pull_request"],
    "max_risk": "low"
  },
  "policy": {
    "external_processing": true,
    "project_spend_usd_max": 0,
    "max_concurrency": 1
  },
  "independence": {
    "provider_family": "google",
    "agent_family": "jules",
    "execution_family": "jules-hosted"
  }
}
```

For raw model providers, tier capability is only one part of eligibility. A raw model connection is not automatically a coding-agent connection.

## 8. Deterministic decision order

The resolver must apply decisions in a fixed order.

### Step 0 — freeze task facts

Bind routing to:

- exact repository;
- exact default/base revision;
- exact issue/spec revision;
- canonical WorkUnit or preview digest;
- policy version.

Do not route against mutable text without recording what was seen.

### Step 1 — authority gate

Before cost or model capability:

```text
if acceptance requires human/external evidence:
    authority = human_required
    automatic dispatch = denied
elif task is deterministic workflow-maintained state:
    authority = deterministic
    model tier = T0
elif named human/governance dependency exists:
    authority = human_gate_then_agent
else:
    authority = agent_candidate
```

### Step 2 — hard risk floor

Set a minimum capability/risk posture from semantic task facts.

Examples:

- security, permissions, credentials, release, governance -> at least strong review posture;
- research methodology/statistical inference -> T4;
- core orchestrator/control plane -> T4;
- schema/protocol/migration -> at least T3;
- bounded isolated tests -> usually T1;
- bounded generated publication/tooling -> T2.

Negative-scope text such as "do not change schemas" must not trigger a schema floor.

### Step 3 — residual complexity

For tasks without an explicit reviewed route, measure bounded observable signals such as:

- number of required files/surfaces;
- acceptance checklist size;
- dependency references;
- number of subsystems;
- architecture/research reasoning signals;
- ambiguity;
- external system interaction;
- verification burden.

The score only raises capability above the hard floor. It never lowers a hard floor.

### Step 4 — construct task requirements

Convert issue/work facts into normalized requirements:

- task classes;
- runtime/tool needs;
- network requirement;
- sandbox requirement;
- candidate type;
- external-processing allowance;
- spend ceiling;
- required context class;
- human approval requirement;
- independent verification requirement.

### Step 5 — hard connector filters

A connector is ineligible if any of these fail:

```text
enabled
AND healthy_or_allowed_degraded
AND connector_kind_compatible
AND required_tier_supported
AND task_class_supported
AND risk_allowed
AND tools/runtime_fit
AND candidate_type_supported
AND secret_refs_resolvable
AND external_processing_policy_satisfied
AND project_spend_policy_satisfied
AND concurrency_capacity_available
AND repository/source_binding_valid
AND human_gate_satisfied_if_required
```

Every rejection must have a stable machine-readable reason.

### Step 6 — deterministic selection

Among eligible connectors, prefer a lexicographic decision rather than an opaque learned score for v0.1.

Recommended ordering:

1. smallest tier overprovision above the requirement;
2. zero-project-cost before paid when project policy prefers/forces it;
3. lower trust/external-processing exposure;
4. connector with healthy current probe;
5. connector with available capacity;
6. avoid reusing the same provider/agent family after a correlated failure;
7. lower historical bounded failure rate when enough evidence exists;
8. stable connection ID tie-break.

This keeps the decision explainable.

A future evidence-driven scheduler may replace some ordering with calibrated policy, but the hard gates remain non-compensating.

## 9. Independence and T4 review

For T4 or other routes requiring independent review, the planner should produce a **route set**, not only one connector.

Example:

```text
primary candidate:
  strong/peak coding agent

independent critic/reviewer:
  different provider family where practical
  no shared candidate-generation prompt lineage when avoidable

deterministic verifier:
  repository test/security/evidence gate

human decision:
  when required by authority policy
```

Independence metadata should track at least:

- provider family;
- model family;
- agent framework;
- execution family;
- prompt/policy lineage where known.

Ten attempts from the same model/prompt/runtime are not ten independent reviewers.

## 10. GitHub-visible labels

GitHub labels are a projection of the canonical RoutingDecision, not the source of truth.

Recommended managed labels:

```text
model:t0-deterministic
model:t1-small
model:t2-standard
model:t3-strong
model:t4-peak
model:none

authority:agent-candidate
authority:human-required
authority:human-gate
authority:deterministic

agent:jules-eligible
route:ready
route:blocked
```

The durable route object/ledger record remains authoritative.

The system should be able to regenerate labels after deletion or repository migration.

## 11. Jules dispatch rule

Do not make model-tier classification itself add the literal provider dispatch label.

Use two stages:

```text
route says:
  agent:jules-eligible

dispatcher checks:
  no active claimant/duplicate PR
  issue still unchanged
  WorkUnit admitted
  Jules connection healthy
  current capacity available
  project policy allows external processing
  authority gate satisfied
  idempotency key not already consumed

then and only then:
  call Jules REST connector
  OR add a configured provider-specific trigger label in GitHub-native mode
```

This prevents an issue edit from becoming an accidental provider invocation.

## 12. No-server GitHub deployment lifecycle

The GitHub-first profile should work as:

```text
issue opened/edited
  -> preview workflow
  -> canonical WorkUnit + RoutingDecision
  -> routing labels/status comment/check

authorized dispatch action
  -> idempotency lookup in durable Git-native run ledger
  -> connector admission
  -> secret materialization only after policy pass
  -> external/local run creation
  -> append run event

provider/PR event or scheduled observer
  -> recover run from durable ledger
  -> update state
  -> candidate normalization
  -> verification

verification complete
  -> evidence publication
  -> awaiting human decision

human normal GitHub review/merge
  -> integration state recorded
```

No always-on coordinator is required for the bootstrap profile.

## 13. Durable state requirements

The router must compose with #597.

Minimum persisted route/run facts:

- routing ID and policy version;
- WorkUnit ID/digest;
- issue/project source revision;
- required tier/authority/risk;
- eligible/ineligible connectors and reasons;
- selected connector when dispatch occurs;
- deterministic idempotency key;
- attempt number;
- escalation reason;
- external provider/session/job IDs;
- candidate reference;
- verification references;
- human decision state.

A workflow crash must not make the project forget which provider was already invoked.

## 14. Multi-user authority

The route resolver must consume identity/role policy from #598 before dispatch.

Examples:

```text
issue author:
  may propose work
  does not automatically gain dispatch authority

authorized maintainer:
  may approve low-risk dispatch

agent worker:
  may produce candidate
  cannot approve itself

automated verifier:
  may produce evidence
  cannot merge

human reviewer:
  may supply required human evidence
  only if project policy recognizes the role

integrator:
  normal GitHub protected-branch authority
```

Role checks happen before secrets are resolved or provider work is started.

## 15. Escalation state machine

Escalation is evidence-driven, not "failure -> larger model".

Recommended transition:

```text
T1
 -> T2
 -> T3
 -> T4
 -> T4 + different-family independent reviewer
 -> explicit human decision / task redesign
```

But classify the failure first.

| Failure class | Action |
| --- | --- |
| provider outage / rate limit | retry or switch equivalent connector at same tier |
| sandbox/environment failure | repair environment; same tier |
| missing secret/authorization | stop; operator configuration |
| task too broad | split WorkUnit; do not buy a larger model to compensate |
| acceptance criteria unclear | improve specification; reroute |
| implementation/reasoning failure on clear task | escalate one tier |
| repeated same-family correlated error | switch provider/model/agent family before another identical attempt |
| verifier disagreement | add independent verifier/reviewer; do not silently choose favorable verdict |
| security/governance boundary | stop at policy gate |
| human-required evidence | wait for human/external actor |
| T4 still inconclusive | preserve uncertainty and return to human/product decision |

Every escalation creates a new attempt identity and append-only event.

## 16. Failure taxonomy

#574 should define stable normalized failure categories used by all connectors:

```text
configuration_error
authentication_error
authorization_error
policy_denied
source_not_connected
rate_limited
quota_exhausted
provider_unavailable
capacity_unavailable
sandbox_failure
tool_failure
agent_failed
reasoning_failed
timeout
cancelled
candidate_missing
result_normalization_error
verification_failed
conflict
not_found
human_gate_pending
```

Do not infer model weakness from provider/network/sandbox failures.

## 17. #574 detailed implementation breakdown

### C1.1 — data model and profile schema

Implement:

- ConnectionProfile v0.1;
- normalized capability declaration;
- RoutingDecision v0.1;
- RouteCandidate/rejection reason structure;
- failure taxonomy;
- policy version field.

Acceptance:

- unknown versions/kinds/drivers fail closed;
- raw secrets rejected;
- schema tests cover valid/invalid examples.

### C1.2 — connector registry

Implement:

- driver registration/lookup;
- connector kind validation;
- enable/disable;
- probe interface;
- deterministic capability view.

Acceptance:

- fake SCM/agent/model/execution connectors load without network;
- duplicate IDs and unknown drivers fail clearly.

### C1.3 — route resolver

Implement:

- authority gate;
- hard tier floor;
- normalized task requirements;
- connector hard filters;
- deterministic selection explanation;
- route dry-run.

Acceptance:

- same inputs -> byte-equivalent/semantically deterministic route output;
- ineligible connector never selected;
- every exclusion has a reason;
- T4/human-required fixtures cannot fall through to cheap automatic dispatch.

### C1.4 — secret-reference boundary

Implement:

- `env:NAME` references only at first;
- existence probe separate from value retrieval;
- materialize value only after route admission;
- redaction in errors/logs.

Acceptance:

- missing secret produces actionable non-secret error;
- route dry-run can explain secret availability without leaking value.

### C1.5 — local persistence

Implement minimal stdlib-friendly state for development mode:

- connection metadata;
- probe results;
- route records;
- run metadata;
- idempotency keys.

This can be SQLite locally while #597 defines GitHub-native durable state for no-server deployment.

### C1.6 — CLI slice

Target:

```text
idkmesh connections validate
idkmesh connections list
idkmesh connections probe
idkmesh doctor
idkmesh route explain --issue N
```

The CLI must call the same service/router code that future HTTP/GitHub surfaces use.

### C1.7 — adversarial tests

At minimum test:

- issue text tries to inject a secret ref;
- issue text requests shell executable override;
- low-risk task contains phrase "do not change security";
- human-required task has T4 complexity but remains non-auto-dispatchable;
- connector claims T4 but max risk is low while task is high risk;
- missing secret;
- disabled connector;
- unhealthy connector;
- external processing forbidden;
- project spend ceiling exceeded;
- duplicate route tie;
- stable deterministic tie break.

## 18. #575 Jules implementation after C1

Jules should implement the common `agent` connector.

The connector should receive:

- canonical WorkUnit;
- admitted RoutingDecision;
- exact source revision;
- bounded repository source;
- policy-controlled plan approval mode.

It returns provider-neutral run events and candidate reference.

Live acceptance should use a T1/T2 low-risk issue, not a T4 core architecture issue.

## 19. #576 model-provider implementation after C1

The OpenAI-compatible connector declares model capability but does not itself become a coding agent.

It should normalize:

- endpoint/base URL;
- model ID;
- tier declaration/evidence;
- auth reference;
- context/tool capability;
- usage metadata;
- external-processing policy;
- spend limits;
- errors.

A local agent such as goose can then reference this model connection.

## 20. #577 local agent implementation

A local agent preset combines:

```text
agent preset
+ admitted model connection
+ execution connection
+ WorkUnit
+ RoutingDecision
```

The preset owns executable/argument templates.

Issue text never chooses:

- executable path;
- shell;
- host mounts;
- secret names;
- Docker socket;
- network expansion.

## 21. #578 GitHub dispatch bridge

#578 should consume routing rather than reimplement it.

Flow:

```text
GitHub event
 -> verify event/delivery identity
 -> build WorkUnit preview
 -> call route resolver
 -> publish route projection
 -> require configured dispatch action
 -> role/authority check
 -> idempotency check
 -> create run
```

Initial dispatch triggers should be explicit:

- manual workflow dispatch;
- one configured GitHub label;
- later GUI/CLI call.

Do not dispatch on every issue-open event.

## 22. #579 candidate normalization

The selected connector becomes irrelevant after candidate normalization.

Both:

```text
Jules PR
local patch bundle
```

must converge to:

```text
WorkUnit binding
+ worker/connector identity
+ exact source SHA
+ candidate reference
+ artifacts/digests
+ ResultManifest
+ VerificationResult request
```

This is the proof that the routing layer is provider-neutral.

## 23. #580 CLI/API/GUI contract

The CLI, optional HTTP API, and Control Tower GUI should display the same route explanation:

- required tier;
- authority;
- risk;
- human gate;
- eligible connectors;
- rejected connectors and reasons;
- selected connector if auto-route policy is enabled;
- estimated/known cost class;
- external-processing flag;
- attempt/escalation history.

Do not show only "assigned to Jules" without the explanation that produced it.

## 24. Development sequence

### Phase A — converge design

1. merge the connector architecture/spec/plan;
2. merge this routing execution plan;
3. update #570/#574/#578/#597/#598 links;
4. freeze C1 v0.1 object names sufficiently for implementation.

Exit gate:

- no duplicate routing subsystem planned elsewhere;
- capability vs authority separation documented;
- no-server state/identity dependencies explicit.

### Phase B — implement C1 kernel

PR sequence:

```text
B1 schemas/types/errors
B2 registry/profile validation
B3 fake connectors + probes
B4 route resolver + explanation
B5 local metadata/idempotency store
B6 CLI validate/list/probe/doctor/route-explain
B7 adversarial tests + docs
```

Keep each PR independently reviewable when practical.

### Phase C — connect real workers

Parallel after C1 contract stabilizes:

```text
C2 Jules REST
C3 OpenAI-compatible model provider
C4 local agent preset
```

Each connector must prove it can fail without corrupting canonical state.

### Phase D — GitHub dispatch and durable state

Implement together with explicit dependency coordination:

- #578 dispatch bridge;
- #597 GitHub-native run ledger;
- #598 actor/role policy.

Exit gate:

- replayed event cannot duplicate provider work;
- workflow restart reconstructs run safely;
- unauthorized actor cannot cross dispatch gate.

### Phase E — result/evidence convergence

Implement #579 and verify:

- remote PR candidate;
- local artifact candidate;
- same canonical result semantics;
- independent verification;
- non-selecting evidence report.

### Phase F — usable product surface

Implement #580 and #572:

- CLI first;
- optional HTTP API;
- thin GUI over same service layer;
- no provider-specific business logic in GUI.

### Phase G — self-host IDKMesh

Run >=10 bounded real repository tasks across >=2 heterogeneous connectors.

Measure:

- accepted candidate rate;
- failures by class;
- human reviewer minutes;
- provider/Actions cost;
- route/escalation count;
- duplicate prevention;
- latency;
- regression findings;
- correlated error patterns.

Do not call the system successful merely because agents ran.

### Phase H — second-project pilot

Implement #596–#599 and demonstrate:

- fresh repository;
- `idkmesh init --github`;
- GitHub-only coordinator;
- at least two human actors;
- >=10 WorkUnits;
- restart recovery;
- idempotent replay;
- heterogeneous workers;
- protected human integration;
- reproducible release.

Only after this evidence should GitHub-only be declared the default deployment profile.

## 25. Acceptance matrix for the router

Before enabling automatic low-risk dispatch, prove at minimum:

| Scenario | Expected result |
| --- | --- |
| focused deterministic unit-test issue | T1, agent candidate, cheap connector eligible |
| bounded generator + regenerated artifacts | T2 |
| cross-cutting schema migration | >= T3 |
| statistical uncertainty/research method | T4 |
| release/security/permissions work | strong/peak posture + human gate according to policy |
| independent human review issue | model none / human required |
| workflow-maintained ledger | T0 deterministic |
| low-tier connector on T4 task | rejected: insufficient capability |
| external provider when external processing forbidden | rejected |
| paid provider when project spend max is zero | rejected |
| missing secret | rejected/configuration error |
| same dispatch delivery replayed | existing run returned; no new provider work |
| same-family repeated reasoning failure | next route penalizes/switches family |
| T4 disagreement remains | human decision, no automatic favorable selection |

## 26. Routing policy versioning

Routing behavior affects cost, security, and evidence. Treat it as versioned policy.

Each route records:

```text
policy_version
router_implementation_version
connector_profile_revision
project_policy_revision
```

Do not silently change historical route interpretation after policy updates.

New policy can reroute future attempts while preserving old route records.

## 27. Observability

The Control Tower should eventually report:

- work queue by required tier;
- ready vs blocked by authority;
- connector health/capacity;
- route decisions by provider family;
- escalations by cause;
- cost by accepted candidate;
- failure class counts;
- independent-review coverage;
- human gate wait time;
- duplicate dispatch prevented;
- verifier disagreement;
- attempt correlation/provider-family concentration.

Avoid vanity metrics such as raw agent task count without verified outcome context.

## 28. Security invariants

The routing/dispatcher layer must never let issue/comment content directly set:

- secret reference;
- executable command;
- shell template;
- host path mount;
- Docker socket;
- network expansion;
- repository write token;
- merge/settings authority;
- branch-protection changes;
- provider base URL outside project policy;
- project spend ceiling.

Untrusted issue text describes work. Maintainer/project policy controls authority and execution.

## 29. Definition of done

The routing/dispatcher layer is not done when labels exist.

It is done when:

1. the same task facts produce the same explained RoutingDecision;
2. connector admission is provider-neutral and fail-closed;
3. a small issue routes to a small/cheap connector;
4. a high-impact issue cannot silently route below its hard floor;
5. a human-required issue cannot be satisfied by escalating model size;
6. provider failures do not masquerade as reasoning failures;
7. retries/escalations create distinct append-only attempts;
8. GitHub replay cannot duplicate work;
9. the same route service powers CLI/API/GitHub/GUI;
10. remote and local candidate paths converge to canonical evidence;
11. protected human integration remains outside worker authority;
12. the second-project pilot uses the same rules without coordinator special casing.

## 30. Immediate next development action

After the design PR is current and merged, **#574 is the next coding target**.

The first bounded implementation PR should contain only:

- connector/profile types;
- normalized capability declaration;
- RoutingDecision type;
- error/rejection reason enums;
- pure deterministic route resolver over fake connectors;
- tests.

It should contain **no live Jules HTTP**, no OpenAI/Gemini network calls, no GitHub webhook mutation, and no merge authority.

That gives every later connector one stable contract to implement against.
