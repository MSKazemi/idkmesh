# Freebuff operator evaluation for IDKMesh

**Status:** operator guidance; not a canonical provider calibration  
**Date:** 2026-10-03  
**Scope:** human-initiated use of Freebuff Cloud/CLI against `MSKazemi/idkmesh`

## Decision

Freebuff is useful **now** as a human-operated external coding worker for bounded IDKMesh issues.

It should **not** be wired into unattended GitHub CI/dispatch as if it were a provider API. Freebuff's current Terms of Service say a human must initiate each session and remain actively present, and prohibit bots/scripts/macros/headless automation from operating the product. If Freebuff later exposes an official automation API with compatible terms, evaluate it through the normal IDKMesh connector boundary instead of scripting the UI.

References:

- https://freebuff.com/
- https://freebuff.com/blog/free-cloud-coding-agent
- https://freebuff.com/terms-of-service
- `config/llm-routing-policy.json`
- `docs/planning/PRODUCT_GOALS_COMPONENT_SLICE_MAP_2026-09-22.md`

## Fit with the existing IDKMesh routing model

IDKMesh already chooses a **capability tier before a provider**:

- T0 deterministic
- T1 small
- T2 standard
- T3 strong
- T4 peak

Freebuff should therefore be treated as another candidate worker surface, not as "the model for IDKMesh".

The repository also keeps these concepts separate:

```text
model capability != coding agent
coding agent != execution backend
worker success != verification
verification != human decision
human decision != merge authority
```

That boundary remains unchanged when Freebuff is used.

## Current free model allowance (checked 2026-10-03)

Freebuff's public pricing page currently says every account receives 100 Freebucks per day and may spend that allowance on any mix of eligible models. The displayed "hours/day" values are **not additive**: each value is the approximate maximum if the entire daily allowance were spent on that model.

| Freebuff model | Public free allowance | IDKMesh use |
| --- | ---: | --- |
| Solar Mini 4 | unlimited | bulk mechanical edits, docs, repetitive low-risk work |
| Space Bunny Alpha | unlimited | secondary low-risk/bulk lane; calibrate before relying on it |
| MiMo 2.6 Flash | 10 h/day equivalent | default T1/T2 implementation lane |
| Solar Pro 4 | 10 h/day equivalent | alternate high-throughput T1/T2 lane |
| GLM 5.3 Flash | 6 h/day equivalent | alternate coding/review lane |
| DeepSeek V4.1 Flash | 10 h/day equivalent | default for harder T2/T3 coding/debugging (provisional) |
| GPT-6 Luna | 5 h/day equivalent | alternate reasoning/coding lane; calibrate on IDKMesh tasks |
| MiMo 2.6 Pro | 3 h/day equivalent | reserve for the hardest bounded coding/reasoning tasks |

The same public page currently says Gemini 3.8 Flash and Muse Spark require a paid plan. GPT-6.1 Sol is free only in the US and otherwise part of a paid plan, so it should not be treated as a generally free IDKMesh lane.

Reference: https://freebuff.com/

## Recommended free-model strategy

For IDKMesh, do **not** spend the whole daily budget on a single model by default. Use a capability ladder:

1. **MiMo 2.6 Pro** — hardest bounded implementation, architecture-aware debugging, difficult refactors.
2. **DeepSeek V4.1 Flash** — primary heavy-development model; much more daily capacity than MiMo Pro (10 versus 3 hours per day equivalent).
3. **MiMo 2.6 Flash / Solar Pro 4** — routine T1/T2 implementation, tests, docs, clear multi-file work.
4. **Unlimited Solar Mini 4 / Space Bunny Alpha** — repetitive cleanup, documentation, mechanical tests, and first-pass chores.
5. Use a different strong model for **advisory review** of important patches rather than spending the strongest model twice on generation.

This is a provisional operational strategy, not a benchmark claim. The Freebuff pages cited here do not rank these models for coding; using DeepSeek and MiMo Pro as first lanes is this document's provisional judgment, and IDKMesh should calibrate them on its own frozen issue cohort before making a canonical mapping.

## Provisional model-use guide

These Freebuff model names are **not yet calibrated IDKMesh tier declarations** and should not be added to `llm-routing-policy.json` as canonical mappings without measured evidence.

| Work class | Suggested first choice | Alternate | Notes |
| --- | --- | --- | --- |
| T1 mechanical/docs/tests | MiMo 2.6 Flash | Solar Mini 4 | Use unlimited/10h lanes for routine work; preserve scarce strong-model allowance. |
| T2 bounded multi-file coding | DeepSeek V4.1 Flash | MiMo 2.6 Flash | DeepSeek is the preferred quality/capacity balance; fall back to the 10h lane for routine slices. |
| T3 architecture-aware/debugging | MiMo 2.6 Pro | DeepSeek V4.1 Flash | Reserve MiMo Pro's smaller allowance for genuinely difficult work. |
| T4 control-plane/research/release/security | no single Freebuff model is pre-approved | strongest available + separate review/human gate | Do not infer T4 authority from model strength. Keep independent-review/human-gate rules. |

