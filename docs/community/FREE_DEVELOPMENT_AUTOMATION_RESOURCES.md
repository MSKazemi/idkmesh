# Free and Zero-Spend Development Automation Resources

Verified against current vendor/project documentation on **2026-09-22**.

This guide focuses on tools that can help develop `idkmesh` in ways similar to Google Jules: implementing bounded tasks, editing code, running tests, opening pull requests, reviewing changes, or automating repository maintenance.

"Free" has three different meanings here:

- **Hosted free tier**: the vendor runs the service for free within limits.
- **Open-source software**: the agent software is free, but model/API inference may still cost money.
- **Zero-spend capable**: the software can be paired with a local model or a vendor free tier so the project can run without project spend.

The repository's trust rule still applies: **agent output is a candidate change, not acceptance evidence or merge authority**.

## Closest alternatives to Jules

| Resource | What it can do | Free status | Fit for IDKMesh |
| --- | --- | --- | --- |
| **OpenHands** | GitHub Action can react to a `fix-me` label or `@openhands-agent`, attempt an issue/PR change, and create/update a PR. | Open-source/local edition is free; hosted individual tier is free to access, but model usage may require BYOK or at-cost inference. | **High.** This is the closest additional issue-to-PR worker to Jules. Use it as a separate worker identity, not as its own verifier. |
| **Amazon Q Developer for GitHub (Preview)** | Feature-development label or `/q dev` can turn issues into implementation PRs; `/q review` performs PR review. | GitHub integration currently offers limited free usage, including without an AWS account; higher free limits are available after registration. | **Potentially high**, but AWS documentation frames setup around GitHub organizations. `MSKazemi/idkmesh` is currently user-owned, so confirm installation eligibility before depending on it. |
| **Google Antigravity CLI** | Terminal coding agent with multi-file editing, tool use, headless one-shot mode, subagents, and machine-readable output. | Current consumer/free Google path after the 2026 Gemini CLI transition. Local headless mode uses cached credentials after interactive authentication; do not assume that makes GitHub Actions authentication free or appropriate. | **High for human-operated local development.** IDKMesh represents it as a bounded local preset; CI/headless automation remains separately gated. |
| **mini-SWE-agent / SWE-agent** | Autonomous software-engineering agents designed to solve repository tasks/issues using a model of your choice. | Open source. Model/API/runtime cost is separate; can be paired with local or free-access models. | **High for research/benchmarking.** Especially relevant to IDKMesh because it exposes an agent worker that can be measured rather than trusted by default. |
| **goose** | Local desktop/CLI/API agent that can write code, run commands, automate workflows, and use MCP extensions. | Apache-2.0 open source. Supports local models such as Ollama as well as cloud providers. | **High for zero-spend local workers** and for testing IDKMesh worker-adapter diversity. |
| **Cline** | IDE and CLI coding agent; CLI can run headlessly for scripting/CI. Reads/writes files and executes commands. | Agent software is open source. Model use depends on provider; local/free model paths are possible. | **Medium-high.** Useful as another heterogeneous worker, particularly for human-supervised tasks. |
| **Aider** | Git-aware terminal coding assistant that edits files and commits changes. | Open source. Supports local models and some free API/model options. | **Medium.** Better for supervised coding than unattended issue dispatch, but useful for contributors and local remediation. |

## Free services that strengthen agent-generated PRs

These are not Jules replacements, but they make automated development safer and faster.

| Resource | Free capability for this public repository | Recommended role |
| --- | --- | --- |
| **GitHub Actions** | Standard GitHub-hosted runners are free and unlimited for public repositories. | Routing, tests, issue/label automation, scheduled maintenance, and orchestration of self-hosted/open-source agents. |
| **Dependabot** | Security/version update automation and PR creation are available on GitHub repositories. | Dependency maintenance and vulnerability patch PRs. |
| **CodeQL** | CodeQL CLI/code scanning is free for public repositories. | Deterministic security analysis on generated code. |
| **CodeRabbit** | Public repositories can receive free code reviews. The separate CodeRabbit coding Agent is usage-priced after applicable free/trial minutes. | Advisory review only. `idkmesh` already has `.coderabbit.yaml`. Do not treat its review as independent human approval. |
| **Semgrep Community Edition** | Free/open-source static analysis with community rules and CI support. | Fast security/bug-pattern checks before merge. |
| **Codecov** | Open-source/public projects receive free coverage service with unlimited public-repository uploads. | PR coverage feedback and regression visibility. |
| **SonarQube Cloud OSS plan** | Public open-source projects can use the OSS plan for free. | Additional quality/security analysis, especially useful if its findings add non-duplicative evidence. |

## What is not counted as a free Jules replacement

- **GitHub Copilot cloud coding agent**: Copilot Free provides limited assistance, but current GitHub documentation places cloud coding-agent access in paid Copilot plans; therefore it is not part of this zero-cost list.
- **Qodo**: current pricing documentation says there is no permanent free tier after the trial, so it is not counted here.
- **Paid-only hosted agents**: tools can still be useful later, but they should not be part of a zero-project-spend automation baseline.

## Implementation status in IDKMesh

The repository now separates **agent identity/configuration** from execution authority:

- Jules: existing GitHub issue-dispatch worker.
- OpenHands: guarded manual pilot in PR #642 / issue #641.
- goose, Antigravity CLI, mini-SWE-agent: represented by the provider-neutral `AgentPreset` contract in issue #647. This is configuration only; it does not execute the tools yet.
- next local-runner slices: disposable exact-SHA workspace, process/resource limits, sandbox/network enforcement, artifact capture, then one pinned/versioned live preset. Antigravity replaces the stale `gemini-cli-free` zero-spend claim for consumer accounts.

The preset contract intentionally stores structured executable/argv metadata rather than shell command strings. Issue text cannot select an executable, inject fixed arguments, expose host/repository credentials, disable the sandbox, or grant candidate acceptance authority.

### Additional free/open-source worker candidates

After the first three presets are proven, the same contract can be extended to **Aider** and **Cline CLI** as heterogeneous supervised/headless workers. They should be added only after their exact non-interactive invocation and credential boundary are pinned and smoke-tested. Do not add a new scheduler per agent.

## Recommended IDKMesh stack

A practical next step is to keep **Jules** as one worker and add diversity instead of replacing it.

1. **Jules** — bounded implementation tasks already routed from issues.
2. **OpenHands** — second issue-to-PR implementation worker for a separate task class.
3. **goose** — first local bounded-runner target because issue #577 already selects it as preferred C4-F worker.
4. **Antigravity CLI** — current Google free-personal local worker; headless `agy -p` is suitable for bounded local runs after authentication and sandbox policy are proven.
5. **mini-SWE-agent** — research/benchmark worker behind the same boundary after the runner is proven.
6. **Aider / Cline CLI** — later heterogeneous presets for supervised/headless experiments.
7. **GitHub Actions** — the orchestrator that routes labels/tasks and always runs the repository's required gates.
8. **CodeRabbit + CodeQL + Dependabot + Semgrep + coverage tooling** — review and deterministic evidence layers, never merge authority.

Suggested routing labels:

- `agent:jules`
- `agent:openhands`
- `agent:local`
- `agent:research`
- `agent:no-auto`
- `risk:low`
- `risk:medium`
- `risk:high`
- `needs-human-review`

Only low-risk, bounded tasks should be automatically dispatched. Security-sensitive changes, workflow-permission changes, release/signing changes, governance changes, and changes that alter verification authority should remain human-gated.

## Zero-project-spend architecture

A realistic zero-spend setup for the current public repository is:

```text
GitHub issue
   |
   +-- agent:jules ---------> Jules ------------------+
   |                                                |
   +-- agent:openhands -----> OpenHands -------------+--> candidate PR
   |                                                |
   +-- agent:research ------> mini-SWE-agent/goose --+
                                                    |
                                                    v
                                  GitHub Actions required gates
                                                    |
                      +-----------------------------+------------------+
                      |                             |                  |
                    CodeQL                       Semgrep           coverage
                      |                             |                  |
                      +-----------------------------+------------------+
                                                    |
                                                    v
                                      explicit human integration
```

For open-source/self-hosted agents, using a local model through Ollama can remove API inference spend, while GitHub Actions can provide free standard public-repository CI capacity. If a self-hosted runner is used for untrusted pull requests, isolate it carefully; public-repository workflows must not expose host credentials or a persistent developer machine to arbitrary contributor code.

## Source documentation

Primary references checked for this guide:

- GitHub Actions public-repository runner pricing: https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- GitHub Actions billing: https://docs.github.com/en/actions/concepts/billing-and-usage
- OpenHands GitHub Action: https://docs.openhands.dev/openhands/usage/run-openhands/github-action
- OpenHands pricing/open-source plan: https://www.openhands.dev/pricing
- Amazon Q Developer for GitHub: https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/amazon-q-for-github.html
- Amazon Q Developer GitHub quickstart: https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/github-quickstart.html
- Amazon Q Developer pricing: https://aws.amazon.com/q/developer/pricing/
- Google Gemini CLI -> Antigravity transition: https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/
- Antigravity CLI headless mode: https://antigravity.google/docs/cli/headless/
- Antigravity CLI installation/auth: https://antigravity.google/docs/cli-install
- goose: https://block.github.io/goose/
- SWE-agent / mini-SWE-agent: https://github.com/SWE-agent/SWE-agent and https://mini-swe-agent.com/
- Aider model/provider documentation: https://aider.chat/docs/llms.html
- Cline: https://github.com/cline/cline
- CodeRabbit pricing: https://www.coderabbit.ai/pricing
- CodeQL CLI licensing/availability: https://docs.github.com/en/code-security/concepts/code-scanning/codeql/codeql-cli
- Dependabot quickstart: https://docs.github.com/en/code-security/tutorials/secure-your-dependencies/dependabot-quickstart
- Semgrep Community Edition: https://semgrep.dev/products/community-edition/
- Codecov pricing: https://about.codecov.io/pricing/
- SonarQube Cloud OSS plan announcement: https://community.sonarsource.com/t/introducing-the-new-free-oss-plan-in-sonarqube-cloud/176923

Because free tiers and quotas change, re-check vendor documentation before making a quota part of repository policy.
