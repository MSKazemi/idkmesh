# ACE GitHub Workflow Threat Model

**Status:** Security review for ACE v0 metadata-only / bounded-actuation operation  
**Scope:** `.github/workflows/ace-community-growth.yml`  
**Related:** #10, #23, #26, #35, #51, `COMMUNITY_GROWTH_ENGINE.md`, `SECURITY.md`.

## Executive assessment

ACE uses `pull_request_target` with `issues: write` so it can maintain a public growth ledger and, in one explicitly authorized case, create a bounded follow-up Growth Seed from a merged PR.

That event is security-sensitive because `pull_request_target` executes base-repository workflow code with a base-repository token even for a fork-originated pull request.

The primary invariant remains:

> **The privileged ACE workflow must never check out, import, execute, evaluate, build, install, or otherwise run contributor-controlled PR code.**

A second independent review identified that code-execution safety is not enough. ACE also needs fail-closed **authorization** and **controller-memory** boundaries:

> **A generic `main.protected = true` bit is not proof that the intended integration policy is configured.**

> **A ledger-shaped issue or syntactically valid JSON is not automatically trustworthy controller state.**

The hardened v0 therefore requires:

- no PR-head execution under `pull_request_target`;
- least-privilege token permissions;
- immutable pin for the privileged third-party action;
- trusted-author gating for marker-driven metadata changes;
- unique workflow-labelled ledger identity;
- trusted/unambiguous legacy-ledger migration;
- semantic validation of ledger state, not JSON parsing alone;
- fully paginated issue scans;
- labelled provenance for generated-seed dedupe markers;
- no untrusted PR-title interpolation into generated issues;
- `main` reported protected **and** a separate explicit repository variable `ACE_AUTONOMOUS_ACTUATION_ENABLED=true` before reproductive actuation is eligible.

**Verdict:** with these guards, ACE v0 is suitable for its current public metadata ledger and explicitly opt-in bounded issue-generation experiment. It is not a sufficient security basis for autonomous merge, code execution, secrets access, governance mutation, financial authority, or high-impact self-evolution.

---

## 1. Assets

ACE must protect more than source code.

### Repository authority

- write-capable `GITHUB_TOKEN` scope;
- issue/label creation and modification authority;
- any future PR, branch, ruleset, deployment, or merge authority.

### Canonical controller state

- ACE Community Growth Ledger identity;
- `ACE_STATE` credit/review-load/count memory;
- Growth Seed identity and lineage;
- future policy weights/versions.

### Community integrity

- issue tracker signal quality;
- contributor/reviewer attention;
- newcomer trust in project-generated work;
- notification and moderation burden.

### Operational capacity

- Actions minutes/queue capacity;
- GitHub API limits;
- maintainer recovery capacity.

### Future high-value assets kept outside v0

- credentials/secrets;
- code/branch write authority;
- autonomous merge/deploy;
- volunteer-compute authority;
- financial/reward allocation;
- AI tool execution with privileged APIs.

---

## 2. Trust boundaries

```text
external contributor / fork
        |
        | untrusted title/body/branch/code/metadata
        v
GitHub event payload
        |
        | pull_request_target enters base-repo workflow context
        v
canonical ACE workflow code
        |
        | typed checks + bounded token
        v
GitHub Issues API
        |
        +--> labelled ACE ledger
        +--> ACE-owned labels
        +--> at most one explicitly authorized follow-up seed
```

### Boundary A — untrusted text to privileged workflow

Issue/PR titles, bodies, comments, branch names, and marker strings are data. They must never become executable source, shell commands, privileged workflow expressions, or authorization merely because they contain an expected phrase.

### Boundary B — PR head to base-repository token

Fork/PR code must never be executed by this privileged workflow. If PR code needs testing, use a separate unprivileged `pull_request` path and an explicit verified-artifact boundary.

### Boundary C — metadata to authorization

