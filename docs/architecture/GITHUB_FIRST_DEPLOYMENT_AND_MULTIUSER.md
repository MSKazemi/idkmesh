# GitHub-First Deployment and Multi-User Operation

**Status:** recommended default deployment architecture  
**Date:** 2026-09-22  
**Scope:** where IDKMesh runs, how a team shares it, and when a separate server becomes necessary.

## Decision

The default deployment for a normal software project should be:

> **GitHub-first, server-optional.**

A small team should be able to install IDKMesh into a GitHub repository and run the normal development loop without operating a permanent IDKMesh server.

GitHub provides the first control plane:

- repository = canonical project state;
- Issues/Projects = work queue and human coordination;
- labels = routing/risk/readiness metadata;
- branches/PRs = candidate code;
- GitHub Actions = event-driven coordinator and deterministic execution;
- Checks/reviews = verification surfaces;
- GitHub identities/teams = initial human identity/roles;
- protected branch/rulesets = integration authority;
- repository/environment secrets = bootstrap secret storage;
- a Git-native IDKMesh ledger = durable compact run/evidence state.

External agents and model providers can remain hosted by their own providers. Optional local or donated machines run `idkmesh-node` only when a task requires local models, special hardware, stronger isolation, or additional compute.

A permanent IDKMesh service should be introduced only when measured requirements exceed the GitHub-first profile.

## 1. Where each component runs

~~~text
                     HUMAN USERS
                 GitHub accounts/teams
                          |
                          v
+--------------------------------------------------------------+
|                     TARGET GITHUB REPOSITORY                 |
|                                                              |
|  code + docs + .idkmesh/ policy                              |
|  issues / labels / projects                                  |
|  PRs / branches                                              |
|  Actions workflows                                           |
|  checks / reviews                                            |
|  protected main                                              |
|  compact durable IDKMesh run/evidence ledger                 |
+----------------------+-------------------+-------------------+
                       |                   |
           dispatch / API calls            | optional pull/claim
                       |                   |
        +--------------+------+     +------+------------------+
        | hosted agent/model  |     | local / volunteer node |
        | provider            |     | laptop/server/workstation|
        | Jules, APIs, etc.   |     | disposable sandbox      |
        +----------+----------+     +-----------+-------------+
                   |                            |
                   +-------------+--------------+
                                 |
                                 v
                       candidate/evidence
                                 |
                                 v
                       GitHub PR + checks
                                 |
                                 v
                       human integration
~~~

### What must be always on?

For the default profile: **nothing owned by the project has to be always on.**

GitHub receives the event and starts a workflow when needed. Hosted providers run their own infrastructure. A local node may be online only when its owner chooses to contribute resources.

This is different from a traditional application server architecture. IDKMesh is primarily a coordination/control workflow, so event-driven execution is preferable until a persistent service is justified.

## 2. Default deployment profile: Repository-Only

Call this **Profile G0 — GitHub Repository Control Plane**.

Required project-owned infrastructure:

- one GitHub repository;
- GitHub Actions;
- branch/ruleset configuration;
- optional repository/environment secrets.

No VPS, Kubernetes cluster, Postgres database, Redis queue, or always-on web service is required.

### Event flow

~~~text
human creates/edits issue
  -> issue-model-router classifies capability/authority
  -> human applies explicit dispatch approval when required
  -> Actions creates/adopts WorkUnit
  -> deterministic route selects eligible connector
  -> external provider or Actions/local node executes
  -> provider returns PR/artifact/result
  -> Actions normalizes candidate
  -> independent checks/verifier run
  -> evidence/status published to GitHub
  -> human reviews
  -> protected merge
~~~

GitHub Actions jobs are ephemeral. Therefore no important state may exist only on one runner.

## 3. State model without a server

A server is often introduced because an application needs a database and queue. IDKMesh can initially map those responsibilities onto GitHub-native surfaces.

| State class | GitHub-first home |
| --- | --- |
| project source/policy | default branch + `.idkmesh/` |
| human-readable work | Issues / Projects |
| routing/readiness | labels + issue metadata |
| candidate source | branch / PR |
| deterministic CI | Checks / workflow runs |
| human comments/decisions | PR/issue/review + structured decision record |
| compact canonical run state | dedicated Git-native IDKMesh ledger |
| ResultManifest / VerificationResult metadata | ledger or versioned evidence path |
| large temporary logs | Actions artifacts/provider logs |
| immutable artifact identity | hashes + provider/GitHub references |
| secrets | GitHub repository/environment secrets or external secret store |
| concurrency hint | Actions concurrency groups |
| idempotency | durable delivery/run identifiers in ledger |

### Why a separate ledger is still needed

Actions logs/artifacts are useful operational evidence but should not be the only durable interpretation record. Hosted runners disappear, provider sessions can expire, and artifact retention is finite.

The GitHub-only design therefore needs a small durable state layer, preferably an append-only or conflict-safe Git-native ledger, containing compact metadata and digests rather than huge raw logs.