A second model can provide useful **advisory review**, but another owner-controlled Freebuff session does not satisfy an issue that explicitly requires independent human/external evidence.

## Recommended first pilot

*Historical:* this pilot was run on 2026-10-03/04 (see "Pilot checkpoint"). Issues #901 and #900 are closed; PRs #904 and #905 merged.

Use open issue **#901 — Usage examples in `--help` for `idkmesh run` and `idkmesh control-tower`**.

Why:

- currently routed as a T1/small agent-candidate task;
- bounded files and explicit acceptance criteria;
- no open PR was found for #901 at this checkpoint;
- the issue explicitly welcomes a contributor's own coding agent while carrying `do-not-automate` for the repository-owned Jules dispatcher.

Recommended first model: **MiMo 2.6 Flash**.

Paste-ready Freebuff prompt:

```text
Work on MSKazemi/idkmesh issue #901 only.

Before editing:
1. Read AGENTS.md completely.
2. Read CONTRIBUTING.md and the relevant CLI/tests/docs.
3. Refresh current main and record the exact base SHA.
4. Read issue #901 and check for open PRs/comments so you do not duplicate work.

Implementation boundary:
- Add argparse Examples blocks only for the commands named in #901.
- Add/adjust the narrow parser tests required by the issue.
- Update only documentation that actually quotes the affected help.
- Do not rename commands or flags.
- Do not broaden scope into unrelated CLI cleanup.
- Do not merge, approve, or push directly to main.

Verification:
- run the focused pytest command from #901;
- run make smoke;
- run make gate;
- report the exact commands and actual results.

Publication:
- one focused branch/PR;
- include AI/tool provenance: Freebuff + selected model;
- state remaining uncertainty explicitly.
```

## Repository access and data handling (checked 2026-10-04)

Connecting this repository to Freebuff Cloud uses the GitHub App `freebuff-web`, owned by the organization `CodebuffAI`. The
App's public listing (GitHub API) declares these permissions: `actions: read`, `administration: write`, `checks: write`,
`contents: write`, `deployments: write`, `issues: write`, `metadata: read`, `pull_requests: write`, `repository_hooks: write`,
`statuses: write`, `workflows: write`, and the event `push`. GitHub's permissions reference lists branch-protection and ruleset
management under Administration write and changes to `.github/workflows` under Workflows write.