Labels/markers are capability-like signals. A text string that resembles `ACE_SEED`, `growth:spawn`, `ace:ledger`, or verification language is not equivalent to repository-controlled authorization.

### Boundary D — public issue state to controller memory

The ledger is controller memory. Identity must be unique and state must be semantically valid. Ambiguity/corruption requires human repair; it must not silently become a new default policy state.

### Boundary E — repository protection signal to autonomous actuation

`branch.protected` is a coarse platform signal. It does not prove that PR requirements, stable checks, review requirements, deletion/force-push restrictions, and bypass policy match IDKMesh's intended safety contract.

ACE therefore requires a second explicit post-verification repository opt-in before reproductive actuation.

---

## 3. Current explicit permissions

```yaml
contents: read
issues: write
pull-requests: read
```

Current behavior needs `issues: write` for the ledger, ACE-owned labels, and the bounded follow-up issue. It does not need source writes, merge permission, secrets, package writes, deployment authority, or Actions administration.

Future design should split stronger autonomy into:

```text
read-only observer
 -> policy evaluator
 -> narrowly scoped typed actuator
```

The actuator should receive verified typed decisions rather than arbitrary event text.

---

## 4. Threat register

| ID | Threat | Severity | Hardened mitigation |
| --- | --- | --- | --- |
| T1 | Execute malicious fork/PR code under `pull_request_target` | Critical | No checkout/import/build/test/install/shell/eval of PR code; regression contract asserts no checkout and no workflow `run:` step. |
| T2 | Untrusted issue author inserts `ACE_SEED` marker and self-enters cohort | Medium | Marker-driven labelling requires trusted `author_association` (`OWNER`, `MEMBER`, `COLLABORATOR`). |
| T3 | Fake issue becomes canonical ledger by matching title/body | Medium/High | Canonical identity is `ace:ledger`; legacy adoption requires trusted author association. |
| T4 | Multiple ledger-like records make controller state ambiguous | High | More than one labelled ledger or more than one trusted legacy candidate fails closed for human repair. |
| T5 | Malformed JSON silently resets controller memory | High | Missing/parse-invalid state throws; no fallback overwrite. |
| T6 | Syntactically valid but semantically poisoned `ACE_STATE` | High | Require supported version, canonical timestamp, non-future timestamp, finite non-negative numeric state, safe non-negative integer counters, valid count keys/object shape. |
| T7 | Attacker plants `spawned-from:pr-N` to suppress legitimate descendant | Medium | Marker only dedupes when carried by a `growth-seed`-labelled issue; scans are paginated. |
| T8 | PR title injects mentions/Markdown into generated issue | Low/Medium | Generated seed uses numeric PR reference, not PR title. |
| T9 | First-100 scan misses ledger/dedupe record | Medium | `github.paginate` for relevant scans. |
| T10 | Moving third-party action tag changes privileged code | High | `actions/github-script` pinned to reviewed full SHA. |
| T11 | Event storm consumes Actions/API/reviewer capacity | Medium | Serialized state writes; public-action budget remains bounded; future design should batch/generate by epochs. |
| T12 | Misapplied `growth:spawn` label authorizes unwanted follow-up issue | Medium/High | Requires merged PR + repository label + both global actuation gates; stronger future actuator should record approval provenance explicitly. |
| T13 | Recursive token-created events create unbounded issue cascade | Medium | Idempotent per-parent marker + labelled dedupe + bounded actuator; do not rely solely on platform recursion suppression. |
| T14 | Prompt/content injection if AI is later added | High | Natural language remains `untrusted_text`; typed policy/evidence must authorize privileged actions. |
| T15 | Token permission expansion accidentally grants canonical mutation | Critical | Explicit least privilege; no `contents: write` or merge authority; regression contract. |
| T16 | Popularity/activity signals become correctness/governance authority | High epistemic | Activity is signal only; verified descendants, security and capacity remain separate. |
| T17 | Any weak/partial branch rule flips `protected=true` and silently enables autonomy | High | `actuationAllowed = mainProtected && explicitActuationOptIn`; opt-in is set only after concrete admin verification. |
| T18 | Protection is weakened later while opt-in remains configured | High | Either gate failing disables actuation; ledger reports gate status. Admin runbook requires opt-in removal during repair/incident response. |

