# Conversation Record — Free Agents and Volunteer Computer Nodes

**Date:** 2026-08-28

## Project-owner question

Can the public IDKMesh repository be attached to free agents in different places so they work continuously or sometimes? How can such agents be found, and could contributors run a small application on their computers to participate?

Repository: https://github.com/MSKazemi/idkmesh

## Assistant interpretation

The question has two related parts:

1. **Existing agent infrastructure:** identify genuinely free/free-tier/open-source agents and GitHub automation that can work against the repository continuously, periodically, or on demand.
2. **IDKMesh-native volunteer application:** explore a small application that contributors can install on laptops/desktops/servers so heterogeneous local agents/models/compute can accept bounded work safely.

## Research findings

The useful near-term ecosystem includes:

- GitHub Actions on GitHub-hosted runners for public-repository automation;
- Google's official `run-gemini-cli` GitHub Action and Gemini CLI free-tier access for bounded repository tasks;
- Google Jules as a no-cost-plan autonomous GitHub coding agent with finite daily/concurrency limits;
- OpenHands Agent Canvas as an open-source/self-hostable agent control center with scheduled/webhook automations;
- goose as an open-source local coding/automation agent that can use Ollama local models;
- SWE-agent as an open-source issue-fixing/research agent;
- Ollama as a local runtime enabling zero-project-API-cost nodes when volunteers provide hardware/electricity;
- GitHub CI/CodeQL as independent verification infrastructure.

A critical security finding is that normal personal volunteer computers should **not** simply be connected as unrestricted GitHub self-hosted runners to a public repository. GitHub's own security guidance warns that public-repository pull requests can compromise persistent self-hosted runners.

## Proposed direction

Create a hybrid architecture:

```text
GitHub events/issues
       |
       v
bounded Work Units
       |
 +-----+----------------+
 |                      |
 v                      v
GitHub-hosted agent   IDKMesh volunteer node
                        |
                        v
                sandboxed adapter
             goose/OpenHands/SWE-agent/
             Gemini CLI/local Ollama/etc.
 |                      |
 +----------+-----------+
            |
            v
candidate patch/report/test result
            |
            v
independent verification + human review
```

The proposed small application is tentatively called `idkmesh-node`. It should be provider-neutral and accept only bounded Work Units. It should run each task inside a disposable sandbox with explicit CPU/RAM/time/network permissions, record provenance, and return candidate artifacts rather than gaining direct merge authority.

Suggested worker roles are observer, researcher, coder, verifier, and deterministic compute worker.

## Meaning of continuous

The recommendation is not to burn LLM tokens continuously. "Continuous" should mean event-driven and periodically awakened:

- new issue -> triage/decomposition;
- approved `agent-ready` issue -> bounded solver;
- PR -> tests/review/security verification;
- nightly -> maintenance/drift checks;
- idle volunteer node -> request one eligible Work Unit;
- disagreement or failed validation -> independent verifier.

## Durable artifacts produced from this conversation

- `docs/findings/2026-08-28-free-agent-network-landscape.md`
- `docs/architecture/AGENT_NETWORK_AND_VOLUNTEER_NODES.md`
- implementation/research issues for a first `idkmesh-node` prototype and repository-agent pilot.

## Open questions

1. What should the canonical Work Unit schema be?
2. Which sandbox technology should be the baseline on macOS, Windows, and Linux?
3. Should the first networked prototype use GitHub issues/labels directly or a tiny broker service?
4. How should result bundles encode model/tool identity and reproducibility evidence?
5. How should a node authenticate without exposing broad GitHub credentials?
6. How should the scheduler learn which hardware/model/agent combinations are good for each task class?
7. How can IDKMesh make node installation simple enough for a large open-source community while keeping the security boundary understandable?

## Community impact

This creates a new contribution path: a participant may contribute code, reviews, research, local model capacity, CPU/GPU time, benchmarks, or verification. Participation must remain opt-in, resource-capped, transparent, easy to stop, and secondary to contributor safety.
