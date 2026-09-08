# Low-effort contributors and free agents

Date: 2026-09-09

Status: **Research-backed proposal and conversation record, not an activated service or a governance change.** No agent installation, account subscription, external recruitment, spending authorization, or merge-policy change is made by this record.

Related guidance: [Project rules](../../PROJECT_RULES.md), [Community growth strategy](../community/COMMUNITY_GROWTH_STRATEGY.md), [Contribution guide](../../CONTRIBUTING.md).

## Owner request

> How I can find some contribiutors? I mean some people or agents that contrinbute to the https://github.com/MSKazemi/idkmesh
> what is the best methods and simple method?
> I dont not want to write blog or in HN or something like that I need to make it smart and modern.
> Is there in github or some ai or robot or agent that can contrinbute freely?
> What are the best practical methods?
> I want to do not work on this repo? I want other works on this repo other people and or robots and I just lead the project.

## Assistant recommendation

Start with **one free coding agent, one advisory review tool, and one human co-maintainer**. Do not build another growth controller or launch a large agent swarm first.

Delegating implementation is different from delegating technical maintenance. An agent-generated PR still needs a decision about correctness, scope, and integration. To stop being the daily implementer and reviewer, the owner needs to share real, bounded technical responsibility with a trusted human maintainer. An owner-controlled bot is not another independent community member.

The proposed operating model is:

```text
Owner: priorities, product direction, boundaries, major decisions
Co-maintainer: task readiness, triage, technical review, releases
Agent and volunteer contributors: bounded changes and evidence
CI and advisory reviewer: automated checks and feedback
Authorized human: integration decision under existing policy
```

Until a co-maintainer joins, the owner still holds the human-review responsibility. Neither free quotas nor passive discovery guarantee a sustainable volunteer team.

## Repository observations

The inspected default-branch checkpoint was `c35b31e7d76073b8c0597ce56779927f1a5520d7`. Issue and PR state below was read on 2026-09-09 and must be refreshed before execution.

The repository already has `AGENTS.md`, contribution/community guidance, starter issues, dependency-bot configuration, CI, GitHub Discussions, topics, and ACE observation machinery. Recreating those is not the next useful intervention. [R1][R2]

The ACE bootstrap observer's 2026-09-08 snapshot reports zero distinct external participants and zero claimed seeds in its original five-seed cohort. This is **cohort-specific evidence**, not a census proving that no outsider has ever participated anywhere in the repository. It does show that creating and observing seeds is not itself evidence of successful recruitment. [R3]

Two immediate readiness findings:

- PR 404 proposes advisory CodeRabbit configuration; its description explicitly separates configuration from owner installation of the app. The PR was still open. Do not duplicate that work or describe the service as already activated. [R4]
- Several recent starter tasks refer to `make setup`, `make test`, or `make integration`, while PR 396's correction states that the Makefile and local testkit are not on `main`. The current contribution guide also lacks the promised setup commands. Reconcile the overlapping local-gate work in PRs 386/396, or correct starter instructions to current-main commands, before sending newcomers down that path. This session did not rerun those branches' claimed test results. [R5][R6]

## Practical agent options

| Option | Current access distinction | Proposed use |
| --- | --- | --- |
| Google Jules | Free tier: 15 tasks per rolling 24 hours, 3 concurrent; quotas can change. | First bounded implementation agent. |
| CodeRabbit | OSS access without a paid subscription; usage limits apply. Repositories below 10 stars require manual review triggering. | Advisory review using the existing PR 404 approach. |
| Existing Dependabot configuration | Dependency-maintenance automation, not general feature development. | Keep this existing lane rather than add a duplicate updater. |
| GitHub Copilot cloud agent | Requires a qualifying paid-plan entitlement; some popular OSS maintainers qualify for free Pro. | Optional when legitimately available, not assumed free for this repository. |
| Codex for Open Source | Selected maintainers can receive six months of ChatGPT Pro with Codex; admission is not guaranteed. | Apply for support, but do not make the pilot depend on approval. |

