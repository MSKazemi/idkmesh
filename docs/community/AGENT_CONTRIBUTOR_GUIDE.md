# Contribute to IDKMesh with your own AI coding agent

You can contribute to IDKMesh with Claude Code, OpenAI Codex, Google Jules, or any
other coding agent you are authorized to use. This guide gets you from zero to a
reviewable pull request in about ten minutes of setup. It adds nothing to the
project's rules: [`AGENTS.md`](../../AGENTS.md) and
[`CONTRIBUTING.md`](../../CONTRIBUTING.md) stay the source of truth, and this page
only shows how to point your agent at them.

Your agent works for you. You are the contributor, so you are accountable for
what you submit, and a person has to read the diff before it is posted.

## What the project provides, and what it does not

- The project provides: a clear task list, tests that tell you whether you broke
  something, and public review.
- The project does not provide: API keys, subscriptions, compute, or any shared
  credentials. Use your own accounts and your own quota.
- Please do not point an agent at the repository and leave it unattended. One
  small pull request that a person checked is worth more than many unchecked ones.

## 1. Set up (about 5 minutes)

You need Git, Python 3.11 or 3.13, and a GitHub account.

```bash
# Fork MSKazemi/idkmesh on GitHub first, then:
git clone https://github.com/<you>/idkmesh.git
cd idkmesh
git remote add upstream https://github.com/MSKazemi/idkmesh.git
git fetch upstream
git switch -c my-change upstream/main

make setup     # creates .venv and installs test dependencies
make smoke     # runs only the tests affected by your uncommitted changes
```

On Windows, use the direct path in [`CONTRIBUTING.md`](../../CONTRIBUTING.md)
(`python -m venv .venv`, then `.venv\Scripts\python.exe -m pip install -r
requirements-phase0.txt pytest`).

What the commands cost, from [`docs/TESTING.md`](../TESTING.md):

| Command | Use it for | Rough cost |
| --- | --- | --- |
| `make smoke` | fast feedback while you edit | about a second |
| `make test` | the full unit suite (the tier CI requires) | about a minute on an idle machine; budgeted at 90 CPU-seconds |
| `make gate` | the cheapest complete tier for your change | depends on the change |
| `make integration` | unit suite plus schema and link gates | longer than `make test` |

Times grow on a busy machine; the budgets are in CPU-seconds for that reason (see
[`docs/TESTING.md`](../TESTING.md)). If a budget fails on your machine, re-run on an
idle one before changing anything, and never raise a budget to get green. If the
suite cannot run at all on your system, that is worth an issue with your OS,
Python version and the failure.

Do not use `python -m unittest discover` to check your work. It silently skips
the module-level pytest functions and still reports `OK`.

## 2. Pick one bounded task