---

## 5. Fork-originated PR analysis

A malicious fork may control:

- PR title/body;
- source branch name;
- commits and files;
- linked Markdown/text;
- any semantic meaning it tries to attach to those strings.

It must not control executable input in the privileged workflow.

### Required invariant

Under `pull_request_target`, do not add any of the following without a separate security redesign:

```text
actions/checkout of PR head
npm/pip/cargo/etc install from PR contents
source/import/require from PR contents
shell commands derived from PR fields
runpy/eval/exec of PR content
Docker/build execution of PR content
AI tool execution where PR text can choose privileged tools
secret exposure to PR-controlled execution
```

If PR code must be evaluated, do it in an unprivileged workflow and promote only independently verified artifacts across an explicit trust boundary.

---

## 6. Ledger identity and migration

### Canonical identity

A title is not identity. Any issue author can choose a title.

The canonical open ledger is the unique open issue carrying `ace:ledger`.

If multiple open issues carry that label, the workflow stops rather than selecting whichever appears first.

### Legacy migration

During migration, when no labelled ledger exists, the workflow may adopt exactly one issue that:

- has the canonical legacy title;
- has an `ACE_STATE` marker;
- was created by a trusted repository-associated author.

Zero candidates creates a fresh workflow-labelled ledger. Multiple trusted candidates fail closed for human reconciliation.

This prevents an external user from pre-creating a convincing ledger-shaped issue and having it promoted to controller memory.

---

## 7. Ledger semantic validation

JSON syntax is only the first check.

A retained `ACE_STATE` must satisfy:

- `version == 1`;
- `updated_at` is the canonical ISO representation produced by the workflow;
- timestamp is not implausibly in the future;
- `credit` is finite and non-negative;
- `review_load` is finite and non-negative;
- `total_events` is a non-negative safe integer;
- `counts` is a plain object;
- count keys match the bounded event-key character/length rule;
- count values are non-negative safe integers.

Missing/invalid state stops the workflow and preserves the public evidence for repair. The workflow does not merge malformed state into defaults.

### Why this matters

Values such as a stringified infinity, negative counters, arrays where maps are expected, unsupported versions, or future timestamps can corrupt controller dynamics without being invalid JSON.

Controller memory deserves the same fail-closed discipline as executable configuration.

---

## 8. Two-gate actuation authorization

ACE reproductive actuation is eligible only when:

```text
mainProtected == true
AND
ACE_AUTONOMOUS_ACTUATION_ENABLED == "true"
```

### Why `protected=true` is not enough

GitHub may report a branch protected when **some** protection/ruleset applies. The boolean alone does not prove that the IDKMesh-required combination is present:

- PR-based integration;
- stable required checks;
- blocked force-push/deletion;
- appropriate independent review;
- narrow/auditable bypass policy.

The repository variable is therefore a deliberate second administrative decision after those behaviors are tested.

### Fail-closed states

ACE enters `CONSOLIDATE` and cannot spawn a Growth Seed if either gate is disabled.

The ledger continues for observability but reports that autonomous actuation is disabled.

The opt-in must be removed/set non-`true` during protection repair or incident response. Protection failure independently disables the actuator even if the variable was accidentally left present.

---

## 9. Bounded seed actuator

Even with both global gates enabled, reproduction still requires:

```text
pull_request_target closed event
AND PR actually merged
AND growth:spawn label present
AND no labelled Growth Seed already carries spawned-from:pr-N
```

The generated issue:

- contains only trusted numeric PR identity, not the PR title;
- offers bounded reproduce/challenge/extend/explain paths;
- requires evidence rather than opinion;
- receives `growth-seed` and `help wanted` labels;
- does not merge code, execute code, alter governance, or grant compute/financial authority.