Sources: [S1][S2][S3][S4][S5][S6]. Public-repository status alone does not imply free access to every coding agent. Open-source agent software also does not supply inference, electricity, hardware, or operations for free; volunteer resources must follow the existing zero-project-spend policy. [R2]

### Jules: smallest useful execution pilot

Authorize the Jules GitHub app for the intended repository, then use a specific issue or scoped task. Jules supports starting issue work with the `jules` label once that authorization exists. A label alone is not an installation. [S2]

Start with one active implementation task, not the maximum quota. Issue 402, documenting interoperability conformance-test setup, is a candidate after checking its assumptions and any overlapping work. Its requested before/after test evidence makes the result reviewable. [R7]

Suggested task instruction:

```text
Work on issue 402 from current main.
Read AGENTS.md, PROJECT_RULES.md, and CONTRIBUTING.md.
Check recent issue comments and overlapping PRs before starting.
Verify current file paths and commands; do not assume unmerged tooling exists.
Document interoperability dependency installation and conformance-test execution.
Limit edits to CONTRIBUTING.md and interop/README.md.
Run the relevant checks and report actual before/after skip counts.
Open one focused PR with tool provenance and remaining uncertainties.
No unrelated refactors, dependency changes, workflow changes, or paid services.
Do not approve or merge your own work.
Stop and report when prerequisites or verification cannot be satisfied.
```

These instructions express task scope; they are **not a security sandbox**. Enforce authority through actual repository permissions and existing integration gates. No agent should gain administrator, spending, or self-approval privileges.

Jules also documents daily/weekly scheduled tasks. Consider one narrow weekly job only after the manual pilot reduces maintainer effort; do not schedule open-ended repository improvement. A real queue/controller would need explicit deduplication and review-capacity enforcement rather than trusting a prompt to enforce concurrency. [S7]

### CodeRabbit: assistance, not a substitute human

The repository had one star when inspected, so the documented below-ten-stars rule applies: after installation, request review using `@coderabbitai review` or the status-comment control. Keep it advisory. Do not enable paid overage, manipulate stars, or count its comments as the separate human witness required by an existing review gate. [R1][S3]

## Finding people without blogs or Hacker News

### Maintain a small, genuinely ready task queue

Curate three to five bounded tasks, each with a current command, allowed scope, expected result, and named review owner. Use the exact `good first issue` label for suitable newcomers and `help wanted` for broader work. GitHub documents that beginner labels can help its discovery systems surface tasks; this is an opportunity, not a recruitment guarantee. [S8]

Keep human-evidence tasks separate from agent tasks. Genuine first-run confusion reports, independent security judgments, and actual new-machine tests are valuable precisely because they bring a different person or environment. Do not fabricate them with an owner-controlled agent. The repository already has examples in issues 403, 401, 138, and 151; check readiness and exact evidence requirements before inviting work. [R8]

### Use a one-time contributor directory submission

Submit the project through Up For Grabs' contribution process after starter tasks work on the default branch. This is a task-discovery listing, not a blog campaign. Its guidance expects support/mentoring for newcomers, so assign that role instead of promising unattended volunteer onboarding. Listing acceptance and resulting contributions are not guaranteed, and no submission was made in this session. [S9]

### Invite contributors to bring their own agent

A proposed IDKMesh-specific experiment is a bounded 'bring your own agent' contribution lane:

```text
Choose one approved issue
 -> use your preferred authorized tool/account or local setup
 -> submit one small PR with tests and provenance
 -> receive review and credit
 -> optionally help review another contribution
```

Offer contributors a useful agent-evaluation task, visible attribution, learning, and a path to real responsibility. Do not promise payments, reputation scores based on PR volume, or scientific independence simply because two model names differ. Compute donation remains optional, resource-capped, and within provider terms; do not share credentials or evade quotas.

Suggested pinned GitHub invitation:

> IDKMesh is looking for a technical co-maintainer and contributors interested in testing coding agents on real, bounded tasks. Start with one ready issue and submit one small change with reproducible checks and tool provenance. Review, onboarding, and negative results count as contributions. Reliable contributors can grow into shared technical responsibility; the founder focuses on project direction.

