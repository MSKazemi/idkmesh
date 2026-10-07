# Engineering Answer Strengthening Plan

**Date:** 2026-10-07  
**Status:** proposed convergence plan  
**Assessment source:** PR #935  
**Scope:** strengthen the parts of IDKMesh that are currently weakest as a professional engineering product and as a falsifiable research program, without broadening the architecture unnecessarily.

## 1. Objective

IDKMesh already has a strong verification/evidence foundation.

The next goal is not to add more concepts. It is to make the project's strongest engineering claims true **end to end**, reproducible on external repositories, and easy for a newcomer to verify.

The central claim to strengthen is:

> **IDKMesh should increase verified useful software work per unit of human attention and compute, while preserving explicit authority, provenance, and reproducibility boundaries.**

The work in this plan is complete only when a skeptical external engineer can reproduce the product path and inspect evidence for that claim without relying on project-authored interpretation.

## 2. What must become stronger

The 2026-10-07 engineering assessment identified six gaps that materially limit the product today.

### G1 — Broad swarm value is not yet proven

Current experiments establish important verifier and coordination findings, but they do not yet prove that the IDKMesh workflow beats a strong single-agent/simple baseline on real external software work.

### G2 — Local hostile-code execution is not yet production-isolated

The local runner correctly avoids claiming that raw subprocess execution is a hostile-code sandbox. A production sandbox gate remains open in #804.

### G3 — Executor admission is not yet atomic against changing inputs

Issue #921 identifies the readiness/claim/input-binding time-of-check/time-of-use gap. A professional executor must prevent stale work from being dispatched or canonically submitted.

### G4 — The golden path is still fragmented

The repository can explain and exercise many components, but a newcomer should not have to learn the whole architecture to execute:

```text
real issue
 -> bounded WorkUnit
 -> admitted worker
 -> candidate
 -> independent verification
 -> evidence
 -> explicit human decision
```

### G5 — Multi-user/API production readiness is incomplete

Issue #713 already tracks the correct API program. The missing work is convergence and qualification, not another API design.

### G6 — Public/distribution surfaces trail current capability

The package, website, and external installation evidence should reflect current supported behavior and make experimental versus production-ready capability obvious.

## 3. Non-goals

This plan deliberately does **not** require:

- adding a new agent framework;
- adding more provider connectors before the golden path is stable;
- building a global scheduler;
- claiming Internet-scale coordination;
- autonomous merge;
- cryptocurrency/token incentives;
- Kubernetes as a prerequisite;
- a new WorkUnit, ResultManifest, EvaluatorPlan, VerificationResult, or evidence protocol;
- another parallel HTTP API;
- replacing the existing research program with a single benchmark score.

The plan is a **convergence program**.

## 4. Definition of done

The engineering-strengthening program is done when all of the following are true.

### Product proof

A new user can install a released IDKMesh package and complete one documented real-repository run that reaches:

```text
bounded task
 -> exact admitted execution binding
 -> two materially different worker attempts
 -> canonical candidate normalization
 -> independent verification
 -> non-selecting evidence report
 -> human accept/reject/escalate decision
```

without either worker or verifier gaining merge authority.

### Runtime trust proof

For local hostile-code execution:

- a conforming sandbox backend is required;
- process, network, filesystem, resource, and credential boundaries are tested;
- the orchestrator fails closed if the sandbox is unavailable;
- execution admission binds exact WorkUnit/source/input revisions atomically;
- stale input changes prevent dispatch/submission.

### Scientific proof

A preregistered real-task benchmark compares at least:

- **A — strong single-worker baseline**;
- **B — simple multi-worker baseline** without the full IDKMesh verification strategy;
- **C — IDKMesh verification-first workflow**.

The comparison uses matched task snapshots and transparent budgets.

The primary result reports **verified useful work per unit of human attention and compute**, not agent count or task count.

### External proof

At least one second repository outside the IDKMesh codebase completes a bounded pilot with:

