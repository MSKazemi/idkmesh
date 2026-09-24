# IDKMesh Product Goals, Component Boundaries, and Development Slice Map

**Date:** 2026-09-22  
**Status:** canonical execution decomposition for the connector-control-plane product track  
**Parent tracker:** [#570](https://github.com/MSKazemi/idkmesh/issues/570)  
**Routing plan:** [Model-Tier Dispatcher and Connector Routing](MODEL_TIER_DISPATCHER_EXECUTION_PLAN_2026-09-22.md)

## 1. North-star product goal

IDKMesh should become a **GitHub-first coordination product for bounded human/AI software work**.

A small team should be able to connect a normal GitHub repository, configure several interchangeable worker/model paths, turn backlog items into bounded WorkUnits, dispatch only when policy permits it, retain candidate/evidence provenance, verify independently, and make explicit human integration decisions.

The default product should work without requiring an always-on IDKMesh server.

The core lifecycle is:

```text
human goal / backlog
 -> bounded WorkUnit
 -> capability + authority routing
 -> admitted connector
 -> bounded attempt
 -> untrusted candidate
 -> canonical ResultManifest
 -> independent VerificationResult
 -> evidence/report
 -> explicit human decision
 -> normal protected integration
 -> retained outcome / learning
```

IDKMesh succeeds when that lifecycle is easy to understand, safe to operate, reproducible, and reusable on a second repository without adding project-specific coordinator code.

## 2. What IDKMesh is not trying to become

The connector-control-plane track must not turn into:

- one custom scheduler per provider;
- a bot that merges its own work;
- an opaque AI project-health score;
- a central identity provider;
- a permanent-server requirement for small teams;
- a GitHub-label-only state machine with no durable run record;
- a new WorkUnit/ResultManifest/VerificationResult format;
- an agent benchmark disguised as a product roadmap.

Provider/model capability, execution, verification, and repository authority remain separate concepts.

## 3. Product success gates

Development should be organized around evidence-bearing gates rather than feature count.

### G0 — Core contracts are stable enough to implement against

Done when:

- canonical WorkUnit/result/verification contracts remain unchanged by connector implementation;
- RoutingDecision semantics are explicit;
- connector kinds and normalized error taxonomy are stable enough for provider work;
- capability tier is separate from authority;
- provider-specific code does not leak into coordinator semantics.

### G1 — One provider-neutral connector kernel works locally

Done when:

- profiles validate;
- registry resolves drivers;
- probes produce normalized health/capability data;
- route resolution is deterministic;
- secret references do not leak values;
- local metadata/idempotency survives process restart;
- CLI can explain why a connector is eligible or rejected.

### G2 — At least two materially different worker paths produce candidates

Done when:

- one remote hosted agent path works;
- one local/model-driven path works;
- both consume the same RoutingDecision contract;
- both bind to exact source revisions;
- neither receives merge authority.

### G3 — GitHub can safely coordinate work without an always-on server

Done when:

- explicit dispatch is idempotent;
- duplicate/replayed events do not duplicate provider work;
- important run state survives ephemeral Actions runners;
- actor/role checks occur before secrets/dispatch;
- restart recovery reconstructs run state;
- GitHub remains the human-visible control plane.

### G4 — Candidate evidence converges independently of provider

Done when:

- remote PR and local patch/artifact candidates normalize to the same result semantics;
- exact source/candidate revisions are retained;
- verification is evaluator-owned;
- negative/failed attempts remain visible;
- human decision remains separate from verification recommendation.

### G5 — A newcomer can operate the system without editing Python

Done when:

- bootstrap/configuration has a no-JSON happy path;
- CLI/Issue Form surfaces explain configuration and routing;
- doctor/preflight finds missing protections/secrets;
- GitHub/Control Tower views show work, evidence, authority, and blockers;
- provider-specific payload knowledge is unnecessary.

### G6 — IDKMesh develops IDKMesh through its own interfaces

Done when:

- at least 10 bounded real repository tasks are attempted;
- at least two heterogeneous worker paths are used;
- failures/cancellations/revisions are retained;
- zero worker direct merges occur;
- exact provenance and reviewer effort are measurable;
- at least one run is replayed/recovered.

### G7 — A second repository reaches a reproducible release

Done when:

- a fresh non-safety-critical repository is bootstrapped;
- at least two humans participate;
- at least 10 WorkUnits run through the same product interfaces;
- restart/idempotency behavior is demonstrated;
- normal protected PR integration is retained;
- a reproducible tagged release is produced;
- no project-specific coordinator branch is added to IDKMesh core.

## 4. Component boundaries

Each component owns one primary responsibility.

| Component | Primary responsibility | Must not own |
| --- | --- | --- |
| C1 Connector kernel | profiles, registry, probes, routing primitives | live provider semantics |
| C2 Jules connector | Jules Source/Session/Activity mapping | routing policy, merge authority |
| C3 Model provider | OpenAI-compatible inference contract | coding-agent loop |
| C4 Local agent runner | bounded local coding-agent execution | project authority |
| C5 GitHub dispatch | GitHub event -> admitted run | provider-specific policy |
| C6 Candidate normalization | provider output -> canonical result/evidence | verification verdict |
| C7 CLI/API | human/operator control surface | duplicate business logic |
| C8 GitHub bootstrap | initialize another repo safely | hidden admin mutation |
| C9 Durable ledger | restart-safe run/event/idempotency state | canonical application code |
| C10 Identity/roles | actor -> stage-specific capability | model capability scoring |
| C11 Pilot | prove no-server second-project lifecycle | new core semantics |
| C12 Governance baseline | GitHub rules/permissions/secret preflight | silent repository admin |
| C13 Work intake UX | structured issue/project planning | execution authority |
| C14 GitHub evidence surfaces | readable GitHub-native status/evidence/release views | mutation authority |
| C15 OpenHands worker | second heterogeneous bounded coding-agent path | verification or merge authority |
| UI Control Tower (#572) | human understanding/decision views | canonical state or autonomous merge |

## 5. Slice-sizing rule

A normal development slice should be small enough that one contributor or agent can understand, implement, test, and review it without needing to redesign adjacent components.

### Preferred slice properties

A slice should normally:

- have one primary behavioral outcome;
- change one contract or one runtime boundary, not both;
- have explicit inputs/outputs;
- include focused tests in the same PR;
- have no unresolved external dependency;
- avoid touching more than one authority boundary;
- preserve backwards compatibility unless the slice explicitly versions a contract;
- be independently revertible.

### Practical size target

This is guidance, not a rigid line-count gate:

- **XS:** fixture/schema/test/doc-only or one pure helper;
- **S:** one module or one interface plus tests;
- **M:** one external integration edge with mocks/fake server plus tests;
- anything larger should usually be split.

A PR that simultaneously changes profile schema, provider HTTP, GitHub dispatch, persistence, and UI is too large.

## 6. Promotion rule: catalogued slice -> GitHub issue

Do not create every future micro-slice as an issue immediately.

Promote a slice to a GitHub issue only when:

1. its upstream contract is merged or explicitly frozen;
2. acceptance criteria are testable now;
3. no active PR already implements the same outcome;
4. it can be completed without speculative adjacent redesign;
5. a contributor can start from the issue without needing a private explanation.

This keeps the backlog actionable instead of aspirational.

---

# 7. Component slice catalog

## C1 — Connector kernel (#574)

**Goal:** provide the provider-neutral local product kernel every later connector uses.

### Already completed

- **C1-A — pure routing kernel:** ConnectorProfile/RoutingDecision, hard filters, deterministic selection, fail-closed tests. Landed through PR #602.

### Ready next

#### C1-B — versioned profile loader and validator

Outcome:

- load connector profiles from JSON;
- validate API version, ID, kind, driver, enablement, policy fields;
- reject inline raw secret values;
- normalize data into ConnectorProfile-compatible objects.

Acceptance:

- valid fixture loads deterministically;
- unknown version/kind/driver fails closed;
- duplicate IDs fail;
- inline credentials fail with a redacted error;
- dependency-free base install remains intact.

#### C1-C — connector registry and fake drivers

Outcome:

- register/lookup drivers by kind + driver ID;
- fake SCM/agent/model/execution implementations;
- deterministic capability declaration.

Acceptance:

- all four kinds can register/probe with no network;
- unknown/duplicate registrations fail clearly;
- registry contains no provider-specific routing branches.

#### C1-D — normalized probe contract

Outcome:

- healthy/degraded/unavailable/disabled result;
- observed capability view;
- checked-at/source metadata;
- no secret material in output.

Acceptance:

- fake probes cover all states;
- disabled connector does not probe live;
- probe result is serializable and stable.

#### C1-E — environment secret references and redaction

Outcome:

- parse `env:NAME`;
- check presence without exposing values;
- materialize only after admission;
- central redaction helper.

Acceptance:

- missing env var is actionable;
- secret never appears in exception/repr/log fixture;
- issue/task text cannot introduce a secret ref.

#### C1-F — local metadata/idempotency store

Outcome:

- stdlib SQLite store for connection/probe/route/run metadata;
- stable idempotency key table;
- restart-safe readback.

Acceptance:

- same key + same digest returns existing record;
- same key + different digest conflicts;
- process restart preserves state;
- no secret values persisted.

#### C1-G — CLI: connections validate/list

Outcome:

- `idkmesh connections validate`;
- `idkmesh connections list`.

Acceptance:

- human-readable and JSON modes;
- non-zero exit for invalid profile;
- no live network required.

#### C1-H — CLI: probe/doctor/route explain

Outcome:

- `connections probe`;
- `doctor`;
- `route explain`.

Acceptance:

- every rejected connector shows stable reasons;
- preview performs no dispatch;
- human-required route is visibly blocked.

#### C1-I — adversarial routing fixture pack

Outcome:

- frozen fixtures for secret injection, command injection, negative-scope phrases, T4 floors, risk mismatch, cost/external-processing denial, duplicate connector state.

Acceptance:

- fixtures exercise public service functions;
- all hard gates remain non-compensating.

**C1 exit gate:** G1.

---

## C2 — Jules REST connector (#575)

**Goal:** first real hosted-agent connector behind C1.

### Slices

- **C2-A — Jules HTTP client shell:** auth header construction, timeout, normalized errors, mocked requests only.
- **C2-B — Source lookup/validation:** configured GitHub source -> exact source record; missing/wrong source fails.
- **C2-C — Session creation:** admitted WorkUnit -> Session request with exact branch/revision and plan approval default-on.
- **C2-D — Session observation:** state/activity polling -> normalized run events.
- **C2-E — feedback/plan approval:** explicit operator-controlled approval/message path where supported.
- **C2-F — candidate discovery:** resulting branch/PR/head SHA -> provider-neutral CandidateReference.
- **C2-G — live low-risk smoke:** one public T1/T2 issue through candidate PR; no merge.

**C2 exit gate:** one reproducible hosted candidate with exact provenance.

---

## C3 — OpenAI-compatible model provider (#576)

**Goal:** one model-provider interface for local/hosted compatible endpoints.

### Slices

- **C3-A — connection/config contract:** base URL, model allowlist, auth ref, timeout, external-processing/spend metadata.
- **C3-B — fake-server probe:** model listing/health contract with deterministic local HTTP fixture.
- **C3-C — inference normalization:** request/response and usage metadata; normalized errors.
- **C3-D — redaction + timeout/rate-limit tests:** headers/secrets never leak.
- **C3-E — Ollama local smoke:** zero-secret local compatibility evidence.
- **C3-F — Gemini compatibility smoke:** optional credentialed evidence only; no hard dependency.
- **C3-G — capability declaration evidence:** configured model -> declared tier/context/tools with explicit provenance.

**C3 exit gate:** one local and one optional hosted-compatible model path without coordinator changes.

---

## C4 — bounded local agent runner (#577)

**Goal:** run one local coding agent inside an allowlisted disposable execution boundary.

### Slices

- **C4-A — AgentPreset contract:** maintainer-owned executable/args/model/execution refs.
- **C4-B — disposable workspace:** exact source SHA checkout/copy, deterministic cleanup.
- **C4-C — process limits:** wall time, disk/output bounds, exit normalization.
- **C4-D — sandbox policy:** environment allowlist, no host credentials/Docker socket, network default-off. Promoted as [#804](https://github.com/MSKazemi/idkmesh/issues/804); no raw-process fallback is allowed by [ADR-0017](../decisions/ADR-0017-local-agents-require-sandbox.md).
- **C4-E — artifact capture:** bounded patch/log outputs outside worker authority, normalized through [Local Agent Execution Boundary v0.1](../specifications/LOCAL_AGENT_EXECUTION_BOUNDARY_V0_1.md).
- **C4-F — first preset:** goose or Gemini CLI adapter behind AgentPreset.
- **C4-G — end-to-end harmless WorkUnit smoke:** local candidate -> normalizer boundary.

### Promoted implementation slices

- [#647](https://github.com/MSKazemi/idkmesh/issues/647) / PR #648 — C4-A AgentPreset contract and free-agent catalog.
- [#652](https://github.com/MSKazemi/idkmesh/issues/652) / PR #653 — C4-B/C exact-SHA disposable workspace and bounded local process result.

These remain reviewable foundations only: no real coding agent is executed by either slice.
The orchestration/artifact layer may advance behind the sandbox interface, but
real goose/Gemini/mini-SWE-agent execution stays blocked until #804 proves a
conforming production backend.

**C4 exit gate:** same WorkUnit semantics as remote agent, different execution path.

---

## C5 — GitHub issue/webhook dispatch bridge (#578)

**Goal:** explicit GitHub action creates exactly one admitted run.

### Slices

- **C5-A — event parser/allowlist:** supported event envelope, repository binding, untrusted payload treatment.
- **C5-B — signature verification:** X-Hub-Signature-256 fixture tests.
- **C5-C — delivery idempotency:** stable delivery/request digest -> one admitted dispatch.
- **C5-D — issue -> WorkUnit preview:** no mutation, exact issue revision binding.
- **C5-E — routing projection:** publish/read labels/status from canonical RoutingDecision.
- **C5-F — authorization gate:** actor/role check before secret resolution.
- **C5-G — explicit dispatch action:** manual/configured label -> run creation.
- **C5-H — bounded GitHub status update:** one idempotent run reference/status surface.

**C5 exit gate:** replayed action cannot duplicate work.

---

## C6 — candidate normalization (#579)

**Goal:** erase provider-specific differences after candidate creation.

### Slices

- **C6-A — CandidateReference v0.1:** PR-backed and artifact-bundle forms.
- **C6-B — WorkUnit/source binding checks:** exact digest/SHA mismatch fails closed.
- **C6-C — PR candidate reader:** exact repo/PR/head SHA/artifact metadata.
- **C6-D — local patch bundle reader:** patch + artifacts/digests.
- **C6-E — ResultManifest builder:** provider-neutral normalized result.
- **C6-F — verification request handoff:** evaluator-owned next stage.
- **C6-G — equivalence fixture:** one PR candidate and one local candidate produce equivalent canonical semantics.

**C6 exit gate:** G4 provider-neutral evidence.

---

## C7 — CLI and optional HTTP API (#580)

**Goal:** operate control plane without editing Python.

### Slices

- **C7-A — service layer extraction:** one application service used by CLI/HTTP/GitHub.
- **C7-B — project/connect CLI:** create/read project + connector profiles.
- **C7-C — preview/routing CLI:** work preview and route explain.
- **C7-D — run CLI:** create/status/cancel with idempotency.
- **C7-E — evidence CLI:** show candidate/result/verification/human state.
- **C7-F — read-only HTTP surfaces:** projects/connections/routes/runs GET/preview.
- **C7-G — mutating HTTP auth boundary:** explicit local/network auth policy.
- **C7-H — HTTP mutation endpoints:** create run/cancel/probe over same service layer.

**C7 exit gate:** one newcomer can configure/probe/dispatch/inspect without provider JSON.

---

## C8 — GitHub-first bootstrap (#596)

**Goal:** adopt IDKMesh in a repository with one command and no server.

### Slices

- **C8-A — ProjectManifest/bootstrap file plan:** exact generated files and ownership rules.
- **C8-B — `init --github --dry-run`:** planned file diff only.
- **C8-C — idempotent file generation:** project config + connector template.
- **C8-D — workflow wrapper generation:** thin pinned preview/dispatch/verify/status workflows.
- **C8-E — owner-action checklist:** secrets, branch protection, environments, app install.
- **C8-F — re-run/update behavior:** preserve user edits and report conflicts.
- **C8-G — fresh-repo fixture test:** bootstrap -> preview without server.

**C8 exit gate:** deterministic no-server project bootstrap.

---

## C9 — durable GitHub-native run ledger (#597)

**Goal:** preserve run state across ephemeral Actions workers.

### Slices

- **C9-A — ledger record schema:** run/event/attempt/idempotency references.
- **C9-B — append-only local Git fixture:** deterministic event serialization.
- **C9-C — optimistic append protocol:** concurrent writer conflict/retry semantics.
- **C9-D — idempotent admission record:** duplicate dispatch -> existing run.
- **C9-E — recovery reader:** reconstruct current run state from events.
- **C9-F — killed-workflow recovery test:** resume observation safely.
- **C9-G — GitHub storage adapter:** evidence branch/equivalent with protected application branch untouched.
- **C9-H — retention/reference policy:** large artifacts transient, essential evidence durable.

**C9 exit gate:** G3 restart-safe coordination.

---

## C10 — GitHub identity, roles, claims, authority (#598)

**Goal:** use GitHub human identity while keeping stage-specific authority explicit.

### Slices

- **C10-A — role/capability vocabulary:** owner, integrator, worker, reviewer, automation, node operator.
- **C10-B — actor context parser:** event actor/team/repository context -> normalized identity.
- **C10-C — policy evaluator:** action + risk + actor -> allow/deny/requires-review.
- **C10-D — claim/release state:** bounded WorkUnit claim semantics.
- **C10-E — stale claim recovery:** time/revision-safe release.
- **C10-F — dispatch authorization integration:** before secret materialization.
- **C10-G — distinct-review requirement:** medium/high-risk policy fixture.
- **C10-H — two-user acceptance fixture:** proposer != dispatcher/reviewer/integrator where configured.

**C10 exit gate:** unauthorized GitHub input cannot broaden authority.

---

## C11 — second-project pilot (#599)

**Goal:** prove IDKMesh is a reusable product, not repository-specific automation.

### Slices

- **C11-A — choose/freeze pilot app:** small, non-safety-critical scope and acceptance criteria.
- **C11-B — fresh repository bootstrap evidence.**
- **C11-C — first WorkUnit preview/dispatch.**
- **C11-D — first remote-agent candidate.**
- **C11-E — second heterogeneous worker path.**
- **C11-F — forced coordinator restart/recovery.**
- **C11-G — duplicate dispatch replay test.**
- **C11-H — 10-WorkUnit cohort completion.**
- **C11-I — human-effort/cost/failure report.**
- **C11-J — reproducible tagged release + retrospective.**

**C11 exit gate:** G7.

---

## C12 — GitHub governance and secret baseline (#607)

**Goal:** turn repository-security assumptions into checked preconditions.

### Slices

- **C12-A — governance policy object:** required/warn/optional GitHub guards.
- **C12-B — branch/ruleset fixture evaluator:** pure metadata -> PASS/WARN/FAIL.
- **C12-C — workflow-permission linter:** generated workflows use least privilege.
- **C12-D — secret-bearing job rules:** trusted event + environment approval boundary.
- **C12-E — fork/untrusted-PR secret tests.**
- **C12-F — CODEOWNERS sensitive-path recommendation generator.**
- **C12-G — optional OIDC example/preflight.**
- **C12-H — `doctor --github` rendering.**

**C12 exit gate:** requested operation cannot run when its required GitHub guard is missing.

---

## C13 — structured WorkUnit intake/project planning (#608)

**Goal:** make bounded work understandable without raw JSON.

### Slices

- **C13-A — Issue Form field contract.**
- **C13-B — generated Issue Form template.**
- **C13-C — issue body -> WorkUnit preview parser.**
- **C13-D — incomplete/malicious fallback behavior.**
- **C13-E — label projection from canonical work/run state.**
- **C13-F — optional GitHub Project field mapping.**
- **C13-G — idempotent Project sync.**
- **C13-H — newcomer no-JSON guide/fixture.**

**C13 exit gate:** structured planning improves usability without becoming authority.

---

## C14 — GitHub-native evidence/dashboard/release surfaces (#609)

**Goal:** understand runs from GitHub before requiring the full Control Tower.

### Slices

- **C14-A — Actions step/job summary renderer.**
- **C14-B — one idempotent issue/PR status comment.**
- **C14-C — durable evidence links after runner teardown.**
- **C14-D — public-safe evidence projection/filter.**
- **C14-E — read-only GitHub Pages generator.**
- **C14-F — pilot release metadata/provenance.**
- **C14-G — optional artifact attestation integration.**
- **C14-H — no-GitHub-Pages fallback behavior.**

**C14 exit gate:** one run is understandable from normal GitHub surfaces.

---

## C15 — OpenHands heterogeneous coding worker (#641)

**Goal:** add a second materially different issue-to-candidate coding worker without giving it verification or integration authority.

### Slices

- **C15-A — guarded manual pilot:** workflow_dispatch only; maintainer supplies an already `agent-ready` low-risk issue; no automatic competition with Jules.
- **C15-B — immutable integration boundary:** pin third-party integration/revision and record exact OpenHands run/conversation identity.
- **C15-C — candidate observation:** resulting branch/PR/head SHA -> provider-neutral candidate reference.
- **C15-D — provider-neutral connector adapter:** move OpenHands behind the common `agent` connector once C1 contracts are integrated.
- **C15-E — hosted/self-hosted execution choice:** preserve WorkUnit semantics across deployment modes.
- **C15-F — heterogeneous comparison smoke:** same bounded task class can be attempted by Jules/OpenHands without duplicate automatic dispatch.
- **C15-G — zero-project-spend experiment:** only claim $0 when the actual OpenHands runtime/model route is measured at $0.

### Safety rules

- `agent-ready` approval remains separate from worker selection;
- OpenHands never counts as independent verification of its own candidate;
- no autonomous merge/approval/settings authority;
- no automatic fan-out to Jules and OpenHands from one issue signal;
- hosted inference is not labeled free unless measured.

**C15 exit gate:** one low-risk issue can follow `issue -> OpenHands run -> candidate PR -> normal IDKMesh CI -> human decision` with exact run/source provenance and no authority widening.

---

## UI — Human Control Tower (#572)

**Goal:** make system state understandable to a human without creating a second source of truth.

### Slices

- **UI-A — local shell/navigation only.**
- **UI-B — Run Evidence Report renderer.**
- **UI-C — attempt/result/verification provenance timeline.**
- **UI-D — routing/connector panel:** tier, authority, eligible/rejected reasons, cost/external-processing.
- **UI-E — human decision view bound to immutable evidence digest.**
- **UI-F — verification debt/capacity panel.**
- **UI-G — participants/resources/authority matrix.**
- **UI-H — repository health/IDKGraph panel.**
- **UI-I — goal/uncertainty view.**
- **UI-J — collaboration/scientific evidence views.**
- **UI-K — bootstrap wizard using C8/C12/C13 services.**
- **UI-L — bounded actions only after read/understand surfaces are proven.**

**UI exit gate:** newcomer can explain goal, work, evidence, uncertainty, authority, and required human decision from one interface.

---

# 8. Dependency graph

The critical path is:

```text
C1 kernel
 |
 +--> C2 Jules -----------+
 |                        |
 +--> C15 OpenHands ------+--> C6 normalization --> verification/evidence
 |                        |
 +--> C3 model --> C4 ----+
 |                        |
 +--> C5 GitHub dispatch -+
 |          |
 |          +--> C9 durable state
 |          +--> C10 authority
 |
 +--> C7 CLI/API
 |
 +--> C8 bootstrap --> C12 governance
 |                 --> C13 intake
 |
 +----------------------------------> C14 GitHub evidence
                                       |
                                       +--> UI Control Tower

C1/C2/C4/C5/C6/C7/C8/C9/C10/C12/C13/C14/C15
                              |
                              v
                          C11 pilot
```

## Parallel work that is safe

After C1 profile/registry/probe contracts are stable:

- C2 Jules HTTP work;
- C3 model-provider work;
- C9 ledger schema/local mechanics;
- C10 role vocabulary/policy evaluator;
- C12 governance metadata evaluator;
- C13 Issue Form UX;
- C14 read-only summary renderer;
- UI read-only renderers.

Avoid parallel edits to the same central routing/profile contract until each version is merged.

# 9. Immediate executable wave

The repository should now focus on a small wave rather than opening every future slice.

## Wave 1 — converge the C1 implementation stack

All C1 micro-slices now have implementation candidates. Do **not** create more C1 feature branches until this stack is reviewed, integrated in dependency order, retargeted to current `main`, and the exact-head gates are green.

- #611 -> PR #624 — profile loader/validator;
- #613 -> PR #625 — registry/fake drivers;
- #614 -> PR #626 — normalized probes;
- #615 -> PR #627 — secret refs/redaction;
- #616 -> PR #628 — SQLite/idempotency;
- #617 -> PR #629 — validate/list CLI;
- #618 -> PR #656 — probe/doctor/route-explain CLI;
- #619 -> PR #657 — adversarial fixtures/tests.

The stacked review order is `#624 -> #625 -> #626 -> #629 -> #656 -> #657`, with #627/#628 converged from the C1-B base at the appropriate points. Queued CI is not passing evidence.

## Wave 2 — can begin once C1-B/C/D contracts are merged

Parallel:

- C2-A/B Jules client + Source lookup;
- C15-A/B guarded OpenHands pilot/integration boundary;
- C3-A/B model config + fake-server probe;
- C9-A/B ledger schema/local append fixture;
- C10-A/B role vocabulary + actor context;
- C12-A/B governance object/evaluator;
- C13-A/B Issue Form contract/template;
- C14-A Actions summary renderer;
- UI-B read-only evidence renderer.

## Wave 3 — live execution edges

Only after common contracts stabilize:

- Jules Session creation/observation;
- OpenHands provider-neutral connector/candidate observation;
- local agent preset/sandbox;
- explicit GitHub dispatch;
- candidate normalization;
- role-gated secret materialization.

# 10. Definition of done for any slice

Use `.github/ISSUE_TEMPLATE/05-development-slice.md` when promoting a catalogued slice into a GitHub issue. The template mirrors the fields below so boundedness is enforced at issue creation time rather than discovered during review.

Every slice issue/PR should include:

- **Goal:** one sentence;
- **Inputs:** exact existing contracts/files/events it consumes;
- **Outputs:** exact new object/API/behavior;
- **Non-goals:** adjacent responsibilities it must not absorb;
- **Acceptance tests:** deterministic and locally runnable when possible;
- **Authority statement:** what the slice is explicitly not allowed to approve/merge/change;
- **Dependencies:** only merged/frozen upstream contracts;
- **Evidence:** test command, fixture, or retained run that proves completion;
- **Follow-on:** the next slice unlocked by this one.

If those fields cannot be written clearly, the slice is probably still too large or too speculative.

# 11. Project management rule

The umbrella tracker (#570) should show only:

- north-star gates G0-G7;
- component status C1-C15;
- current executable wave;
- evidence links;
- blockers.

Detailed implementation belongs in component issues and promoted micro-slice issues.

This keeps #570 readable for humans while still allowing many contributors/agents to work independently.

# 12. Current status at this checkpoint

As of this document:

- connector-control-plane architecture/specification is on `main`;
- model-tier dispatcher execution plan is on `main`;
- the pure C1 routing kernel and focused tests are on `main`;
- C1 implementation candidates exist through the adversarial exit-gate slice (#624-#629, #656, #657); integration/CI evidence remains pending;
- C4-A and C4-B/C have concrete implementation PRs (#648, #653);
- C15 OpenHands is now tracked explicitly by #641;
- CI/Jules generation backpressure is tracked by #651 with implementation PR #655, because verification capacity must bound new agent generation;
- C2-C15 remain product components until their exit gates are demonstrated;
- the next C1 action is convergence/review, not additional feature slicing.