Issue #597 tracks this work.

## 4. Multi-user model

A separate IDKMesh login/account system is not required for the first product.

GitHub identity is the bootstrap identity provider.

### Human roles

Minimum roles:

- **Owner/Admin** — repository settings, secrets, rulesets.
- **Maintainer/Integrator** — decides what reaches the protected branch.
- **Worker** — human contributor implementing a WorkUnit.
- **Verifier/Reviewer** — examines candidate evidence.
- **Dispatcher/Operator** — may approve eligible WorkUnits for agent execution.
- **Node Operator** — may donate local compute; receives no repository authority automatically.

A person can hold several roles, but each action is checked against its specific authority.

### Agent identities

Agents are not GitHub users merely because a human initiated them.

Provenance should distinguish:

~~~text
initiating human: @alice
dispatch workflow: github-actions/run-...
worker connector: jules-main
external session: sessions/...
candidate PR author: provider bot / GitHub app
verifier: deterministic-ci + verifier-B
integrator: @bob
~~~

This is important in a collaborative environment because the question is not only “who clicked the button?” but “which actor actually generated, verified, and authorized the result?”

Issue #598 tracks the concrete role/claim/authority implementation.

## 5. How simultaneous users avoid duplicate work

GitHub Actions concurrency alone is not enough.

The design needs a durable claim/run protocol:

~~~text
WorkUnit ready
 -> actor requests claim/dispatch
 -> calculate deterministic idempotency key
 -> atomically/optimistically record admitted run
 -> dispatch connector
 -> later duplicate event sees existing run
 -> duplicate becomes no-op/status lookup
~~~

The durable key should bind at least:

- repository/project identity;
- WorkUnit ID/version/digest;
- exact input/base SHA;
- attempt number or dispatch slot;
- connector where explicitly selected;
- triggering GitHub delivery/event identifier where relevant.

Human claims should have explicit release/expiry behavior so abandoned tasks do not remain locked forever.

## 6. Secrets in the GitHub-only profile

Do not put secret values in `.idkmesh/`, issues, WorkUnits, or result manifests.

Tracked configuration contains references such as:

~~~text
env:JULES_API_KEY
env:GEMINI_API_KEY
~~~

The workflow resolves the reference only after policy/authority checks.

Initial secret locations:

1. GitHub Environment secrets for sensitive dispatch lanes;
2. repository secrets for lower-complexity setup;
3. provider-managed credentials for GitHub Apps/hosted agents.

Later hosted deployments may integrate Vault/1Password/cloud secret managers without changing WorkUnit semantics.

For higher-risk connectors, GitHub Environments can provide an additional approval boundary before a job can access secrets.

## 7. What GitHub Actions is good for

Use GitHub Actions for:

- issue/event classification;
- WorkUnit validation;
- routing;
- explicit provider dispatch;
- status polling/recovery jobs;
- deterministic tests;
- schema checks;
- static/security analysis;
- result normalization;
- evidence generation;
- scheduled recovery sweeps;
- release/package verification.

Do **not** treat Actions as:

- a permanent in-memory scheduler;
- the only durable database;
- an unlimited compute cluster;
- a safe place to execute arbitrary untrusted code with repository secrets;
- proof that two verifiers are independent merely because they ran in two jobs.

## 8. External hosted agents do not require an IDKMesh server

For providers like Jules or GitHub-native coding agents:

~~~text
GitHub workflow
 -> provider API / issue label / GitHub App
 -> provider owns long-running execution
 -> provider creates branch/PR or exposes result
 -> later GitHub event / recovery sweep observes completion
~~~

The GitHub workflow does not need to stay running while the agent works.

This is a major reason the serverless profile is practical.

The coordinator records an external session/reference, exits, and a later event or scheduled recovery pass resumes observation.

## 9. Local models and special hardware

Some work cannot run “on GitHub” because it depends on:

- Ollama/local models;
- a developer's GPU;
- licensed/private local tooling;
- a large test environment;
- specialized hardware;
- strong sandbox runtimes;
- private-network resources.

For these tasks use `idkmesh-node`.

~~~text
GitHub approved WorkUnit
 -> node securely discovers/pulls eligible work
 -> node checks local policy
 -> disposable sandbox
 -> local model/tool execution
 -> candidate/evidence
 -> GitHub
~~~

The node is a **worker**, not the central server.

It can disappear at any time. The durable coordination state remains outside the node.

## 10. When do we actually need a server?

Do not build a server because “multi-user software normally has a server.” Add one when measured requirements require it.

### Trigger A — webhook latency / event volume

If GitHub Actions startup latency, workflow quotas, or event handling materially block useful work, a GitHub App webhook service can become the always-on ingress.

### Trigger B — high-frequency scheduling

If many workers need sub-minute leases, heartbeats, work stealing, and dynamic capacity matching, a persistent broker/queue becomes useful.