- at least two human actors;
- at least two materially different worker paths where available;
- at least 10 WorkUnits;
- success, failure, retry/revision, and cancellation evidence;
- duplicate-dispatch/idempotency evidence;
- restart/recovery evidence;
- reviewer time and compute/provider cost;
- one reproducible tagged release.

### Product/API proof

The declared beta API scope has:

- frozen versioned contracts;
- schema/runtime/OpenAPI conformance;
- durable resource/event semantics;
- explicit authentication/authorization profile;
- idempotent mutation semantics;
- bounded reliability/backpressure behavior;
- observability;
- qualification tests;
- official client/documentation for the declared scope.

### Distribution proof

- PyPI Trusted Publishing is active;
- clean Python 3.11 and 3.13 installs are demonstrated from the released distribution;
- current public docs match the released CLI/API surface;
- external setup evidence exists on the supported platform matrix.

## 5. Execution strategy

Do not attack all gaps independently.

Use this dependency order:

```text
W0 capability truth + claim freeze
        |
        v
W1 one golden path
        |
        +--------------------+
        |                    |
        v                    v
W2 runtime trust        W3 benchmark protocol
        |                    |
        +---------+----------+
                  |
                  v
          W4 external pilot
                  |
          +-------+-------+
          |               |
          v               v
     W5 API beta      W6 release/distribution
          |               |
          +-------+-------+
                  |
                  v
          W7 public evidence
```

Some work can execute in parallel, but no later claim should be made before its upstream evidence gate is satisfied.

---

# W0 — Capability truth and claim freeze

## Goal

Create one canonical map of what IDKMesh can prove today and prevent the website, README, package metadata, paper, and API docs from drifting apart.

## Deliverable

Add a maintained capability matrix with one row per public engineering question.

Minimum columns:

- engineering question;
- capability/status;
- canonical implementation path;
- canonical contract/specification;
- user-facing CLI/API/UI;
- evidence/test;
- status:
  - `implemented`;
  - `experimental`;
  - `planned`;
- known limitation;
- last verified source revision.

Example:

| Question | Status | User surface | Evidence | Limitation |
|---|---|---|---|---|
| Can I measure verifier independence? | implemented | `idkmesh gate-audit` | E015-E017 + tests | requires ground-truthed verdict data |
| Can I safely run hostile local code? | planned/experimental | local agent runner | #804 | production sandbox not yet complete |
| Can I deploy a public multi-user API? | planned | API program | #713 | local profile is not public-service auth |

## Required controls

1. README front door links to the matrix.
2. Website renders or mirrors the matrix.
3. Package metadata names only released capabilities.
4. Paper claims link to the same evidence classes where practical.
5. CI detects stale documented CLI command examples.
6. A capability cannot be promoted from experimental to implemented without:
   - implementation;
   - test/evidence;
   - user-facing path;
   - known-limit statement.

## Exit gate

A newcomer can answer, in under one document:

- what IDKMesh does today;
- what is experimental;
- what is planned;
- what evidence supports each implemented claim.

## Existing owners

- #471 — repository/docs/paper stewardship;
- PR #935 — engineering question assessment;
- existing CLI help/README/docs tests.

---

# W1 — Converge one canonical golden path

## Goal

Turn the current Product Spine, local loop, evidence, and decision concepts into one obvious reference workflow.

This is the product path every later experiment and release should reuse.

## Canonical path

```text
1. intake real bounded issue/request
2. derive/freeze WorkUnit
3. compute exact source + input binding
4. explain routing/admission
5. dispatch two isolated attempts
6. observe exact candidate revisions/artifacts
7. normalize to ResultManifest
8. run verifier-owned EvaluatorPlan
9. produce VerificationResult per candidate
10. produce non-selecting Run Evidence Report
11. inspect in Control Tower
12. record explicit human accept/reject/escalate
13. normal protected integration remains outside worker/verifier authority
```

## UX requirement

The reference workflow should be executable with a small number of supported commands.

The user should not need to call internal Python modules manually.

The final command vocabulary may evolve, but it should feel like one product:

