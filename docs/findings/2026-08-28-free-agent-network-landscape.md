# Free / Low-Cost Agent Network Landscape for IDKMesh

**Date:** 2026-08-28

## Question

Can IDKMesh attach its public GitHub repository to free AI/software agents that work continuously, periodically, or on demand? Can volunteer computers run a small IDKMesh application and contribute useful agent/compute work safely?

## Executive finding

Yes, but the best near-term design is a **hybrid, event-driven agent mesh**, not a fleet of permanently running paid cloud agents and not a public pool of ordinary GitHub self-hosted runners.

IDKMesh can combine:

1. free GitHub-hosted automation for the public repository;
2. free-tier GitHub-connected coding agents for bounded tasks;
3. open-source agents running on contributor machines;
4. local open-weight models through Ollama or similar runtimes;
5. a future small `idkmesh-node` application that accepts only bounded, sandboxed Work Units and returns candidate artifacts for verification.

This fits the existing IDKMesh principles: bounded work, independent verification, provenance, community-first contribution, and generation not outrunning verification.

## Immediately usable options

| Option | Cost profile | Works while your laptop is off? | Best IDKMesh use | Important limitation |
| --- | --- | ---: | --- | --- |
| GitHub Actions on standard GitHub-hosted runners | Free for public repositories | Yes | orchestration, CI, scheduled scouts, issue/PR events, validation | individual jobs are bounded; scheduled workflows may be delayed |
| Google `run-gemini-cli` GitHub Action | Action is open source; model access can use free-tier Gemini quotas | Yes | issue triage, PR review, code analysis/modification, `@gemini-cli` tasks, scheduled workflows | requires model authentication; free quota is finite and can change |
| Google Jules | Has a no-cost plan | Yes | autonomous bounded coding tasks against GitHub repositories | free plan has daily/concurrent task limits |
| OpenHands / Agent Canvas | Open source/self-hostable; model may be local or paid/free provider | Only if hosted on an always-on machine | always-on multi-agent control center, GitHub/webhook/scheduled automations | secure self-hosting and sandboxing are essential |
| goose | Open source (Apache-2.0); can use local Ollama models | If the host computer stays on | lightweight local coding/automation worker | quality depends strongly on the chosen model |
| SWE-agent | Open source | If the host computer stays on | issue-fixing experiments and agent research | model/runtime cost depends on configuration |
| Ollama | Open source/local models | If the host computer stays on | zero-API-cost local model runtime for volunteer nodes | consumes contributor CPU/GPU/RAM/electricity |
| GitHub CodeQL | Free for public repositories | Yes | independent security verification | verifier, not a general coding agent |

## Strongest GitHub-native path

GitHub states that standard GitHub-hosted runners are free for public repositories. GitHub Actions workflows can run from repository events or schedules; scheduled workflows can run as often as every five minutes, although GitHub warns they can be delayed at high-load times and are automatically disabled in inactive public repositories after 60 days. GitHub-hosted jobs have execution-time limits, so IDKMesh should use repeated bounded jobs rather than pretending a single job is a permanent daemon.

Sources:

- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://docs.github.com/en/actions/reference/limits

Google maintains an official `run-gemini-cli` GitHub Action. Its documented uses include autonomous routine coding tasks, pull-request review, issue triage, code analysis/modification, scheduled workflows, and on-demand requests such as `@gemini-cli fix this issue`. It also supports a repository `GEMINI.md` context file.

Sources:

- https://github.com/google-github-actions/run-gemini-cli
- https://github.com/google-gemini/gemini-cli

Current Gemini CLI documentation describes a free tier. As of this research date, the documented maximum is 1,000 model requests/user/day when signing in with a Google account under Gemini Code Assist for individuals, while an unpaid Gemini API key is documented at 250 requests/user/day and Flash-only. These quotas are external service policy and must be treated as changeable rather than an architectural guarantee.

Source:

- https://github.com/google-gemini/gemini-cli/blob/main/docs/resources/quota-and-pricing.md

## Useful free autonomous coding service

Google Jules is GitHub-integrated and runs tasks autonomously in fresh VMs. Its documentation currently lists a no-cost plan with 15 daily tasks and 3 concurrent tasks. That makes it useful as one independent contributor/solver, but not as the foundation for an unlimited continuous mesh.

Sources:

- https://jules.google/docs/faq/
- https://jules.google/docs/usage-limits

## Open-source local / self-hosted agents

OpenHands currently describes Agent Canvas as a self-hosted, always-on developer control center that can run agents locally, in Docker, on VMs, or on cloud backends; connect multiple backends; integrate with GitHub; and trigger automations by schedule or webhook. This is highly relevant to IDKMesh as a possible **prototype control plane** before building every orchestration feature from scratch.

