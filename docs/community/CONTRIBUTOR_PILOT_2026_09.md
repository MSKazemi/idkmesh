# Contributor pilot: one useful contribution at a time

Date: 2026-09-09. This is a bounded operating pilot under the existing
[community strategy](COMMUNITY_GROWTH_STRATEGY.md),
[project rules](../../PROJECT_RULES.md), and [governance](../../GOVERNANCE.md).
It grants no new integration, spending, or administrative authority.

## Join

The public entry point is [the co-maintainer and bring-your-own-agent invitation](https://github.com/MSKazemi/idkmesh/issues/407).
Participation is voluntary and unpaid. No hardware, paid model subscription, or
compute donation is required. The current bootstrap review contact remains
MSKazemi until responsibility is explicitly shared with another maintainer.

Choose a task rather than learning the entire research history:

| Task | Intended participant | Deliverable |
| --- | --- | --- |
| [403: first-read confusion](https://github.com/MSKazemi/idkmesh/issues/403) | A genuinely new human reader | One honest report, no code needed |
| [399: one README translation](https://github.com/MSKazemi/idkmesh/issues/399) | Someone able to verify the target language | One translation preserving maturity/limitation statements |
| [398: architecture diagram](https://github.com/MSKazemi/idkmesh/issues/398) | Human or AI-assisted contributor | One diagram checked against authoritative prose |
| [402: interoperability setup](https://github.com/MSKazemi/idkmesh/issues/402) | Initial bounded coding-agent pilot | Focused documentation PR with real before/after test evidence |

Check issue state, recent comments, assignees, and linked PRs before working.
Comment on the task with your intended scope. Do not duplicate an active attempt.
Issue 403 deliberately welcomes multiple independent people.

Use [the current setup/test instructions](../../CONTRIBUTING.md). A command
mentioned in an old branch is not proof that it exists on current `main`.

## Bring your own agent

Use an authorized tool/account or a local setup you control. Keep contributions
small. Report tool/model identity if known, source revision, commands actually
run, results including failures/skips, and what a person checked. Do not label
AI-written first-time-user feedback as an independent human observation.

No shared credentials, quota evasion, surprise paid usage, or recursive streams
of PRs. Submit one candidate, respond to review, and only then take the next task.
A useful negative result is welcome. Owner-directed bots and external humans
remain separate participation categories.

## Project-operated coding-agent pilot

Start with Jules on issue 402; do not build a new scheduler first. The pilot has
one active task at a time and a maximum of one candidate PR for that attempt.
This is a maintainer-operated limit, not a claim of an implemented queue lock.
Pause new starts whenever the prior candidate is awaiting review.

Before starting, the owner must authorize the Jules GitHub app for this
repository and confirm that the task uses an eligible free allowance. The
`jules` issue label is a request to the authorized integration, not evidence of
installation or execution. Only an actual Jules acknowledgement/session and its
result can establish that it ran. If there is no acknowledgement, do not keep
reapplying labels or launch duplicate tasks.

Issue 402 contains the task scope and stop conditions. Do not execute unrelated
refactors, workflow changes, dependency upgrades, or governance changes. Prompt
instructions express scope; actual permissions and repository integration rules
must enforce the security boundary. Exhausted free capacity means stop/queue,
never enable paid fallback. Do not enable scheduled tasks during this pilot.

## Advisory review

[PR 404](https://github.com/MSKazemi/idkmesh/pull/404) installed repository
configuration, not the CodeRabbit GitHub app. The owner must authorize the app
for the intended repository; no third-party authorization is inferred from a
configuration file. After authorization, request a review on one ready PR with
`@coderabbitai review` if an automatic review has not already run.

Keep the OSS/no-paid-overage path. Advisory comments do not replace required
human review or grant approval/merge authority. A rate-limited or absent review
is not a successful review. Record useful findings, false positives, and actual
maintainer effort rather than counting comments.

## Shared technical ownership

Express interest in issue 407. Start by helping with a small review or onboarding
problem, then discuss a bounded area such as contributor onboarding or the
`gate-audit` CLI. Sustained judgment and community support matter more than
commit count. Any reviewer/maintainer appointment must be explicit and public
under existing governance. The founder can delegate operational work without
inventing automatic access rights or promising compensation.

## Directory submission

[The prepared Up For Grabs entry](up-for-grabs-idkmesh.yml) is submission material,
not proof that the project is listed. Up For Grabs asks for a pull request adding
`_data/projects/idkmesh.yml` to its `gh-pages` branch. Follow its
[listing instructions](https://github.com/up-for-grabs/up-for-grabs.net/blob/gh-pages/docs/list-a-project.md).

Submit only while a real maintainer can guide newcomers and review their work.
The connected tools used for this pilot do not expose creation of the required
external fork; no upstream PR or acceptance is claimed. A contributor with an
authorized GitHub web session can use the prepared entry in the upstream web
editor. Do not create an unrelated promotional issue instead of following the
upstream submission process.

## Evaluation and stopping rule

For each attempt record the issue, actor category (external human,
external AI-assisted human, or owner-operated agent), base revision, PR/result,
actual verification, maintainer review minutes if measured, and regressions.
Use `not measured` instead of inventing time data.

Evaluate after the first three completed attempts, or stop earlier if the review
queue grows, the free allowance is unavailable, or a security concern appears.
Expand only when accepted useful work reduces rather than increases maintainer
burden. Three attempts are a pilot checkpoint, not statistical proof of efficacy.
No independent participants, agent completions, or measured savings are claimed
merely because this document or the invitation was published.

## Sources and project record

Provider details were checked on 2026-09-09 and can change:
[Jules issue workflow](https://jules.google/docs/running-tasks/),
[Jules allowances](https://jules.google/docs/usage-limits/), and
[CodeRabbit OSS plan and limits](https://docs.coderabbit.ai/management/plans).
This pilot relies on confirmed account access, not indefinite free-tier guarantees.

See [the execution record](../conversations/2026-09-09-contributor-pilot-execution.md)
and [the prior proposal PR](https://github.com/MSKazemi/idkmesh/pull/406) for context.