```text
idkmesh work preview ...
idkmesh route explain ...
idkmesh run create/execute ...
idkmesh run status ...
idkmesh run evidence ...
idkmesh decision record ...
idkmesh control-tower ...
```

Do not create duplicate commands if an existing command can be extended safely.

## Required golden-path fixture

Retain one small repository task that includes:

- one correct candidate;
- one incorrect or failed candidate;
- independent verification;
- a disagreement/failure visible in the report;
- exact replay;
- pending human decision;
- explicit no-merge authority.

## Required failure cases

The golden path must visibly demonstrate:

- worker process failure;
- verifier/control failure;
- wrong candidate rejected;
- changed source/input binding refused;
- duplicate dispatch replay does not create duplicate external work;
- evidence digest mismatch fails closed;
- no worker can record its own acceptance/integration.

## Exit gate

A newcomer can complete the full path from one bounded request to an inspectable human decision artifact without reading historical conversation documents.

## Existing owners

- #16 — local Verified Swarm Runner v0.1;
- #4 — multi-worker orchestrator;
- #374 — reproducible release gate;
- #682 — Product Spine;
- #572 — Control Tower;
- #578 — GitHub dispatch bridge;
- #579 — candidate normalization.

---

# W2 — Close runtime trust gaps

This work is mandatory before stronger claims about safe autonomous local coding.

## W2-A — Production sandbox

**Owner:** #804.

### Required backend capabilities

- process-tree lifetime containment;
- deterministic cleanup;
- default-deny network;
- explicit allowlist/model-only network mode;
- CPU ceiling;
- RAM/address-space ceiling;
- writable-disk ceiling;
- PID/process ceiling;
- filesystem confinement;
- disposable workspace;
- no host home/SSH/cloud/browser credentials;
- no Docker socket;
- no repository integration credential;
- bounded stdout/stderr/stdin;
- wall-clock timeout;
- capability attestation to the orchestrator.

### Important rule

`subprocess.Popen` can remain an internal process primitive but must never satisfy the hostile-code sandbox capability contract.

### Negative-test suite

Tests must prove:

- forked/background child cannot survive attempt cleanup;
- network access is unavailable by default;
- forbidden host credentials are inaccessible;
- resource limits fail safely;
- workspace escape is blocked;
- sandbox capability downgrade is detected before execution.

## W2-B — Atomic executor admission

**Owner:** #921.

### Admission transaction must bind

```text
project scope
+ WorkUnit digest
+ source revision
+ input/dependency digest
+ readiness state
+ task claim
+ fencing epoch
+ resource/admission decision
= one execution grant
```

### Mandatory rechecks

Revalidate the exact bound inputs:

1. before durable dispatch intent;
2. before canonical candidate submission;
3. before integration if integration consumes mutable upstream state.

### Failure semantics

Use explicit failures such as:

- `task_not_ready`;
- `task_already_integrated`;
- `binding_mismatch`;
- `inputs_changed`;
- `stale_epoch`;
- `not_claim_owner`.

Do not silently refresh a stale binding.

## W2 exit gate

No supported local coding-agent path can execute without a conforming sandbox, and no execution/candidate can cross the canonical boundary after relevant inputs changed.

---

# W3 — Build the decisive benchmark

This is the most important research-strengthening work.

## Goal

Answer:

> **For real repository tasks, when does IDKMesh produce more verified useful work per human attention and compute than simpler alternatives?**

The experiment should be capable of disproving the IDKMesh advantage.

## 3.1 Experimental arms

### Arm A — Strong single-worker baseline

One strong coding agent receives the same bounded task and budget.

It may use ordinary tests/tools, but does not receive extra parallel candidate generation.

### Arm B — Naive multi-worker baseline

Multiple workers attempt the task.

Use a simple aggregation/selection strategy such as:

- first passing candidate;
- majority judge;
- best standalone verifier score;

without IDKMesh's correlation-aware/evidence-first strategy.

### Arm C — IDKMesh

Use:

- bounded WorkUnit;
- heterogeneous attempts where available;
- explicit candidate normalization;
- independent verifier-owned evidence;
- correlation/marginal-evidence diagnostics where applicable;
- non-selecting report;
- explicit human decision.

## 3.2 Task cohort

Use #5 as the bootstrap cohort owner.

Start with 5 replayable tasks, then expand only after the first cohort is valid.

The full evidence target should later include enough tasks for meaningful paired analysis; do not choose the final size merely to obtain statistical significance.

Task families should include:

1. deterministic contract/docs-code consistency;
2. bug reproduction/fix;
3. bounded feature;
4. regression/test repair;
5. refactor/maintenance;
6. API/schema change;
7. reliability/error-handling task;
8. security-sensitive but non-safety-critical task when the sandbox is qualified.

Avoid tasks that can only be judged by subjective style.

## 3.3 Freeze before execution

For every task retain:

- exact repository and source SHA;
- WorkUnit;
- hidden/verifier-owned acceptance criteria;
- evaluator version;
- budget;
- allowed tools;
- worker/model version/configuration;
- stopping rule;
- primary and secondary metrics;
- planned exclusions.

Do not change acceptance rules after seeing candidate outputs.

## 3.4 Primary metric

Use a transparent multi-objective record, with this leading quantity:

```text
verified useful work
-------------------------------
human reviewer attention + compute/provider cost
```

Do not hide the numerator or denominator behind one opaque score.

Record the components separately.

### Verified useful work should include

At minimum:

- task acceptance by frozen verifier criteria;
- regression-free result;
- post-integration defect/rework outcome when available.

### Human attention

Measure actual review/decision minutes where practical.

Do not count owner-controlled autonomous compute as human attention.

### Compute/provider cost

Record:

- provider monetary cost where measurable;
- runtime/CPU/GPU time where practical;
- CI minutes;
- number of attempts;
- verifier cost.

## 3.5 Secondary metrics

Per task/arm record:

- task success;
- verifier recommendation;
- hidden-test result;
- post-merge regression;
- rework required;
- wall-clock latency;
- candidate count;
- duplicate candidate rate;
- verifier disagreement;
- pairwise verifier error dependence;
- effective votes;
- reviewer minutes;
- provider/compute cost;
- retry count;
- execution failures;
- verification/control errors;
- stale-input refusals;
- security-policy blocks.

## 3.6 Independence requirements

Where multiple verifiers are used:

- report nominal verifier count;
- report measured dependence/correlation;
- report effective-vote estimate;
- use known-bad probes when suitable;
- do not present a panel as independent merely because model IDs differ.

## 3.7 Statistical analysis

Use paired task comparisons where possible.

Report:

- per-task outcomes;
- means/medians;
- confidence intervals;
- effect sizes;
- failure/inconclusive counts;
- sensitivity to cost weighting;
- sensitivity to task family;
- negative results.

Do not discard failed tasks because they make the system look worse.

## 3.8 Stopping rule

Preregister the expansion rule.

Example:

- first 5 tasks validate the protocol and instrumentation;
- expand to 10 if replay and metric capture are complete;
- expand further only if verifier/reviewer capacity can keep up and no metric definition needs post-hoc repair.

Do not stop early simply because Arm C leads.

## W3 exit gate

The repository can make a bounded empirical statement such as:

> On task families X/Y/Z under the declared budget and verifier configuration, the IDKMesh workflow changed verified useful work per reviewer-minute by N relative to the single-worker baseline, with these confidence intervals and failure modes.

A valid result may be positive, neutral, or negative.

## Existing owners

- #1 — central multi-agent benchmark question;
- #5 — first replayable benchmark cohort;
- E015-E017 — verifier dependence foundation;
- marginal-evidence tooling;
- benchmark publication infrastructure.

---

# W4 — Prove external-project adoption

## Goal

Move the central result off the IDKMesh repository.

**Owner:** #599.

## Pilot requirements

Use a fresh, non-safety-critical repository.

