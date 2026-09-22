# Use IDKMesh to Build Another Software Project

**Status:** practical adoption guide for the current alpha framework  
**Audience:** project owners, maintainers, human contributors, AI-agent operators, and automation builders

This guide answers the practical question that is easy to miss in the rest of the repository:

> How do I start a new application repository and use IDKMesh ideas and contracts so humans, AI agents, tools, and CI can collaborate without giving any one worker too much authority?

The short answer is:

**Use Git/GitHub as the canonical project state, use bounded Work Units as the unit of delegation, let humans and agents produce candidate work, verify candidate work separately, and keep integration authority outside the worker and verifier.**

Today, IDKMesh can support this as a **GitHub-native operating model plus executable contracts and validation components**. The full one-command Verified Swarm Runner that automatically discovers, dispatches, verifies, and integrates arbitrary external projects is not finished yet.

That distinction matters throughout this guide.

### Where does IDKMesh run?

For a normal new software project, the recommended deployment is **GitHub-first and server-optional**.

You should not need to operate a permanent IDKMesh server just to use the collaboration model. The target repository holds project/policy state, GitHub Actions runs event-driven coordination, hosted agents run on their providers, and optional `idkmesh-node` workers run on contributor/project machines only when local models or special compute are needed.

See [GitHub-First Deployment and Multi-User Operation](architecture/GITHUB_FIRST_DEPLOYMENT_AND_MULTIUSER.md) for the exact deployment profiles, durable-state plan, multi-user role model, and criteria for when a separate control service becomes justified.

## 1. What IDKMesh adds to an ordinary GitHub project

An ordinary development loop often looks like this:

~~~text
issue -> developer or agent -> pull request -> tests -> merge
~~~

An IDKMesh-style loop makes the trust and evidence boundaries explicit:

~~~text
goal
  -> bounded issue / Work Unit
  -> capability and risk routing
  -> human or agent worker
  -> candidate branch / artifacts
  -> worker result + provenance
  -> independent verifier
  -> verification evidence
  -> protected integration decision
  -> measured outcome
  -> next bounded work
~~~

The most important invariant is:

~~~text
worker success != acceptance
verification recommendation != merge authority
CI success != independent human review
~~~

IDKMesh is therefore useful when the hard problem is not merely generating code, but coordinating multiple imperfect contributors and preserving enough evidence to decide what should become canonical.

## 2. Who should use this approach

This operating model is a good fit for:

- software teams using more than one AI coding agent or model;
- open-source projects where humans and agents contribute asynchronously;
- teams that want GitHub issues and pull requests to remain the shared coordination surface;
- projects that want explicit provenance for AI-assisted changes;
- teams that need stronger separation between implementation and review;
- research or experimental projects comparing agents, prompts, models, or verification strategies;
- projects where high-risk changes should be routed to stronger models, specialist humans, or stricter verification.

It is probably unnecessary for a tiny throwaway project where one person is comfortable owning generation, review, and integration alone.

It is also not yet a finished turnkey solution if the requirement is:

- install one package;
- connect every major model provider;
- automatically decompose every goal;
- dispatch live workers across many machines;
- verify every result;
- merge correct work without a human-controlled integration policy.

Those are reference-product goals, not current production claims.

## 3. The three layers to keep separate

A clean adoption keeps three things distinct.

### Layer A — your application repository

Your new project remains the canonical source of truth for:

- code;
- tests;
- documentation;
- GitHub issues;
- pull requests;
- CI results;
- releases;
- decisions.

IDKMesh does not need to replace GitHub.

### Layer B — IDKMesh coordination contracts

These define how work is bounded and how evidence is interpreted:

- ProjectManifest;
- DomainPack;
- WorkUnit;
- ResultManifest;
- EvaluatorPlan;
- VerificationResult;
- integration policy;
- provenance and evidence requirements.

See [ProjectManifest and DomainPack interfaces](specifications/PROJECT_DOMAIN_INTERFACES.md) and [schema navigation](../schemas/README.md).

### Layer C — replaceable participants

Workers and verifiers can be:

- humans;
- GitHub-native coding agents;
- local coding agents;
- hosted model-backed agents;
- A2A-compatible agents;
- MCP-connected tools or agents;
- deterministic scripts;
- test runners;
- security scanners;
- benchmark workers.

The project contract should describe **capabilities and authority**, not hard-code one model vendor.

## 4. End-to-end flow

~~~mermaid
flowchart TD
    A[Project goal or GitHub issue] --> B{Small and testable enough?}
    B -- No --> C[Research or decompose]
    C --> B
    B -- Yes --> D[Create bounded Work Unit]
    D --> E[Classify risk, permissions, dependencies, evidence]
    E --> F[Route to lowest-cost capable worker]
    F --> G[Human or agent works on isolated branch/worktree]
    G --> H[Candidate artifacts + worker provenance]
    H --> I[Independent verification on exact candidate revision]
    I --> J{Required checks and evidence satisfied?}
    J -- No --> K[Reject, revise, replan, or escalate]
    K --> D
    J -- Yes --> L[Protected PR / integration review]
    L --> M{Human or governance decision}
    M -- Reject --> K
    M -- Accept --> N[Merge into canonical branch]
    N --> O[Observe outcome and record evidence]
    O --> A
~~~

The flow is intentionally a loop. A failed attempt is not an exceptional state; it is evidence that should improve the next Work Unit, routing decision, validator, or policy.

## 5. Start from an empty directory

The following is the recommended conceptual sequence for a new application.

### Step 1 — create the project locally

~~~bash
mkdir myapp
cd myapp
git init
~~~

Create the smallest runnable skeleton for the application, for example:

~~~text
myapp/
  README.md
  src/
  tests/
  docs/
  .github/
    workflows/
~~~

Commit the baseline before inviting agents to work:

~~~bash
git add .
git commit -m "Initial project baseline"
~~~

### Step 2 — create the GitHub repository

Create the remote repository and push the baseline using the GitHub UI, GitHub CLI, or your normal Git workflow.

The important property is not the creation command. It is that the repository has one canonical default branch and all later candidate work can be traced to exact Git revisions.

### Step 3 — protect the canonical branch

Before connecting autonomous workers:

- require pull requests for changes to the main branch;
- require the project test/CI gate;
- restrict direct pushes;
- do not give ordinary worker credentials merge authority;
- keep workflow and secret permissions minimal;
- require stronger review for security, CI, dependency, release, or governance changes.

The application repository, not an agent prompt, is the authority boundary.

### Step 4 — add a project-side IDKMesh area

A practical project-side layout is:

~~~text
myapp/
  .idkmesh/
    README.md
    project.json
    work-units/
    results/
    verification/
    evidence/
~~~

This layout is a recommended adoption convention, not yet an official bootstrap generated by a stable idkmesh init command.

Use the current reference contracts as templates:

- [self-improvement ProjectManifest](../examples/projects/idkmesh-self-improvement.project.json);
- [software-engineering DomainPack](../examples/domain-packs/software-engineering-v0.1.domain-pack.json);
- [WorkUnit v0.2 example](../examples/work-units/phase0-smoke.work-unit.json).

The current ProjectManifest validator in experiments/project_contracts.py resolves manifests and DomainPack paths inside the IDKMesh checkout. It is therefore useful as the contract reference and self-test today, but the repository does **not** yet provide a polished arbitrary-external-repository bootstrap/validation CLI. Do not mistake the reference contract for a completed external-project installer.

### Step 5 — define project policy before selecting models

The project policy should answer these questions first:

1. Which kinds of work may be delegated?
2. Which repository paths may a worker change?
3. Which actions require a sandbox?
4. Can a worker use the network?
5. Which secrets, if any, may be materialized at runtime?
6. Which risk classes can run autonomously?
7. How many independent verifiers are required?
8. Which checks must pass?
9. Who can integrate into the protected branch?
10. What cost, token, time, or compute budget is allowed?

Only after these are defined should the project choose models or agent products.

This prevents a provider integration from accidentally defining project governance.

## 6. Connect humans, agents, and models