On 2026-10-04 `main` requires the checks `gate (3.11)` and `gate (3.13)`, requires no approving reviews, has
`enforce_admins=false`, restricts no pushers and has no rulesets. The rules in this document and in the prompts ("never push
directly to main", "never merge or approve") are instructions to the tool; they are **not** limits enforced by the App's
permissions. Which repositories the App is installed on is visible only in the repository owner's GitHub settings and is not
recorded here.

Freebuff's Terms (last updated 10/01/2026) say: "Connecting a GitHub repository to Freebuff Cloud authorizes Codebase Evaluation
only of code, files, and other content in that connected repository." and grant the company a license to "host, reproduce,
transmit, modify, and otherwise process your Content only as reasonably necessary to provide, maintain, develop, evaluate,
improve, secure, and support Service." The pricing page has no data-handling statement. This repository is public; do not
connect a repository, branch or fork that contains non-public material.

## Human-operated workflow

1. Connect `MSKazemi/idkmesh` in Freebuff Cloud (or clone locally and run the Freebuff CLI).
2. Pick one bounded issue that is not already implemented and has no active PR.
3. Select a model appropriate to the task tier.
4. Give Freebuff the issue-specific prompt and repository safety instructions.
5. Inspect the plan before broad edits.
6. Review the Changes pane and terminal output.
7. Require focused tests plus the repository gate appropriate to the diff.
8. Publish one focused PR, not a stream of incremental branch-head updates.
9. Treat the result as an untrusted candidate until normal CI/review completes.
10. Use a different model only as advisory review unless the issue's evidence contract explicitly allows model-based verification.

## Long-running human-present Freebuff session

Freebuff's current Terms allow automation performed by Freebuff **after a human starts a session**, but require a human to initiate each session and remain actively present. State a maximum number of slices for the session before starting it, and repeat that cap in the controller prompt, so that the human-present requirement stays checkable. The daily allowance is not a reason to continue unattended. Do not use an external bot, macro, script, headless browser, or GitHub Action to keep submitting Freebuff requests.

For a long development session, keep **Build** mode and run a single human-started "session controller" prompt. The controller may process several independent micro-slices sequentially, but every slice remains one bounded issue/PR and normal repository authority rules still apply.

### Stop conditions

The session must stop immediately when any of these is true:

- Freebuff reports the daily allowance is exhausted;
- the next issue needs human-only evidence, security/governance approval, secrets, or release authority;
- an active PR or implementation already covers the task;
- the issue is umbrella-sized or needs decomposition;
- tests cannot be made green without broadening scope;
- current `main` moved in a way that invalidates the candidate;
- creating the next candidate would exceed repository review/CI capacity;
- the agent is uncertain whether the next action is allowed.

### Paste-ready session-controller prompt

```text
You are an implementation worker for MSKazemi/idkmesh.

This is one human-initiated Freebuff session. Continue making safe, bounded,
reviewable progress while I remain actively present, until either the Freebuff
daily allowance is exhausted or one of the stop conditions below is reached.

AUTHORITY:
- Read AGENTS.md completely before any change and obey it exactly.
- Read CONTRIBUTING.md, PROJECT_RULES.md, ARCHITECTURE.md and relevant planning docs.
- Never push directly to main.
- Never merge or approve a PR.
- Never weaken tests, security, evidence, or human-review requirements.
- Never treat your own output or another owner-controlled model as independent human evidence.
- Never work around Freebuff limits or automate Freebuff from outside the product.

WORK LOOP:
For each iteration, choose exactly ONE bounded implementation-ready issue or
micro-slice.

Before choosing work:
1. Refresh current main and record the exact SHA.
2. Inspect open issues, open PRs, comments, recent merged PRs, and relevant code.
3. Do not assume an open issue is unimplemented.
4. Prefer current T1/T2/T3 agent-candidate tasks with explicit acceptance criteria.
5. Skip human-required/human-gated, security-sensitive, secret-bearing, release,
   governance, research-evidence, or umbrella issues.
6. Skip any issue already covered by an active PR or current main.

For the chosen issue:
1. State the issue number, base SHA, files likely to change, and a short plan.
2. Create one focused branch from current main.
3. Implement only that issue/micro-slice.
4. Run the smallest focused tests while editing.
5. Run the repository gate appropriate to the final diff.
6. Inspect git diff for unrelated changes.
7. Create one focused PR using the repository template.
8. In the PR record:
   - exact base SHA;
   - exact test commands and actual results;
   - remaining uncertainty;
   - AI/tool provenance: Freebuff Cloud + <the model actually used, read from the Freebuff UI>.
9. Do not merge the PR.
10. Return to current main, refresh repository/PR state, and select the next
    independent eligible issue.

FIRST PRIORITY:
- Finish issue #901 if it is still open, unimplemented, and has no active PR.
- After that, re-evaluate the live repository. Issue #900 is a reasonable next
  candidate only if it is still unimplemented, has no active PR, and current
  main still matches its acceptance criteria.
- Do not hard-code a longer issue list; live repository state is authoritative.

STOP CONDITIONS:
Stop and report instead of continuing if:
- Freebuff says the free allowance is exhausted;
- no safe bounded issue is available;
- the next task requires human/external evidence, secrets, security/governance,
  release authority, or architecture judgment outside a bounded issue;
- an active PR conflicts with the work;
- tests fail for reasons that require broad unrelated changes;
- you cannot verify that your next action is allowed.

At the end of the session, provide a compact ledger:
- issues attempted;
- PRs created;
- tests run and results;
- failures/blocks;
- approximate human interventions;
- remaining Freebuff quota if visible.
```

This loop is intentionally **sequential**, not a parallel PR generator. The objective is to use the available model budget efficiently without creating more candidate work than the repository can safely review.

## Future integration path

If an official Freebuff machine API becomes available and permits unattended automation:

```text
Freebuff provider/API
  -> provider-neutral connector
  -> explicit capability declaration
  -> WorkUnit admission
  -> candidate output
  -> ResultManifest
  -> independent VerificationResult
  -> human/integration authority
```

Do not add UI automation, browser scraping, or a provider-specific coordinator branch as a shortcut.

## Evaluation to run before canonical routing

Before Freebuff model names become formal tier mappings, run a small frozen cohort of representative T1/T2/T3 issues and record:

- success against acceptance tests;
- regression rate;
- wall time;
- model/session consumption;
- number of human interventions;
- scope violations;
- first-pass vs final-pass success;
- cross-model disagreement on review.

Use that evidence to update routing policy rather than choosing a permanent project-wide model.


## Pilot checkpoint — 2026-10-04

The first human-operated Freebuff session (model recorded in the PR bodies) produced two focused candidate PRs:

- PR #904 for issue #901: CLI help examples (2 files); merged as `e00a859`.
- PR #905 for issue #900: CI-validated API examples (8 files); merged as `abdf644`.

Both candidates first reported an unrelated repository-wide gate failure in
`tests/test_resource_compute_bindings_live.py::LiveFreshnessTests`: the GitHub Actions public-standard binding and its source
evidence were last reviewed on 2026-08-28 with a 30-day freshness window. The gate is fail-closed and says to re-read the upstream
source and move `reviewed_at` / `checked_at` only after a real re-review; widening `max_age_days` is not an acceptable repair.
That was resolved by PR #906 (`52fe9dc`) after a re-read on 2026-10-03 of
https://docs.github.com/en/actions/reference/runners/github-hosted-runners ("Use of the standard GitHub-hosted runners is free
and unlimited on public repositories.").

Observations to carry into any further pilot: the work was committed as the repository owner's identity, so it is
owner-controlled automation and counts as no independent review; and the candidates took two issues that had been filed for
outside contributors.