Required evidence:

- fresh bootstrap from supported docs;
- at least 2 human actors;
- at least 10 WorkUnits;
- at least 2 materially different worker paths where practical;
- one intentional worker failure;
- one rejected/incorrect candidate;
- one cancellation;
- one revision/retry;
- one duplicate-dispatch replay;
- one coordinator restart/recovery;
- exact candidate/source/evidence bindings;
- reviewer minutes;
- provider/compute cost;
- CI minutes;
- setup friction;
- defects/rework;
- reproducible tagged release.

## Pilot report

Publish a retrospective with four sections:

1. **What worked without project-specific code**
2. **What required workaround/customization**
3. **What failed or was confusing**
4. **Which claims the pilot supports and does not support**

## Critical rule

Do not classify the pilot as successful merely because 10 WorkUnits ran.

Success means the product path was usable, trustworthy, recoverable, and inspectable.

## Exit gate

A different repository reaches a real release using the same public IDKMesh interfaces.

---

# W5 — Converge API v1 beta

## Goal

Make the API support the proven product path, not expand into a second product.

**Owner:** #713 and its child issues.

## P0 beta scope

The first beta does not need every future control-plane capability.

It does need stable support for:

- status/readiness;
- projects/work-units/runs;
- attempts/evidence;
- canonical events;
- human decision;
- connector inspection/routing where included in the declared beta;
- bounded SSE if retained in beta scope.

## Required beta gates

### Contract

- every public object has a versioned schema;
- OpenAPI resolves all references;
- examples validate;
- runtime responses validate;
- compatibility CI detects breaking changes.

### Identity/authority

- caller identity is explicit;
- scopes/roles are enforced;
- worker/verifier identities cannot obtain decision/merge authority;
- localhost profile and network profile are clearly different.

### Mutation safety

- idempotency key;
- request digest;
- exactly-one logical mutation on retry;
- conflict semantics;
- immutable historical decision/evidence records.

### Persistence

- durable run/event/evidence/decision model;
- migration strategy;
- corruption/digest checks;
- restart reconstruction;
- retention policy;
- backup/restore for network profile.

### Reliability

- request/body/header limits;
- timeouts;
- concurrency bounds;
- backpressure;
- 429/503 behavior;
- graceful shutdown;
- SSE client limits where applicable.

### Observability

- health/readiness;
- request/error/latency metrics;
- in-flight/overload signals;
- trace propagation;
- privacy-safe telemetry;
- initial SLOs.

### Qualification

- schema/OpenAPI conformance;
- property/fuzz tests;
- concurrency/load tests;
- security/auth bypass matrix;
- restart/recovery tests.

## Exit gate

"API v1 beta" refers to a tagged, reproducible contract with a qualification artifact, not merely endpoints on main.

---

# W6 — Package, release, and external installation

## Goal

Make the strongest current capabilities consumable without cloning the research repository.

## W6-A — PyPI

**Owner:** #769.

Required:

- Trusted Publishing;
- protected publishing environment;
- exact version/tag match;
- clean Python 3.11 install;
- clean Python 3.13 install;
- released CLI reports expected version;
- released commands operate from installed distribution.

## W6-B — Runner release

**Owner:** #374.

The release should include one bounded canonical end-to-end example with:

- WorkUnit;
- candidate/result artifacts;
- independent verification;
- evidence report;
- replay;
- human decision boundary;
- limitations.

## W6-C — External setup matrix

**Owner:** #401.

Collect genuine external evidence across:

- macOS;
- Windows;
- non-Ubuntu Linux.

Record failures as evidence.

## Exit gate

A user can install the released package from PyPI and complete the supported reference workflow without a source checkout, except where a real repository checkout is inherently part of the task.

---

# W7 — Make public evidence match current reality

## Goal

The public story should be generated from or checked against current supported capability.

## Required changes

### Website

The front door should answer only:

1. What problem does IDKMesh solve?
2. What can I run today?
3. What evidence do I get?
4. What is not production-ready?