Different participants can join the same flow without becoming the same kind of actor.

### Human contributor

A human can:

1. claim a bounded issue or Work Unit;
2. create a branch;
3. implement the requested change;
4. run the declared checks;
5. open a PR;
6. report evidence and uncertainty;
7. stop before self-approval.

A human worker follows the same scope contract as an automated worker.

### GitHub-native coding agent

A GitHub-native agent can be given:

- issue read access;
- repository read access;
- permission to create a branch or candidate PR;
- a bounded task description;
- required tests;
- forbidden paths.

It should normally **not** receive direct main-branch or merge authority.

The GitHub issue is the routing and coordination surface; the PR is the candidate artifact.

### Local or hosted coding agent

A local agent can work in:

- a disposable clone;
- a Git worktree;
- a container;
- a VM or sandbox;
- a provider-owned isolated workspace.

Give it:

- exact repository and base revision;
- bounded objective;
- allowed and forbidden paths;
- declared tool/network permissions;
- required outputs;
- validators;
- evidence requirements;
- budget;
- stop conditions.

Credentials should be runtime-scoped and short-lived where possible. Do not store API keys or secrets inside Work Units or committed provenance files.

### A2A/MCP-compatible integration

IDKMesh already contains protocol-neutral worker-adapter infrastructure and A2A/MCP mappings under [interop](../interop/README.md).

Use these protocols as **transport and tool-integration surfaces**, while keeping IDKMesh semantics in:

- Work Units;
- provenance;
- evidence;
- verification;
- risk;
- authority.

A successful A2A or MCP call is transport success, not acceptance of the work.

### Deterministic tools

Do not use an LLM when a deterministic tool is the better worker or verifier.

Examples:

- compiler;
- formatter;
- unit test;
- schema validator;
- dependency checker;
- static analyzer;
- benchmark;
- link checker.

A useful routing rule is: **deterministic before probabilistic, smaller capable model before larger model, and stronger verification as risk rises.**

## 7. Turn backlog items into small Work Units

The ideal Work Unit is not merely “an issue that sounds small.” It is a task with enough structure that a different worker and verifier can agree on what was asked.

A machine/agent-friendly Work Unit should make these fields explicit:

| Field | Question it answers |
| --- | --- |
| ID | Which task is this? |
| exact base revision | What repository state is the worker changing? |
| objective | What single result is wanted? |
| inputs | What may the worker rely on? |
| outputs | What artifacts must be produced? |
| allowed paths | Where may the worker write? |
| forbidden paths | What must remain untouched? |
| capabilities | What must the worker be able to do? |
| security/risk | How dangerous is the work? |
| permissions | Network, filesystem, secrets, process limits |
| dependencies | What must already exist? |
| validators | Which checks are required? |
| evidence | What proof must be retained? |
| budget | Time, compute, human attention, tokens, spend |
| failure semantics | Stop, retry, replan, or escalate |
| provenance | Who or what created the Work Unit? |

The current machine-readable definition is [WorkUnit v0.2](../schemas/work-unit-v0.2.schema.json).

### Small-chunk rules

Prefer a Work Unit that has:

- one primary intent;
- one main candidate artifact or tightly related set of artifacts;
- one exact starting revision;
- explicit dependencies;
- explicit acceptance checks;
- a bounded write surface;
- enough context to work without private chat history;
- a change that can be reviewed and reverted independently.

Split a task when it combines materially different questions, for example:

~~~text
research -> architecture decision -> implementation -> migration -> deployment
~~~

Those are usually separate Work Units because each stage can invalidate the next one.

Also split:

- implementation from independent verification;
- high-risk workflow/security changes from ordinary feature work;
- uncertain research from routine coding;
- broad refactors from the bug fix that motivated them;
- test-infrastructure changes from the product behavior they are supposed to test.

A good test is:

> Can a reviewer understand what changed, why, and how it was checked without reading the worker's private conversation?

If not, the unit is probably too large or underspecified.

## 8. Recommended routing policy for LLMs and agents

The core contract should remain vendor-neutral. Model names change quickly; capability classes are more stable.

