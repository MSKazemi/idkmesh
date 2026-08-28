# ACE GitHub Workflow Threat Model

**Status:** Security review for ACE v0 metadata-only operation.  
**Scope:** `.github/workflows/ace-community-growth.yml`  
**Related:** #10, #23, #26, #35, `COMMUNITY_GROWTH_ENGINE.md`, `SECURITY.md`.

## Executive assessment

ACE v0 uses `pull_request_target` with `issues: write` so it can update a public growth ledger and, in one explicitly authorized case, create a bounded follow-up issue from a merged PR.

That event is security-sensitive because `pull_request_target` runs in the context of the base repository and can receive a write-capable token even when the PR came from a fork.

The most important current invariant is therefore:

> **The ACE privileged workflow must never check out, import, execute, evaluate, or `eval` contributor-controlled PR code or commands.**

The reviewed workflow satisfies that invariant. It consumes GitHub event metadata only.

This review also found several metadata-integrity and abuse risks. The accompanying hardening patch:

- pins `actions/github-script` to the current `v7` commit SHA (`f28e40c7f34bde8b3046d885e986cb6290c5673b` at review time);
- prevents arbitrary issue authors from self-applying `growth-seed` through an `ACE_SEED` body marker;
- identifies the growth ledger through a workflow-owned `ace:ledger` label rather than title alone;
- makes malformed/missing ledger state fail closed instead of silently resetting to zero;
- paginates issue scans instead of inspecting only the first 100 results;
- prevents an arbitrary unlabelled issue from poisoning the generated-seed deduplication marker;
- removes untrusted PR-title interpolation from automatically generated issue bodies;
- checks the actual GitHub protection state of `main` and disables reproductive actuation while that external integration boundary is absent.

**Verdict:** with these guards, ACE v0 is **safe enough for its current metadata-only experimental scope**, assuming repository token permissions remain bounded and the no-PR-code-execution invariant is preserved. It is **not** a sufficient security basis for autonomous merges, code execution, secrets access, governance changes, or higher-impact self-evolution.

---

## 1. Assets

ACE must protect more than source code.

### Repository authority

- `GITHUB_TOKEN` granted to the workflow;
- issue/label creation and modification authority;
- any future PR, branch, ruleset, or merge authority.

### Canonical state

- the ACE Community Growth Ledger;
- Growth Seed identity and lineage;
- review-load and reproductive-credit measurements;
- future policy weights and fitness evidence.

### Community integrity

- issue tracker signal quality;
- contributor attention and notification budget;
- newcomer trust in project-generated issues;
- reviewer/maintainer capacity.

### Operational capacity

- GitHub Actions minutes/quota;
- API rate limits;
- workflow queue capacity.

### Future high-value assets

- credentials/secrets if ever added;
- autonomous policy-selection authority;
- repository write/merge authority;
- volunteer compute or agent execution capabilities.

The current design should avoid introducing these future assets into ACE v0.

---

## 2. Trust boundaries

```text
external contributor / fork
        |
        | untrusted issue/PR title, body, labels visible in payload,
        | branch names, comments, metadata
        v
GitHub event payload
        |
        | pull_request_target enters privileged base-repo workflow context
        v
ACE workflow code from canonical/default branch
        |
        | bounded GitHub token
        v
GitHub Issues API
        |
        +--> ACE ledger
        +--> ACE-owned labels
        +--> at most one authorized follow-up Growth Seed
```

### Boundary A — untrusted text to privileged workflow

Issue bodies, PR titles, branch names, comments, and other contributor-controlled strings are **data**. They must never become shell commands, JavaScript source, workflow expressions that alter control flow unsafely, prompts with privileged tool authority, or trusted authorization claims.

### Boundary B — PR head to base-repository token

`pull_request_target` must not check out PR-head code. A checkout, import, package install, build, test, or script execution from the PR branch would cross a critical boundary.

### Boundary C — labels to authorization

Labels such as `growth:spawn`, `growth-seed`, and `ace:ledger` are capabilities/signals. Untrusted text that merely *names* or imitates a label must not gain equivalent authority.

### Boundary D — public state to controller input

The ledger is controller state. Malformed state must not be silently repaired to a favorable/default value because that would allow state loss to masquerade as a valid observation.

### Boundary E — repository files to protected integration