Then link into research/architecture depth.

### Current command verification

CI should execute or parse every copy-paste command shown on the main start page.

Avoid manually duplicated commands when generated snippets are practical.

### Evidence status

Every major public claim should expose one of:

- implemented;
- synthetic validation;
- observed real run;
- external reproduction/pilot;
- unresolved research hypothesis.

### Version freshness

Show the release version or "verified against source revision" for command-heavy pages.

### Case studies

Publish only evidence-backed cases:

- verifier-panel independence finding;
- first golden-path run;
- first external pilot;
- benchmark result;
- negative/inconclusive findings.

## Exit gate

A visitor does not need GitHub issue archaeology to know what is supported.

---

# 6. Issue ownership map

Do not create duplicate implementation issues for these responsibilities.

| Need | Canonical owner |
|---|---|
| central multi-agent scientific benchmark | #1 |
| first 5–10 benchmark tasks | #5 |
| local Verified Swarm Runner | #16 |
| runner/package reproducibility gate | #374 |
| docs/paper/repo synchronization | #471 |
| second-project no-server pilot | #599 |
| API professionalization | #713 |
| first PyPI release | #769 |
| external install/platform evidence | #401 |
| production local sandbox | #804 |
| atomic executor admission/stale-input checks | #921 |
| engineering assessment | PR #935 |

New issues should be created only for a bounded missing slice that has no existing owner.

---

# 7. Priority order

## P0 — Do now

1. Land a canonical capability truth matrix.
2. Converge the golden path under #16/#374.
3. Close #921 atomic admission.
4. Close #804 production sandbox before production-safe local execution claims.
5. Freeze the first 5-task benchmark protocol under #5.
6. Run the three-arm baseline comparison on the first cohort.
7. Start #599 only after the golden path and trust gates are stable enough that pilot failures measure product reality rather than known missing foundations.

## P1 — Immediately after the P0 evidence path is stable

8. Expand the benchmark cohort only when the first five replay cleanly.
9. Converge #713 to a bounded v1 beta around the proven workflow.
10. Complete #769 and #401.
11. Update the public site from the canonical capability/release data.
12. Publish external-pilot and benchmark evidence.

## P2 — Only after evidence justifies it

- add more provider connectors;
- broader scheduling optimization;
- 100+ node experiments;
- federation/decentralization;
- sophisticated learned routing;
- additional domain packs.

These should not distract from proving the current core claim.

---

# 8. Decision gates

Use hard gates to avoid architecture expansion without evidence.

## Gate A — Can we safely execute?

Pass only when #804 + #921 requirements are satisfied for the declared local execution profile.

If not, continue to label local hostile-code execution experimental.

## Gate B — Can a newcomer complete the full lifecycle?

Pass only when the golden path is executable through supported interfaces.

If not, do not add provider breadth.

## Gate C — Does IDKMesh add measurable value?

Pass only when the baseline benchmark is complete.

Possible decisions:

- **positive:** continue scaling the mechanism;
- **mixed:** narrow claims to task families where it helps;
- **neutral:** simplify the architecture;
- **negative:** reject or redesign the expensive mechanism.

## Gate D — Does it work outside IDKMesh?

Pass only after #599 produces inspectable external-project evidence.

If not, treat self-hosting evidence as insufficient for general adoption claims.

## Gate E — Is the API ready for beta?

Pass only after the declared API scope is schema-frozen, qualified, and tagged.

## Gate F — Is the product ready for broader promotion?

Pass only when released install, docs, benchmark, and external-pilot evidence agree on the same capability boundary.

---

# 9. Metrics dashboard

Do not use raw agent activity as the top-level success metric.

Track these categories.

## Product effectiveness

- WorkUnits attempted;
- verified accepted candidates;
- rejected candidates;
- inconclusive/control failures;
- post-integration regressions;
- rework rate.

## Human attention

- setup minutes;
- review minutes;
- decision minutes;
- manual recovery minutes.

## Resource cost