A practical routing ladder is:

| Tier | Typical worker | Best for |
| --- | --- | --- |
| T0 | deterministic tool/script | formatting, schema checks, tests, mechanical transformations |
| T1 | lightweight/fast model | issue classification, simple docs, narrow edits, boilerplate |
| T2 | strong general coding/reasoning model | normal features, bugs, refactors, multi-file reasoning |
| T3 | peak model or specialist human | high uncertainty, security-sensitive design, difficult debugging, architecture, failed lower-tier attempts |

This is a **recommended routing policy**, not a claim that the current repository already provides one universal live router across every vendor.

Use this decision order:

~~~text
1. Is the task allowed by project policy?
   no -> stop/escalate

2. Can a deterministic tool solve it?
   yes -> T0

3. What capabilities are required?
   select only workers that match them

4. What is the risk class?
   higher risk -> stronger worker constraints + stronger verification

5. How much ambiguity, context, novelty, and cross-file reasoning is present?
   low -> T1
   normal -> T2
   high or repeated failure -> T3

6. Can the result be independently verified?
   no -> decompose or require human/specialist review

7. Route to the lowest tier that is capable of producing useful evidence.
~~~

Never use model size as an authority rule.

~~~text
bigger model != permission to merge
higher benchmark score != permission to weaken verification
same model twice != automatically independent verification
~~~

Independence can be weakened by shared model families, prompts, tools, datasets, providers, or failure modes even when two separate agent processes are used.

## 9. Worker protocol

For each assigned Work Unit, the worker should follow a bounded loop:

~~~text
inspect exact base revision
 -> confirm scope and permissions
 -> make the smallest candidate change
 -> run required local checks
 -> record exact commands/results
 -> record tool/model provenance when practical
 -> identify remaining uncertainty
 -> open/update candidate PR or result artifact
 -> stop
~~~

The worker should not silently expand scope just because it notices another problem.

If a blocker appears, the correct outputs are often:

- a precise blocker;
- a smaller follow-up Work Unit;
- a research question;
- a failed reproduction;
- a request for stronger capability.

“Could not complete safely” is better evidence than an unbounded attempt.

## 10. Candidate and ResultManifest

A worker completion is a **candidate**, not an accepted result.

For software work, the candidate normally consists of:

- branch or commit;
- diff;
- test output;
- logs needed for reproduction;
- artifact hashes where relevant;
- worker/tool/model provenance;
- known limitations or uncertainty.

The [ResultManifest contract](specifications/RESULT_MANIFEST_V0_1.md) exists to record worker-produced artifacts and claims without granting acceptance authority.

In a lightweight GitHub-only adoption, a PR description can initially carry the same information even before every project automates the JSON contract.

## 11. Independent verification

Verification should target the exact candidate revision, not a moving branch.

A verifier should:

1. read the Work Unit and acceptance criteria;
2. inspect the exact candidate head SHA;
3. use verifier-owned checks rather than trusting worker claims;
4. rerun required tests or reproductions where practical;
5. check scope violations and unexpected changes;
6. inspect risk-sensitive surfaces;
7. record findings and evidence;
8. recommend accept, reject, revise, or escalate;
9. stop before integration if the project requires a separate integrator.

A good verifier attempts to **falsify** the candidate, not merely confirm the worker's summary.

