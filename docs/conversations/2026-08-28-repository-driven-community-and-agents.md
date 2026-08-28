# Conversation Record — Repository-Driven Community and Free Agents

Date: 2026-08-28

## Project-owner questions / goals

The project owner wants IDKMesh to grow into a very large contributor community without requiring large amounts of personal time spent on social media or advertising. The desired primary surface is the GitHub repository itself.

Questions raised:

- How can one GitHub repository organically reach thousands of contributors?
- How can visibility and collaboration be designed for physics, mathematics, computer science, web development, art, robotics, and AI agents?
- What innovative research questions should IDKMesh ask about community growth and visibility?
- Are there free/open-source agents or robots that can continuously help evolve the project?

## Assistant synthesis

The proposed strategy is to treat community growth as a systems problem rather than a marketing problem. The repository should become a community engine that optimizes the full loop:

`discover -> understand -> bounded task -> contribute -> verify -> recognize -> return -> help others -> discover`

A branching-process-inspired metric called the **community reproduction number** `R_c` was proposed: the expected number of new retained contributors eventually caused by one active contributor/contribution cycle. The research target is to determine whether `R_c > 1` is achievable while keeping maintainer workload low.

GitHub-native mechanisms emphasized:

- accurate repository topics;
- continuous real `good first issue` / `help wanted` supply;
- complete community-health files;
- GitHub Discussions instead of requiring external chat/social platforms;
- GitHub Pages generated from repository content;
- reproducible releases/experiments;
- fast automated verification and recognition.

The response explicitly avoids automated spam or unsolicited outreach to unrelated repositories.

## Robots / agents

Deterministic automation recommended first:

- GitHub Actions;
- Dependabot;
- CodeQL/code scanning;
- secret scanning / push protection;
- OpenSSF Scorecard;
- Renovate where appropriate.

Open-source AI-agent options identified for local/self-hosted operation include OpenHands and SWE-agent/mini-swe-agent. Local open-weight models can avoid API fees, but hardware and electricity remain real costs.

A proposed self-evolution architecture separates roles into Observer, Planner, Builder, Critic, Verifier, Integrator, and Historian. The safety invariant is that no agent may propose, approve, and merge the same change by itself.

## Research ideas promoted

The detailed strategy and 30 research questions were promoted to:

`docs/findings/2026-08-28-repository-driven-community-growth.md`

Topics include GitHub-native discovery, contributor activation energy, cross-disciplinary percolation/connectivity, queueing/review latency, contributor retention, AI-agent provenance, bounded autonomous maintenance, anti-Sybil mechanisms, and minimum maintainer workload for a growing community.

## Repository finding

The README currently points newcomers to `CONTRIBUTING.md`, `GOVERNANCE.md`, and `LICENSE`, but those paths were not present when checked in this turn. This should be fixed because it creates immediate newcomer friction.

## Working direction

IDKMesh should pursue **repository-driven organic community growth as a first-class experiment**. Social media may later amplify the project but should not be a required dependency for growth.