- provider cost;
- CI minutes;
- CPU/GPU runtime;
- verifier cost;
- retries.

## Trust

- provenance-binding failures;
- stale-input blocks;
- duplicate dispatches prevented;
- sandbox-policy blocks;
- worker/verifier identity overlap;
- verifier error dependence;
- effective verifier votes;
- known-bad probe breaches.

## Reliability

- worker failure rate;
- verifier/control error rate;
- restart recovery success;
- idempotent replay success;
- p95 API latency for the declared bounded workload;
- overload/retry behavior.

## Adoption

- clean install success by supported platform;
- external repository pilots;
- external repeat users/contributors;
- independently reproduced results.

---

# 10. Claim policy

Use this hierarchy in README, website, release notes, and papers.

## Level 0 — planned

Specified but not implemented.

## Level 1 — implemented

Code + deterministic tests exist.

## Level 2 — observed internal real run

Mechanism executed against real runtime/work, but within owner-controlled project conditions.

## Level 3 — controlled benchmark evidence

Compared against frozen baselines under preregistered metrics.

## Level 4 — external reproduction/pilot

Independently or externally operated use confirms the behavior.

## Level 5 — production-qualified

Security/reliability/deployment qualification exists for the declared production profile.

Do not use a higher-level wording for lower-level evidence.

Example:

- a unit test can support "implemented";
- an owner-run CI experiment can support "observed";
- it cannot support "externally validated";
- a localhost token implementation cannot support "multi-user production authentication."

---

# 11. The benchmark result that would most strengthen IDKMesh

The single most valuable result would be a table like this, backed by replayable evidence:

| Metric | Strong single agent | Naive multi-agent | IDKMesh |
|---|---:|---:|---:|
| tasks attempted | N | N | N |
| verifier-accepted regression-free changes | ... | ... | ... |
| post-integration defects | ... | ... | ... |
| median reviewer minutes | ... | ... | ... |
| compute/provider cost | ... | ... | ... |
| wall time | ... | ... | ... |
| nominal verifier count | ... | ... | ... |
| effective verifier votes | ... | ... | ... |
| control failures | ... | ... | ... |
| stale/unsafe executions blocked | ... | ... | ... |

The point is not to force the IDKMesh column to win every row.

The useful scientific result is to discover:

> **which task/risk/verification regimes justify the extra coordination and verification cost.**

That answer would be stronger than a universal "multi-agent is better" claim.

---

# 12. Recommended product positioning during this program

Until the external benchmark and pilot graduate, use:

> **IDKMesh is a verification-first control layer for human and AI software work. It turns bounded tasks into untrusted candidates, binds them to exact provenance, measures independent verification evidence, and keeps final integration authority separate from workers and verifiers.**

Avoid presenting the project as a generally proven large-scale swarm system.

After the benchmark/pilot, strengthen the wording only to the level supported by the data.

---

# 13. Immediate execution checklist

The next concrete sequence should be:

- [ ] merge/review PR #935 or otherwise retain its assessment as the baseline;
- [ ] add canonical capability-status matrix and front-door link;
- [ ] reconcile #16/#374 into one current golden-path acceptance checklist;
- [ ] complete #921;
- [ ] complete #804;
- [ ] freeze first five benchmark tasks under #5;
- [ ] preregister A/B/C benchmark arms and budgets before running them;
- [ ] retain raw per-task evidence and publish the first cohort result;
- [ ] execute #599 on a fresh repository;
- [ ] converge #713 to the minimum v1-beta scope actually required by that workflow;
- [ ] publish through #769;
- [ ] collect #401 external-platform evidence;
- [ ] refresh public website from the capability/release truth source;
- [ ] publish benchmark and pilot results, including negative findings.

## Final rule

**Do not add another major architectural layer until one of these gates demonstrates a concrete need for it.**

The shortest path to making IDKMesh stronger is now:

```text
fewer new concepts
+ stronger runtime boundaries
+ one simple product path
+ real baseline comparison
+ external repository evidence
+ qualified release
= professional credibility
```
