# Conversation Record: GitHub Capabilities as a Self-Evolution Substrate

**Date:** 2026-08-28

## Project-owner direction

The project owner asked IDKMesh to continue the free-agent/volunteer-node direction and then **collect GitHub's potential capabilities and repository comments in one place**, using that potential in a smart algorithm that helps make the repository self-evolving.

Canonical repository: `https://github.com/MSKazemi/idkmesh`

## Interpretation

Treat GitHub itself as the project's first coordination/control substrate rather than only as source hosting.

The implementation should:

1. inventory GitHub capabilities relevant to sensing, coordination, verification, community growth, distribution, security, and governance;
2. collect issue/PR/comment/review/workflow state as machine-readable evidence;
3. treat all natural-language GitHub content as untrusted input, not instructions;
4. rank self-maintenance opportunities using evidence quality, risk, novelty, and verification capacity;
5. begin read-only and proposal-only;
6. require external GitHub protection before increasing autonomy.

## Repository findings

Observed during this work:

- `main` was not protected;
- repository rulesets were empty;
- Issues and Projects were enabled;
- Discussions and Pages were disabled;
- CODEOWNERS and issue/PR templates existed;
- main already had ACE community-growth and Phase 0 schema-check workflows;
- issue comments already contain valuable architecture/progress evidence, for example sequencing between WorkUnit, ResultManifest, node, and runner work;
- existing ACE correctly treats activity counts as signals rather than success objectives.

## Architecture decision

Add a **GitHub Reflex Observatory** that complements the repository-structure observatory in Issue #20.

GitHub supplies:

- sensors: issues, comments, PRs, reviews, reactions, workflow results, security state, branches, releases, community events;
- memory: durable public issue/PR/review history and workflow artifacts;
- actuators: later bounded issue/PR/review operations;
- guards: rulesets, branch protection, CODEOWNERS, required checks, independent review.

Core rule:

> GitHub engagement directs attention; independent evidence and verification decide acceptance.

## Smart algorithm

Use a typed temporal GitHub observation graph plus a homeostatic review-capacity controller.

Candidate actions are ranked from benefit, confidence, novelty, review capacity, cost, and risk. Repeated/correlated signals decay. Constitutional-risk changes cannot be self-authorized.

Initial deterministic rules:

- `GuardAutonomy`;
- `RequestIndependentReview`;
- `SynthesizeDiscussion`;
- `TriageStaleWork`;
- `RepairVerification`.

The algorithm caps autonomy at recommendation-only while the default branch lacks protection/rulesets.

## Artifacts added

- `docs/architecture/GITHUB_CAPABILITY_AND_EVENT_MAP.md`
- `docs/architecture/GITHUB_SELF_EVOLUTION_ENGINE.md`
- `schemas/github-observation-v0.1.schema.json`
- `tools/github_observatory.py`
- `tools/test_github_observatory.py`
- `.github/workflows/github-reflex-observatory.yml`

## Validation

Before repository commit, the deterministic policy tests passed locally and the Python source compiled successfully.

## Next steps

1. Review/merge the P0 observatory.
2. Run it on GitHub and inspect the real JSON artifact.
3. Merge its collaboration graph with Issue #20's structural repository graph.
4. Establish external branch/ruleset guards before Level 2 autonomy.
5. Add one rate-limited proposal actuator only after read-only recommendations demonstrate value.
6. Later use GitHub App webhooks for incremental event collection as repository activity grows.
