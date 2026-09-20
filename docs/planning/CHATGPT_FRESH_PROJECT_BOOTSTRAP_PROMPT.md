# Fresh ChatGPT Project Bootstrap Prompt for IDKmesh

Paste the prompt below into a new ChatGPT Project after connecting GitHub access to `MSKazemi/idkmesh`.

```text
This is the fresh ChatGPT Project for IDKmesh.

Use the public GitHub repository MSKazemi/idkmesh as canonical durable project memory.

First read:
1. docs/planning/CHATGPT_PROJECT_MIGRATION_PACK_2026-09-19.md
2. docs/planning/CHATGPT_AUTOMATIONS_V3.yaml
3. AGENTS.md
4. PROJECT_RULES.md
5. docs/planning/REPOSITORY_IMPROVEMENT_LOOP.md
6. docs/planning/BRANCH_CONVERGENCE_POLICY.md

Then recreate the nine jobs in the canonical_v3 profile from CHATGPT_AUTOMATIONS_V3.yaml.

Requirements:
- use the exact job titles;
- use the exact schedules and timing modes;
- use Europe/Rome as project-local time where specified;
- use the full prompts from the YAML manifest;
- do not recreate the 34 legacy historical jobs;
- do not create duplicate jobs;
- preserve the global maximum of 3 open agent-authored implementation PRs and 1 per specialist role;
- never push directly to main;
- never self-approve;
- never count owner-controlled AI as independent human/external review;
- never weaken tests, CI, security controls, branch protections, or evidence gates;
- never commit secrets or real .env values;
- record substantive project outputs publicly in the GitHub repository.

Create them in this order:
Phase A:
1. IDKmesh Swarm Governor
2. IDKmesh PR Integrator
3. IDKmesh Reliability & Repository Health
4. IDKmesh Documentation & Paper Sync

Phase B:
5. IDKmesh Backend & Interoperability
6. IDKmesh Product & Developer Experience

Phase C:
7. IDKmesh Research & Standards Scout
8. IDKmesh Growth & Release
9. IDKmesh Weekly Deep Steward

After creation, list exactly the nine created job titles, cadence, timing mode, and next applicable schedule. Check for duplicates and report any mismatch against the YAML manifest before doing other project work.
```

## Recovery mode

If a future maintainer needs an old historical role for comparison or a bounded experiment, read the historical appendices in `CHATGPT_PROJECT_MIGRATION_PACK_2026-09-19.md`. Do not reactivate the entire historical swarm.