Repository instructions, docs, labels, and workflow comments are not an enforcement boundary. Stronger ACE actuation must fail closed while GitHub reports `main` as unprotected. Branch protection/rulesets are external state and must be checked as such.

---

## 3. Attack surfaces

1. `pull_request_target` event payloads from fork-originated PRs.
2. Issue-open events and issue body markers.
3. PR labels present when a PR is merged.
4. PR titles or other strings copied into generated Markdown.
5. Growth Ledger discovery and JSON state parsing.
6. Issue-list scans used for deduplication.
7. GitHub Actions third-party dependencies.
8. Workflow/API event storms.
9. Future AI processing of issue/PR text.
10. Future expansion of token permissions or autonomous actuators.
11. Missing or weakened GitHub branch protection/rulesets.

---

## 4. Threats and mitigations

| ID | Threat | Severity | Likelihood in v0 | Current / patched mitigation |
| --- | --- | --- | --- | --- |
| T1 | Execute malicious fork/PR code under `pull_request_target` | Critical | Low while invariant holds | No checkout, import, build, tests, shell execution, or evaluation of PR code. Preserve as a hard invariant. |
| T2 | Untrusted issue author inserts `<!-- ACE_SEED` and gains `growth-seed` label | Medium | High before patch | Marker-driven labeling requires trusted `author_association` (`OWNER`, `MEMBER`, or `COLLABORATOR`). |
| T3 | Fake issue with ledger title is selected as canonical state | Medium | Medium | Workflow-owned `ace:ledger` label becomes canonical identity. Legacy migration selects the oldest title + state-marker match and labels it. |
| T4 | Malformed ledger JSON silently resets credit/load/counts | Medium | Low/Medium | Parse/missing-state failures throw and stop the run; state is not overwritten. |
| T5 | Attacker plants `spawned-from:pr-N` text to block a legitimate seed | Medium | Medium before patch | Deduplication counts the marker only on issues already carrying `growth-seed`; scans are fully paginated. |
| T6 | PR title injects mentions/Markdown into generated Growth Seed | Low/Medium | Medium | Generated seed no longer copies the PR title; only numeric PR reference is emitted. |
| T7 | More than 100 issues causes duplicate ledger/seed because scans stop at first page | Medium | Increases with growth | Use `github.paginate` for open/all issue scans. |
| T8 | Dependency/supply-chain compromise of moving `actions/github-script@v7` tag | High | Low | Pin to observed full commit SHA. Review/update deliberately when upgrading. |
| T9 | Event storms consume workflow/API quota or create state churn | Medium | Medium | Concurrency serializes state writes; future ACE should batch/generate by epochs rather than react publicly to every event. |
| T10 | Misapplied `growth:spawn` label authorizes unwanted issue creation | Medium/High | Low for external users | Only a merged PR with the label can actuate; future stronger actuation should record label/approval provenance explicitly. |
| T11 | Recursive issue creation creates uncontrolled workflow cascades | Medium | Low | Dedupe marker and one-seed-per-parent logic; do not rely on token recursion behavior alone. |
| T12 | Prompt/content injection when AI is later added | High | Not present in v0 | Treat all natural-language GitHub content as untrusted. AI output remains proposal/evidence until separately authorized and verified. |
| T13 | Token permission expansion creates accidental repository authority | Critical | Future risk | Keep explicit least privilege. No `contents: write` or merge authority in v0. |
| T14 | Popularity/activity signals are gamed into correctness or governance authority | High epistemic risk | Medium | Stars/forks/comments/PR volume are signals only; verified evidence and capacity gates stay separate. |
| T15 | ACE reproductive actuator runs while `main` lacks external protection | High governance/integration risk | Current until admin config changes | Read actual branch metadata; force `CONSOLIDATE` and disable the actuator while `mainProtected == false`. |

---

## 5. Fork-originated PR analysis

`pull_request_target` is intentionally used because the workflow needs a base-repository context and issue-write capability while observing PR lifecycle events.

A malicious fork can control or influence metadata such as PR title/body, source branch name, commit contents, and linked text. It cannot safely be allowed to control executable input inside this workflow.

### Required invariant

Under `pull_request_target`, never add any of the following without a separate security redesign:

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

If ACE ever needs to test PR code, use an unprivileged `pull_request` workflow with read-only/no-secret context and pass only verified artifacts across an explicit trust boundary.