### Trigger C — long-lived bidirectional agent sessions

If providers need streaming interaction, real-time cancellation, or operator messaging that cannot be represented cleanly by short workflow jobs, use the optional control service.

### Trigger D — large multi-project tenancy

If one IDKMesh installation manages many organizations/repositories, per-repository Actions become inefficient. A shared control plane with a database becomes useful.

### Trigger E — private enterprise data

Organizations may require self-hosted APIs, private networking, SSO, audit systems, private registries, and dedicated secret stores.

### Trigger F — richer interactive GUI

GitHub Pages can display static/read-only views. A live Control Tower with secure mutations, streaming state, or cross-repository queries may justify an authenticated backend.

### Trigger G — state size / query complexity

If the Git-native ledger becomes too large, contended, or expensive to query, move operational state to SQLite/Postgres while retaining immutable Git/evidence references.

## 11. Evolution profiles

### G0 — GitHub-only

~~~text
GitHub repository + Actions + hosted connectors
~~~

Best for:

- one project;
- small/medium team;
- asynchronous agent work;
- normal GitHub PR development.

**This should be the default onboarding target.**

### G1 — GitHub + optional nodes

~~~text
GitHub control plane
 + contributor/project idkmesh-node workers
~~~

Adds local models, GPUs, special tools, donated compute.

Still no central server.

### G2 — GitHub + lightweight control service

~~~text
GitHub
   |
GitHub App / webhook
   |
IDKMesh API service
SQLite/Postgres
   |
connectors/nodes
~~~

Adds faster events, durable queryable operational state, live cancellation/status, and better GUI support.

GitHub remains the canonical code/integration authority.

### G3 — shared multi-project control plane

~~~text
organizations/repos
       |
GitHub App installations
       |
IDKMesh control plane
       |
queue/db/policy/audit
       |
distributed execution substrates
~~~

Use when there is real multi-organization or high-volume demand.

### G4 — federated mesh

Multiple independently operated control planes/nodes exchange bounded work/evidence.

This is long-term research. It should not complicate the first usable product.

## 12. What remains to build

The existing connector-control initiative (#570) already captures much of the product path.

### Existing active connector work

- #574 — connector kernel/profile/probes/routing;
- #575 — Jules REST connector;
- #576 — OpenAI-compatible model connector;
- #577 — bounded local agent;
- #578 — GitHub issue/webhook dispatch bridge;
- #579 — candidate/result normalization;
- #580 — CLI + optional HTTP API.

### Deployment/multi-user gaps added from this review

- #596 — `idkmesh init --github` + reusable no-server workflow pack;
- #597 — durable GitHub-native run ledger and restart-safe/idempotent state;
- #598 — GitHub multi-user identity, role, claim, and authority policy;
- #599 — real second-project no-server pilot.

### Existing runtime/scale work

- #11 — volunteer local-model/node lane;
- #16 — finish coherent local Verified Swarm Runner;
- #461 — always-on GitHub-native repository development loop;
- #572 — Human Control Tower GUI.

## 13. Implementation order

The practical critical path is:

~~~text
connector kernel (#574)
       |
       +--------------------+
       |                    |
       v                    v
hosted connector        model/local connector
#575                    #576 -> #577
       |                    |
       +----------+---------+
                  |
                  v
GitHub dispatch bridge (#578)
                  |
                  v
candidate normalization (#579)
                  |
        +---------+---------+
        |                   |
        v                   v
GitHub bootstrap        durable state
#596                    #597
        |                   |
        +---------+---------+
                  |
                  v
multi-user authority/claims (#598)
                  |
                  v
CLI / optional HTTP UX (#580)
                  |
                  v
no-server second-project pilot (#599)
                  |
          evidence-based decision
                  |
       +----------+----------+
       |                     |
 GitHub-only works      concrete limits found
       |                     |
 default profile      introduce G2 service
~~~

The exact parallelism can change, but the pilot should not be replaced by architectural speculation.

## 14. Definition of success

The GitHub-first deployment is successful when a new team can:

1. create a GitHub repository;
2. run `idkmesh init --github`;
3. configure branch protection and secret references;
4. invite multiple GitHub collaborators;
5. create/approve bounded WorkUnits;
6. route work to hosted and/or local agents;
7. survive duplicate/replayed events and workflow restarts;
8. inspect candidate/verification state entirely from GitHub;
9. merge only through normal protected human authority;
10. develop and release a small real application;
11. operate without a permanent IDKMesh server.

Only after this is demonstrated should the project make an always-on server part of the normal installation story.

## Bottom line

For the first serious IDKMesh product:

> **The application “sits” primarily in the target GitHub repository.**

The coordinator is a set of versioned, event-driven workflows and libraries. Hosted agents run elsewhere. Optional local nodes supply special compute. GitHub holds project truth and integration authority.

A central server is an optimization for scale, latency, richer state, and multi-project operations — not a prerequisite for collaboration.