For model-based verification, diversity can help, but nominal reviewer count is not the same as independent evidence. If a project collects many reviewer verdicts, [idkmesh gate-audit](GETTING_STARTED.md#path-b-audit-a-review-or-verifier-panel) can diagnose correlated failures from observed verdict data.

## 12. Integration

The integrator or maintainer decides what becomes canonical.

Before merging, check:

- Work Unit scope;
- exact candidate revision;
- required CI;
- required verification evidence;
- unresolved findings;
- risk-specific review;
- branch protection;
- migration or rollback implications;
- documentation changes;
- provenance when required.

The preferred default for software projects is:

~~~text
automatic candidate generation: allowed within policy
automatic self-acceptance: forbidden
automatic merge: off unless an explicit future policy safely enables it
protected human/governance integration: on
~~~

The current reference software-engineering ProjectManifest follows this pattern.

## 13. State machine for humans and agents

A project can implement the workflow with GitHub labels, project fields, or an external queue. The exact label names are project-specific, but the state transitions should remain explicit.

| State | Entry requirement | Exit artifact |
| --- | --- | --- |
| draft | idea exists | clarified issue or research question |
| ready | bounded objective and checks exist | Work Unit |
| claimed | eligible worker selected | worker identity + base revision |
| candidate | worker produced artifacts | branch/PR + result evidence |
| verifying | verifier owns evaluation | check/review evidence |
| revise/reject | required evidence failed | findings + next action |
| verified | required checks satisfied | verification result/recommendation |
| integration review | protected authority inspects evidence | accept/reject/escalate decision |
| integrated | canonical branch changed | merge commit/release artifact |
| observed | outcome measured | follow-up evidence or next Work Unit |

Agents should be able to parse these states without depending on private conversational context.

## 14. A minimal GitHub operating model that works today

You can adopt the principles before the full runner exists.

### Minimal profile

Use:

- GitHub issue = human-readable task;
- WorkUnit JSON = machine-readable task for important or automated work;
- branch/worktree = isolated worker attempt;
- PR = candidate;
- CI = deterministic evidence;
- separate reviewer = verifier;
- PR maintainer = integration authority;
- issue/PR comments or committed evidence = provenance and outcome record.

This gives a real coordination improvement without waiting for every automation component.

### More automated profile

Add:

- ProjectManifest;
- software-engineering DomainPack;
- worker adapters;
- A2A/MCP bindings;
- automated ResultManifest generation;
- verifier-owned EvaluatorPlans;
- VerificationResult generation;
- panel gate-audit where multiple reviewers are used;
- capability/risk routing;
- sandboxed execution;
- automated queue and scheduling.

Each new automation layer should remove manual friction **without collapsing the authority boundaries**.

## 15. Four example scenarios

### Scenario A — solo developer with two AI agents

Use one agent as builder and a different model/tool or deterministic test stack as verifier.

The human keeps merge authority.

Good first adoption because the workflow is simple while still preventing one coding agent from self-certifying.

### Scenario B — small engineering team with multiple model providers

Use GitHub issues as shared Work Units, route narrow work to cheaper/faster workers, difficult work to stronger workers, and keep verification independent from the producing agent where practical.

Collect verdict data if several automated reviewers are used and periodically audit whether they are actually independent.

### Scenario C — open-source project with humans and agents

Humans and agents use the same bounded issue/PR path.

Do not create a privileged “AI lane” that bypasses contributor rules. Instead expose:

- starter Work Units;
- clear ownership;
- exact test commands;
- review requirements;
- provenance expectations;
- protected integration.

This keeps the repository understandable to contributors who do not use the same agent tools.

### Scenario D — research or reproduction project

Use read-only or proposal-only ProjectManifest policy, separate research Work Units from implementation Work Units, require artifact hashes and reproduction evidence, and keep the repository write boundary narrow.

The existing research-replication ProjectManifest demonstrates this pattern.

## 16. Best practices

### Prefer contracts over giant prompts

A long prompt can contain useful context, but it should not be the only place where scope, permissions, tests, and authority rules live.

Durable project state belongs in repository artifacts.

### Prefer exact revisions

Route and verify against immutable SHAs when possible.

A verifier evaluating “whatever is currently on the branch” can accidentally inspect a different artifact from the one the worker produced.

### Prefer capability matching over vendor matching

Ask:

> Which capabilities and trust level does this task require?

before asking:

> Which vendor should receive it?

### Prefer cheap evidence early

Run deterministic checks before expensive model review.

Do not spend frontier-model attention to discover a formatting error or failing unit test.

### Increase verification before increasing generation

If candidates are accumulating faster than they can be reviewed, add review capacity or reduce generation.

More workers are harmful when verification debt grows without bound.

### Separate confidence from proof

A worker saying “I am 95% confident” is provenance about the worker state. It is not substitute evidence.

### Keep secrets out of task artifacts

Work Units may describe required permission scopes. Secret values belong in protected runtime stores.

### Make failure useful

A failed attempt should leave:

- exact revision;
- reason for failure;
- commands run;
- logs or evidence;
- next recommended action.

## 17. Anti-patterns

Avoid:

- “build the whole application” as one Work Unit;
- one agent planning, coding, reviewing, and merging its own change;
- giving an agent a repository-wide write token when only one path is needed;
- asking multiple identical agents for votes and assuming the votes are independent;
- letting CI success silently become automatic approval;
- routing by model brand before checking task capability and risk;
- storing important decisions only in private chats;
- changing the task objective mid-execution without versioning or replanning;
- allowing agent output volume to exceed reviewer capacity;
- using a stronger model as a reason to weaken permissions or evidence requirements.

## 18. Machine-friendly bootstrap checklist

A new external application is ready for an IDKMesh-style development loop when all of the following are true:

~~~text
[ ] repository exists and has a canonical default branch
[ ] main/default branch is protected
[ ] baseline CI is reproducible
[ ] project goals and contribution rules are in the repository
[ ] project policy defines allowed work and integration authority
[ ] ProjectManifest/DomainPack strategy is selected
[ ] worker roles/capabilities are defined
[ ] verifier role is separate where required
[ ] agents receive least-privilege credentials
[ ] tasks can be expressed as bounded Work Units
[ ] every automated task has explicit stop/failure semantics
[ ] candidate work is isolated on a branch/worktree/sandbox
[ ] required evidence is attached to the exact candidate revision
[ ] merge authority remains protected
[ ] outcomes feed back into future tasks/routing
~~~

## 19. What should be automated next

For external-project adoption to become truly easy, IDKMesh should converge toward a bootstrap such as:

~~~text
idkmesh init
  -> create .idkmesh/
  -> select DomainPack
  -> generate ProjectManifest
  -> inspect repository language/test commands
  -> generate bounded default policies
  -> install GitHub workflow templates
  -> configure worker adapters
  -> validate branch-protection assumptions
  -> emit first Work Units
~~~

Then an operational loop can become:

~~~text
GitHub event
  -> classify/decompose
  -> Work Unit
  -> capability/risk routing
  -> worker adapter
  -> candidate + ResultManifest
  -> verifier adapter
  -> VerificationResult
  -> protected integration queue
  -> human/governance decision
~~~

This is the direction of the reference product. The current repository already has many underlying contracts and adapter concepts, but not yet this complete external-project bootstrap as one polished user flow.

## 20. The shortest adoption path

If you want to use IDKMesh ideas on a new application **today**, do this:

1. Create the application repository and baseline tests.
2. Protect the main branch.
3. Copy the software-engineering ProjectManifest/DomainPack patterns into your project documentation/configuration.
4. Define one small GitHub issue as a bounded Work Unit.
5. Give that Work Unit to one human or agent with limited permissions.
6. Require a candidate PR and exact test evidence.
7. Give the candidate to an independent verifier or independent verification stack.
8. Keep merge authority with the protected maintainer/governance path.
9. Record the outcome.
10. Repeat with slightly more automation only after the previous loop is stable.

That is the smallest useful “mesh.”

You do not need many agents to start. You need **clear boundaries, evidence, and a repeatable loop**.

## Related documents

- [Getting Started](GETTING_STARTED.md)
- [What Is IDKMesh?](WHAT_IS_IDKMESH.md)
- [Architecture](../ARCHITECTURE.md)
- [ProjectManifest and DomainPack interfaces](specifications/PROJECT_DOMAIN_INTERFACES.md)
- [Schema index](../schemas/README.md)
- [Interoperability](../interop/README.md)
- [Agent Network and Volunteer Nodes](architecture/AGENT_NETWORK_AND_VOLUNTEER_NODES.md)
- [Execution Substrate Abstraction](architecture/EXECUTION_SUBSTRATE_ABSTRACTION.md)
- [Testing and CI Practice](TESTING.md)
- [Project Rules](../PROJECT_RULES.md)