Sources:

- https://github.com/OpenHands/OpenHands
- https://github.com/OpenHands/OpenHands/blob/main/docs/SELF_HOSTING.md

goose is an open-source extensible agent that can edit, execute, and test code and supports many providers, including local LLMs through Ollama. It is a good candidate for the first lightweight IDKMesh volunteer worker adapter.

Sources:

- https://github.com/aaif-goose/goose
- https://github.com/block/goose/blob/main/documentation/docs/getting-started/providers.md

SWE-agent is another open-source agent specifically designed to let language models fix issues in real repositories and interact with isolated computer environments. It is useful as a benchmark/alternative implementation rather than something IDKMesh must fork immediately.

Source:

- https://github.com/SWE-agent/SWE-agent

Ollama is a practical local runtime for open models. It makes a genuinely zero-API-cost worker possible when the volunteer provides the hardware and electricity.

Sources:

- https://github.com/ollama/ollama
- https://ollama.com/

## Critical security finding: do not make volunteer PCs ordinary public-repo runners

GitHub explicitly recommends using self-hosted runners only with private repositories and says self-hosted runners should almost never be used for public repositories, because a malicious pull request can execute untrusted code and persistently compromise the runner environment, including secrets or repository credentials.

Therefore the first IDKMesh volunteer-compute design should **not** be:

`public GitHub repository -> arbitrary PR -> contributor's normal laptop as self-hosted GitHub runner`

Instead use:

`approved bounded Work Unit -> disposable sandbox/container/VM -> least-privilege credentials -> candidate patch/artifact -> independent verification -> human/maintainer merge`

Sources:

- https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners
- https://docs.github.com/en/actions/reference/security/secure-use

## Recommended IDKMesh architecture

Use GitHub as the initial public coordination surface and build a thin provider-neutral worker protocol around it.

```text
GitHub issue / research question / PR event
              |
              v
      Work Unit generator
              |
      +-------+---------+
      |                 |
      v                 v
GitHub-hosted       idkmesh-node
agent/action        volunteer node
      |                 |
      v                 v
Gemini/Jules      Goose/OpenHands/SWE-agent
                  + local Ollama model
      |                 |
      +-------+---------+
              |
              v
      candidate artifact
              |
              v
 tests / CodeQL / verifier agents / human review
              |
              v
        merge or reject
```

## Proposed `idkmesh-node`

The smallest useful application should behave more like BOINC for **bounded knowledge/software Work Units** than like a remote shell.

A node should advertise capabilities (OS, CPU/GPU, RAM, available local models, agent adapters, time budget), request an eligible signed Work Unit, clone or materialize the exact input revision inside a disposable sandbox, execute only the allowed tools/resources, record provenance and logs, and return a patch/report/test result rather than directly merging into the canonical repository.

Suggested node modes:

- `observer`: classify, summarize, reproduce, or search public material;
- `researcher`: literature/reference and hypothesis tasks;
- `coder`: bounded implementation task;
- `verifier`: tests, fuzzing, static analysis, critique, reproduction;
- `compute`: benchmark/simulation work that does not need an LLM.

The default permission level should be read-only and network-restricted. Write access should be to an isolated workspace only. Submission should use a narrowly scoped GitHub identity/app or a server-side gateway, never a contributor's full personal token.

## What “continuous” should mean

For IDKMesh, continuous should usually mean **event-driven or periodically awakened**, not an agent burning tokens 24/7.

Examples:

- on new issue -> triage/decomposition agents;
- on `agent-ready` label -> one or more independent solvers;
- on PR -> test/review/security agents;
- nightly -> stale-task discovery, dependency checks, documentation drift checks;
- when a volunteer node is idle -> request one bounded Work Unit;
- on disagreement -> spawn an independent verifier rather than more copies of the same solver.

This is cheaper, easier to audit, and better aligned with verification capacity.

## Near-term recommendation

1. Make the repository agent-readable with explicit agent instructions.
2. Pilot the official Gemini CLI GitHub Action for low-risk issue triage and PR review after adding a free-tier model credential as a GitHub secret.
3. Use Jules manually as an independent bounded solver where useful.
4. Prototype `idkmesh-node` locally with Docker + goose + Ollama (and compare against OpenHands/SWE-agent).
5. Keep GitHub-hosted CI and CodeQL as independent verification.
6. Do not allow autonomous direct merges at this phase.
7. Measure useful verified work per unit of compute, API quota, and human review attention.

## Community impact

This direction is attractive for IDKMesh because it creates a contribution path for people who can donate different things: code, review, spare CPU/GPU time, local models, security expertise, research, or agent-adapter work. A one-command node can become a community-growth surface, but only if participation is safe, transparent, resource-capped, opt-in, and produces reviewable public artifacts.