---

## 6. Workflow permissions

Current explicit permissions are:

```yaml
contents: read
issues: write
pull-requests: read
```

For current behavior, `issues: write` is required to manage the ledger, labels, and bounded seed issue; `pull-requests: read` is sufficient for PR metadata; `contents: read` does not grant source writes.

No `contents: write`, actions administration, deployments, packages, secrets, or merge permission is granted.

Future design should separate a read-only observer, a policy evaluator, and a narrowly scoped actuator. The actuator should receive typed verified decisions—not arbitrary event text.

---

## 7. Ledger integrity

The ledger is not just documentation; it is controller memory.

### Identity

A title alone is not a secure identity because any issue author can choose the same title. v0 therefore uses a workflow-owned `ace:ledger` label as the canonical locator.

### Parsing

Malformed state fails closed. The workflow must not silently replace malformed state with defaults because state loss would become a new policy input without review.

### Future validation

Before ACE policy weights become consequential, validate state version, finite/ranged numerics, non-negative counts, plausible timestamps, explicit policy provenance, and replayable transitions where practical.

---

## 8. Denial-of-service and spam

The current workflow edits one ledger rather than commenting on every event. Remaining risks include queued Actions runs, API limits, permissive future Growth Seed generation, and Sybil distortion of low-trust activity proxies.

The recommended next-generation architecture remains:

```text
many events
 -> append/collect quiet evidence
 -> scheduled/generational evaluation
 -> capacity gate
 -> deduplicate
 -> strict public-action budget
```

Recommended actuator ceiling before real community evidence exists: **at most one deduplicated low-risk Growth Seed per eligible verified parent**, and no automatic cohort expansion while review capacity is constrained.

---

## 9. Recursive-trigger analysis

GitHub generally prevents repository-token-created events from recursively starting new workflow runs in many cases, but recursion safety must not depend on that behavior alone.

ACE uses a global concurrency group, deterministic `spawned-from:pr-N` marker, full-history deduplication on labeled Growth Seeds, an explicit `growth:spawn` gate, and—after this convergence patch—an external branch-protection gate.

Future actuators must remain idempotent even if platform event-delivery behavior changes or an event is retried.

---

## 10. Prompt/content injection boundary

ACE v0 does not call a language model. If AI is introduced later, issue/PR/comment text must be marked untrusted; model output must not directly select privileged APIs from arbitrary text; tool calls need typed allowlists and policy checks; generation and authorization remain separate; high-impact actions require deterministic guards and independent review.

A useful rule is:

> **Text may propose; typed policy and verified evidence authorize.**

---

## 11. Guards required before stronger autonomous actuation

Before ACE can do more than maintain metadata and create one explicitly authorized low-risk seed issue, require at least:

1. `main` protected according to #35;
2. verified parent -> seed -> descendant lineage (#25);
3. independent verification evidence separated from activity;
4. explicit risk classification for each actuator;
5. typed allowlist of writable fields/actions;
6. deterministic idempotency key;
7. capacity/review-load gate;
8. provenance for authorization;
9. no self-approval or self-merge;
10. rollback/recovery path;
11. audit log;
12. prompt-injection boundary if models consume GitHub text;
13. immutable action dependencies;
14. negative/adversarial tests;
15. external Phase-B activation gate such as PR #89 or its accepted successor.

Autonomous merge is explicitly outside the current safe envelope.

---

## 12. Current v0 verdict

### Safe enough for

- counting low-trust activity signals;
- updating one public experimental ledger;
- maintaining ACE-owned labels;
- applying `growth-seed` only from trusted issue authors;
- creating one bounded follow-up issue from an explicitly labelled merged PR **only when `main` is protected**;
- public simulation/measurement experiments.

### Not safe enough for

- checking out or running fork/PR code under a write token;
- secrets access;
- executing AI-generated commands;
- automatically accepting verification claims from GitHub text;
- changing governance/security policy;
- pushing to protected code branches;
- autonomous merge/deploy;
- broad recursive issue/PR generation;
- assigning financial or volunteer-compute authority.

The current recommendation is:

> **Keep ACE at metadata-only / bounded low-risk actuation, merge hardening only after review, and require external repository protections plus evidence-linked verification before increasing autonomy.**
