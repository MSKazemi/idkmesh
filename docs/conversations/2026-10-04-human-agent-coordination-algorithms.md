# Human–agent collaboration, duplicate work, recovery, dependencies, and routing

**Date:** 2026-10-04, Europe/Rome  
**Inspected main:** `52cbf2992eca8908d0b9fac9c0d3c5b8ca4ebbe8`  
**Artifact:** [coordination algorithm proposal](../planning/HUMAN_AGENT_COORDINATION_ALGORITHMS_2026-10-04.md)

## Project owner's questions and requirements

Preserved user request:

> This will be platform for collabrative work between the agents and humans ?
> How we will be sure that same jobs does not done by 100 agnets and human? Maybe more than one can be acceptable to select the best one ? Maybe bit 50 for example wasiting the time and energies? which algorithm you suggest for this ? if some agent or human do not answer or done in accaptable time what we will do?
> How it control dependecy of the different tasks to gethre? which method?
> How it evaluate the jobs tasks effort to use small models for simple and hard bigger?
> These are very importnat questions you need to think one by one answer in best possible way - you need to check the math - economic - physic - biological algorithms - soscity - ... to find the best solution and alorithms for each of the questions of this repo

Standing requirement: inspect the current repository before work and preserve substantive results there.

## Assistant's answer and proposed interpretation

IDKMesh's intended product is human–agent collaboration. The current repository has executable contracts, routing, local idempotency, candidate/verification separation, provider-specific dispatch controls, and research harnesses. It is not yet a completed production multi-user coordination platform.

Recommendations:

1. Give each logical task a shared canonical identity across humans and all connectors. Resolve known duplicate issues to that identity; use semantic matching as advisory triage only.
2. Use an atomic admission transaction, one primary implementation slot by default, and separate execution/request bindings. Actor/provider/event identity must not create an extra ownership slot.
3. Lease ownership and enforce slot-specific monotonic fencing epochs at canonical submission/write boundaries. Expired workers cannot replace their successors' evidence.
4. Keep execution occupancy separate from ownership. Unknown provider-create outcomes or unconfirmed termination retain resource reservations; reassignment cannot bypass concurrency caps.
5. Permit two, exceptionally three, competing candidates under an explicit pilot policy, lifetime attempt budget, fixed acceptance procedure, and declared reason. Favor complementary roles and separate tasks over repetitive generation.
6. Reassign stalled work through acknowledgement/liveness/progress/hard deadlines, provider reconciliation, cancellation, validated checkpoints, and new attempt identities. Human check-ins use agreed availability/grace windows.
7. Reuse the WorkUnit `requires` DAG, reject cycles, bind dependency artifacts/revisions, and dispatch only ready work. Default Git prerequisites require integrated evidence; candidate-stack pipelines require explicit policy.
8. Use critical-path/HEFT-inspired priority and capability-filtered power-of-two placement where appropriate. These heuristics do not supply ownership correctness.
9. Reuse T0–T4 capability floors and human gates. Estimate effort, ambiguity, coupling, runtime, risk, and verification cost separately; use the smallest eligible capable lane, categorized escalation, and later observed-data shadow learning.
10. Keep project-funded compute at zero. Treat quota, CI, donor resources, energy, and review time as separate scarce resources; pause generation under verification saturation.
11. Treat Contract Net, bandits, stigmergy, Physarum, evolutionary search, control theory, and commons governance as scoped mechanisms/inspiration. Keep them only when measured evidence supports their relevant role.
12. Preserve worker claims, verifier evidence, and human integration as separate authorities. An economic score or automatic reviewer cannot select/merge a canonical winner.

No universal optimum is claimed. Near-term correctness depends on ordinary transactional/distributed-systems controls; adaptive placement is a later comparison, not a substitute.

## Research and mathematical checks

Primary research/documentation was retrieved for leases, external API idempotency, hedged requests, HEFT, power-of-two choices, RouteLLM/FrugalGPT, budgeted/contextual bandits, Little's queue relation, AIMD, Amdahl, Contract Net, ant systems, Physarum, and Ostrom's institutional analysis. Source links, transfer limits, and an inaccessible full ant-paper download are recorded in the proposal.

Python Decimal arithmetic at 60-digit precision checked the illustrative 1–50 candidate allocation models:

- independent per-worker success 0.6 with value 100 and cost 8 gives a toy optimum of three candidates;
- shared failure probability 0.25 and conditional success 0.8 gives a toy optimum of two and a 75% limiting success probability;
- independent 2% per-candidate false acceptance across 50 candidates gives a 63.58% chance of at least one false acceptance;
- serial fraction 0.2 gives ideal decomposed speedup about 4.63 with 50 workers;
- 12 daily candidate arrivals and four daily reviews create eight additional queued candidates per day.

These are assumption-explicit calculations, not observed IDKMesh worker outcomes or evidence that the recommended pilot cap is optimal.

## Decisions and remaining work

This turn preserves a **proposal**, not an accepted ADR or live algorithm change. Existing component issues retain ownership: C9 597, C10 598, C5 578, Product Spine 682, and second-project pilot 599. Existing routing and research owners retain model/allocation/evidence work. No implementation gate is closed by this documentation.

First implementation priority: the common logical-task claim transaction and its concurrent human/agent admission fixture. Durable provider reconciliation and fenced recovery follow before safe unattended multi-user operation can be promised.

## Repository artifacts and verification

The proposal is indexed from planning and the main docs index, linked as proposed work from the architecture map, and preserved in this conversation index. The sitemap is regenerated from complete history for the new documentation pages. Actual repository checks and their results are recorded in the accompanying pull request.

## Community impact and provenance

Visible ownership/blockers reduce duplicated effort. Realistic voluntary human check-ins, credit for partial/late work, contributor consent, and newcomer opportunity remain explicit. Donation does not buy authority or standing.

Prepared with ChatGPT/Codex, connected GitHub reads, primary-source web research, local repository inspection, and numerical calculations. Review here is agent/automated review; no independent human validation, live multi-user experiment, or learned-router performance result is represented.