This is a proposal, not a posted recruitment message or evidence that contributors have joined. Directory discovery and a pinned invitation can be delegated, but refusing all discovery, contact, and onboarding would make reliable recruitment an unsupported expectation.

## Decision sequence and success measures

1. **Repair the entrance.** Align starter tasks with current-main setup/testing instructions and reconcile existing local-gate PRs instead of opening redundant ones.
2. **Establish review capacity.** Review the existing CodeRabbit proposal, perform any app authorization deliberately, and identify the human responsible for integration.
3. **Run one bounded agent trial.** Use Jules within its free allowance and stop rather than pay when capacity is exhausted.
4. **Run one human recruitment experiment.** Maintain a small ready-task queue, submit a directory listing, and seek a co-maintainer through an explicit, scoped invitation.
5. **Delegate progressively.** After evidence of reliable work, share a subsystem and its review/release responsibilities under existing governance.

Suggested pilot targets, not predicted outcomes: one useful accepted agent change, one genuine external contribution, one repeat contributor or prospective co-maintainer, and less maintainer time per accepted change. Record abandoned attempts and review minutes too. More generated PRs are not success when the review backlog grows.

No automatic merging, constitutional edits, review-gate bypasses, mass mentions, unsolicited bot outreach, recursive issue creation, or paid-provider fallback is proposed. Explicit human-review requirements remain in force. [R2]

## Preservation and verification

This document preserves the owner's request, the assistant's practical recommendation, material repository findings, and current provider references. It is intentionally a single conversation record rather than another controller or an adopted process rewrite. A future accepted pilot should update the linked community strategy with measured results.

Verification in this session consisted of reading repository files/issues/PRs through the connected GitHub tools and checking provider-owned documentation. No agent task was executed, no volunteers were contacted, and no test-suite performance claim was independently reproduced. Provider offers and open-PR state are time-sensitive.

## Reference map

### Repository evidence

- [R1] [Repository metadata](https://api.github.com/repos/MSKazemi/idkmesh) and [README](../../README.md).
- [R2] [Project rules](../../PROJECT_RULES.md) and [agent guidance](../../AGENTS.md).
- [R3] [ACE bootstrap observer, issue 109](https://github.com/MSKazemi/idkmesh/issues/109).
- [R4] [Advisory reviewer proposal, PR 404](https://github.com/MSKazemi/idkmesh/pull/404).
- [R5] [Local gate correction, PR 396](https://github.com/MSKazemi/idkmesh/pull/396) and [related PR 386](https://github.com/MSKazemi/idkmesh/pull/386).
- [R6] [Current contribution guide](../../CONTRIBUTING.md).
- [R7] [Interoperability documentation, issue 402](https://github.com/MSKazemi/idkmesh/issues/402).
- [R8] [First-run feedback, issue 403](https://github.com/MSKazemi/idkmesh/issues/403), [machine setup reports, issue 401](https://github.com/MSKazemi/idkmesh/issues/401), [independent node review, issue 138](https://github.com/MSKazemi/idkmesh/issues/138), and [independent control-plane audit, issue 151](https://github.com/MSKazemi/idkmesh/issues/151).

### External primary sources checked 2026-09-09

- [S1] [Jules limits and plans](https://jules.google/docs/usage-limits/).
- [S2] [Running tasks with Jules](https://jules.google/docs/running-tasks/).
- [S3] [CodeRabbit plans, OSS access, and review limits](https://docs.coderabbit.ai/management/plans).
- [S4] [GitHub Copilot cloud agent](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent) and [Copilot plans](https://docs.github.com/copilot/get-started/plans-for-github-copilot).
- [S5] [Codex for Open Source application](https://openai.com/form/codex-for-oss/).
- [S6] [Dependabot version updates](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependabot-version-updates).
- [S7] [Jules scheduled tasks](https://jules.google/docs/scheduled-tasks/).
- [S8] [GitHub labels for helpful contributions](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/encouraging-helpful-contributions-to-your-project-with-labels).
- [S9] [Up For Grabs contributor directory](https://up-for-grabs.net/).