- Browse [good first issues](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22good+first+issue%22),
  [help wanted](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22help+wanted%22)
  and issues labelled `one:agent-task` ("bounded task suitable for a human or
  connected agent"). The [contributor quickstart](CONTRIBUTOR_QUICKSTART.md) and the
  [starter tasks](STARTER_TASKS.md) describe concrete options; check an issue's
  state before you start, because tasks close.
- Be aware that many newcomer issues carry `authority:human-required` or
  `human-required`. They ask for something only a person can provide, such as a
  first-run report from a real machine or an independent review, so an agent cannot
  complete them for you. They are still valuable if you do the observing yourself.
- Skip issues labelled `research-evidence`, `security-sensitive`, `blocked` or
  `needs-decomposition` unless you have talked to a maintainer.
- `do-not-automate` only keeps the repository's own Jules dispatcher away from an
  issue (see section 5). Maintainers add it to starter tasks on purpose, so the task
  stays free for you; on a `good first issue` or `help wanted` task you are welcome
  to use your own agent.
- If no bounded, agent-doable task is open when you arrive, say so on the
  [bring-your-own-agent invitation](https://github.com/MSKazemi/idkmesh/issues/407)
  or open an issue describing a small task you would like to take. That is a normal
  and welcome way in.
- Check assignees, comments and linked pull requests, then comment on the issue with
  the piece you intend to do. Avoid duplicating someone else's work unless the task
  says parallel attempts are welcome.
- For a large feature, a new protocol or a design change, open an issue first.

## 3. The safe loop

1. Refresh from `upstream/main` and note the exact base commit.
2. Give your agent the task, [`AGENTS.md`](../../AGENTS.md), and the prompts below.
3. Keep the change small and focused: one reviewable outcome per pull request.
4. Add or update a test that would have failed before your change.
5. Update the documentation in the same pull request, including any `--help` text,
   examples or architecture note that your change makes wrong.
6. Run `make smoke` while iterating and `make gate` before you push. If you edited
   Markdown, also run `python scripts/check_links.py` (stage new files with
   `git add` first, because links resolve against tracked files).
7. Read the full diff yourself. Stage files by name, not with `git add -A`, and
   read `git status` before you commit.
8. Open the pull request with the template and fill in the provenance section.

### Provenance: say what was generated and what you checked

The pull-request template has an "AI/tool provenance" section. Use it. State the
tool and model if you know them, the base commit, the exact commands you ran with
their results, what you personally verified, and anything still uncertain. The
project treats agent output and automated review as advisory: they are never
independent human review, and a pull request is merged on evidence, not on who
vouched for it.

### Link issues carefully

Put issue numbers on the `Refs:` line. Use `Closes: #<issue>` only when merging
should actually close it, with nothing else on that line. GitHub closes issues
from closing keywords in titles, bodies and commit messages, and the PR Gate
check enforces this rule (see [`CONTRIBUTING.md`](../../CONTRIBUTING.md)).

### Several files from one agent

Avoid publishing one commit per file edit. Each new pull-request head can restart
CI and invalidate review evidence. Let your agent finish a coherent change locally
and push it once. See "Agent publication backpressure" in
[`AGENTS.md`](../../AGENTS.md).

## 4. Quick starts

All three tools should be told the same thing. This brief works in each of them:

```text
You are helping me contribute to https://github.com/MSKazemi/idkmesh.
Read AGENTS.md and CONTRIBUTING.md first and follow them exactly.
Task: <one issue link and one sentence>.
Rules: make one small, focused change; add a test that fails without it; update
the docs and any --help text in the same change; run `make smoke` and `make gate`
and report the exact results; do not touch .github/workflows, add third-party
actions or dependencies, or include secrets; stage files by name; do not
force-push. Fill in the pull-request template, including the AI/tool provenance
section, and state plainly what was generated and what is not verified.
```

### Claude Code

Claude Code reads [`AGENTS.md`](../../AGENTS.md) on its own when it finds no
`CLAUDE.md` in your working directory or above it (Anthropic documents this for
v2.1.277 and later). You normally need to do nothing. If you keep a personal
`CLAUDE.md` or `CLAUDE.local.md`, Claude reads that instead and skips `AGENTS.md`,
so start your file with one line:

```text
@AGENTS.md
```

`CLAUDE.md` is listed in this repository's `.gitignore` on purpose: keep yours
local and never commit it. Authentication is your own Claude subscription or API
key. `gh` (the GitHub CLI) lets Claude open the pull request from your fork.

If you want `@claude` mentions on your own fork, Anthropic's GitHub Action
(`anthropics/claude-code-action`) is installed on a repository you administer, with
your own secret, and it runs there on your minutes and quota. Do not add it to
this repository: please open an issue first for any change under
`.github/workflows/`.

### OpenAI Codex

Codex reads `AGENTS.md` from the repository root down to your working directory
and combines the files, so there is nothing to configure. Sign in with your own
ChatGPT account. Codex cloud lets you pick a GitHub repository, review the
changes and open a pull request when you are ready; OpenAI also documents a
command-line tool. Point whichever you use at your fork, and open the pull request
from the fork to `MSKazemi/idkmesh`. Check OpenAI's documentation for which plan you
need.

### Google Jules

Jules works on repositories you connect through its GitHub App ("Connect to
GitHub account", then choose all or specific repositories). It looks for
`AGENTS.md` in the repository root, shows you a plan to approve before it writes
code, and then lets you create a branch and open a pull request from it. Google's
documentation does not say how Jules behaves with forks or repositories you do not
own, so treat that as untested: connect your fork, and check the result yourself.
Free-tier limits change; see Google's current
[usage limits](https://jules.google/docs/usage-limits/).

### Freebuff

[Freebuff](https://freebuff.com/) describes itself as a free coding agent ("$0",
daily free credits, no API key or credit card for the CLI and desktop app). Install
the CLI with `npm install -g freebuff` and run it inside your fork. Its public page
does not show what it does with your data, so read its terms before pointing it at
anything private; for this public repository that is rarely an issue. As with every
agent here, you review the diff and you open the pull request.

### Other agents

Any agent that follows `AGENTS.md` works. If it needs a different file name, give
it the same brief above.

## 5. About the repository's own Jules automation

The maintainer runs a separate, owner-controlled Jules dispatcher
([`docs/operations/JULES_AUTOMATION.md`](../operations/JULES_AUTOMATION.md)). It is
driven by labels such as `agent-ready`, `agent:jules-eligible`,
`agent:jules-dispatched` and `agent:jules-needs-attention`. Those labels are set
by maintainers and by the repository's router, not by contributors. Please do not
add them, and do not add the legacy `jules` label. The router can queue small
tasks for that automation by itself, which is why maintainers mark starter tasks
`do-not-automate`. They are queue controls, not a
way to request review. Output from that automation carries no more authority than
yours does: it is not independent human review.

## 6. What not to do

- Do not include secrets, tokens or private data, and do not commit local agent
  files (`CLAUDE.md`, `GEMINI.md`, `.env*`, `.vscode/`).
- Do not change `.github/workflows/`, add a third-party GitHub Action, or add a
  dependency without discussing it in an issue first. A workflow or action change
  runs code in the project's CI, so it needs an explicit decision, and a
  third-party action pinned by a mutable tag cannot be reviewed once and trusted.
- Do not force-push over a branch other people have reviewed.
- Do not describe agent or tool output as human review, and do not claim you ran
  something you did not.
- Do not open many pull requests at once or send unattended streams of generated
  changes. One focused pull request at a time.
- Do not weaken a test, a gate or a lint rule to make something pass.

## 7. What happens after you open the pull request

- A maintainer reads the diff and replies in public. The required CI check, PR
  Gate, runs the unit tier plus the Markdown link check on Python 3.11 and 3.13,
  without repository secrets. GitHub may ask a maintainer to approve the first CI
  run on a pull request from a fork.
- An automated reviewer (CodeRabbit) may comment. Its comments are advisory and
  carry no authority. Disagree with it in the thread if you think it is wrong.
- Maintainers may ask for changes, push small fixes on top, or reshape the change
  to fit the architecture; they will say what they changed and keep your commits
  and credit. Turnaround is not guaranteed, because this is a volunteer project.
- Contributions that land are recorded in [`CONTRIBUTORS.md`](../../CONTRIBUTORS.md),
  which describes how entries are added. If you would rather not be listed, say so
  in the pull request.
- Questions or confusion are welcome as issues. Honest reports of where setup
  broke are useful project evidence.

Conduct: [`CODE_OF_CONDUCT.md`](../../CODE_OF_CONDUCT.md). Security issues: follow
[`SECURITY.md`](../../SECURITY.md) and do not open a public issue.