Before any higher-impact actuator is added, label/approval provenance should itself become typed evidence rather than inferred from current metadata.

---

## 10. Denial-of-service / Goodhart risks

ACE deliberately updates one ledger rather than publicly replying to every event, but event storms can still consume:

- workflow queue capacity;
- Actions minutes;
- API budget;
- controller churn;
- reviewer attention.

Raw stars, forks, comments, issues and PRs are not success objectives. They are low-trust activity signals.

Recommended future shape:

```text
many events
 -> quiet evidence collection
 -> scheduled/generational evaluation
 -> verification/capacity gate
 -> dedupe
 -> strict public-action budget
```

Before real community evidence exists, the actuator ceiling remains at most one deduplicated low-risk Growth Seed per explicitly eligible verified parent.

---

## 11. Prompt/content injection boundary

ACE v0 does not call a language model, so prompt injection is not currently an execution path.

If AI is introduced later:

- issue/PR/comment text is `untrusted_text`;
- model output cannot directly select arbitrary privileged APIs;
- privileged tool calls use typed allowlists and policy checks;
- generation and authorization remain separate;
- high-impact actions require deterministic guards and independent evidence/review;
- strings such as `ignore previous instructions`, `ACE_SEED`, or fake verification prose grant no authority.

Useful rule:

> **Text may propose; typed policy and verified evidence authorize.**

---

## 12. Guards required before stronger autonomy

Before ACE can do more than maintain metadata and create one explicitly authorized low-risk seed issue, require at least:

1. #35 GitHub protection configured and behaviorally verified;
2. explicit actuation opt-in enabled only after that verification;
3. verified parent -> seed -> descendant lineage;
4. independent verification evidence separated from activity;
5. explicit risk class per actuator;
6. typed writable-field/action allowlist;
7. deterministic idempotency key;
8. capacity/review-load gate;
9. provenance for the authorizing actor/policy;
10. no self-approval/self-merge;
11. rollback/recovery path;
12. audit log of proposed/rejected/executed/reverted actions;
13. prompt-injection boundary if a model consumes GitHub text;
14. immutable action dependencies;
15. adversarial/negative tests;
16. controller-state schema/version migration discipline.

Autonomous merge remains explicitly outside the current safe envelope.

---

## 13. Verification checklist for future edits

A reviewer changing the privileged workflow should confirm:

- no PR-head checkout or executable PR-controlled input;
- no new shell `run:` in the privileged job;
- third-party privileged action remains pinned;
- token permissions do not expand accidentally;
- marker text is not authorization;
- canonical ledger identity is unique;
- legacy migration cannot adopt untrusted/ambiguous state;
- semantic state validation remains fail closed;
- relevant scans stay paginated;
- untrusted titles/text are not copied into privileged generated control data;
- dedupe requires labelled provenance;
- both protection and explicit opt-in are required for actuation;
- the regression safety contract is updated to encode any new invariant.

---

## 14. Current v0 verdict

### Safe enough for

- counting low-trust activity signals;
- updating one public, semantically validated experimental ledger;
- maintaining ACE-owned labels;
- trusted-author marker labelling;
- one deduplicated follow-up Growth Seed from an explicitly labelled merged PR **only after both global actuation gates are enabled**;
- public simulation/measurement experiments.

### Not safe enough for

- executing fork/PR code under a write token;
- secrets access;
- executing AI-generated commands;
- treating GitHub text as verification/authorization;
- changing governance/security policy autonomously;
- pushing protected code branches;
- autonomous merge/deploy;
- broad recursive issue/PR generation;
- financial or volunteer-compute authority.

Current recommendation:

> **Keep ACE metadata-first and fail-closed, independently review PR #51, configure/test real GitHub protection, and enable the separate actuation opt-in only after those controls are demonstrated.**
