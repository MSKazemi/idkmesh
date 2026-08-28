# IDKMesh Current Priorities

**Snapshot date:** 2026-08-28

This file records the highest-leverage next actions after inspecting the current repository, open issues, open pull requests, CI state, and project roadmap.

For the repeatable method used to decide whether a repository change is actually an improvement, see [`REPOSITORY_IMPROVEMENT_LOOP.md`](REPOSITORY_IMPROVEMENT_LOOP.md).

The repository has reached an important transition point: the conceptual surface is already rich, Phase 0 contracts exist, community-growth experiments exist, and multiple implementation branches are open. The main risk now is continuing to add parallel theory and automation faster than the project converts them into protected, executable, independently verified evidence.

## Priority rule

Rank work by:

```text
Priority ~= (unblocked verified value + community leverage + safety leverage)
            / (dependency cost + reviewer attention + coordination risk)
```

The immediate objective is **not more documents or more issue count**. It is to create a protected path from a bounded Work Unit to an executable candidate, independent verification, reproducible evidence, and a contribution surface outsiders can extend.

---

# P0 — Protect the integration boundary

**Issue:** #35

Current `main` is not protected. The repository already contains write-capable GitHub automation and is developing self-evolution/community-growth controllers. Repository policy must become a real safety boundary before stronger automation is allowed.

Minimum target:

- require pull-request based integration for code/structural changes;
- block force-pushes and accidental branch deletion;
- require stable CI checks before merge;
- preserve an explicit maintainer emergency-recovery path;
- keep the rule that one autonomous actor cannot propose, approve, and merge the same protected change;
- document which low-risk deterministic automation may eventually bypass normal review, if any.

This is the highest safety priority because instructions inside agents are not an enforcement boundary.

**Current limitation:** configuring GitHub branch protection/rulesets requires repository settings/admin capability not exposed by the current repository-content workflow. Until it is configured, do not increase autonomous write/merge authority.

---

# P0 — Integrate the canonical local node

**PR:** #34  
**Acceptance:** #37  
**Parent issues:** #11, #16

PR #34 is the most important implementation branch because it turns the canonical Phase 0 Work Unit/ResultManifest contracts into a bounded local executable worker.

Current state observed:

- Phase 0 schema CI passes on the PR head;
- node CI passes on the PR head;
- the branch has diverged substantially from `main` and must be synchronized;
- GitHub currently reports the PR as non-mergeable;
- a real controlled Docker execution is still an explicit acceptance gate (#37).

Required sequence:

1. synchronize/rebase/merge current `main` into the PR branch and resolve any conflict deliberately;
2. rerun all schema + node CI on the updated head;
3. perform #37 on an explicitly controlled Docker host;
4. attach the requested sanitized runtime evidence;
5. perform independent review of sandbox/path-policy assumptions;
6. merge only after the above gates pass.

This is higher priority than adding more worker adapters. First establish one canonical executable path.

---

# P0 — Remove the duplicate node path

**PR:** #21  
**Replacement:** #34

PR #21 predates the canonical Phase 0 contracts and contains a competing Work Unit/result shape. PR #34 explicitly supersedes its core node-runtime path.

After #34 is integrated:

- close #21 as superseded for the node runtime;
- preserve any still-useful advisory Gemini-agent work as a small separate PR tied to #12 rather than merging the old private protocol;
- make it difficult for contributors to accidentally implement against two incompatible Work Unit contracts.

Reducing protocol ambiguity has higher value than preserving old implementation volume.

---

# P1 — Finish deterministic repository observability before self-rewriting

**PR:** #36  
**Issue:** #20

PR #36 introduces the proposal-first Repository Homeostasis Engine. It is currently draft, mergeable, and its Repository Homeostasis workflow has passed on the current PR head.

Recommended sequence:

1. establish the protected `main` boundary (#35);
2. review the workflow trust boundaries and write-capable ledger job;
3. ensure observations are deterministic/reproducible;
4. merge the proposal-only observatory;
5. use measured repository-health evidence before performing any structural migration;
6. keep file moves/deletions/semantic merges proposal-only until the project has strong independent verification.

The observatory should become a foundation for IDKGraph, not an autonomous cleanup bot.

---

# P1 — Complete the first end-to-end Verified Swarm Runner loop

**Milestone:** #16  
**Core work:** #4 and #5

Once #34 provides a canonical bounded worker, the next product milestone should be:

```text
bounded Work Unit
 -> 2+ isolated candidate workers
 -> candidate ResultManifests
 -> independent verifier
 -> Evidence Report
 -> human accept/reject/refine
```

The next implementation order should be:

1. independent validator + benchmark substrate (#5);
2. single-machine multi-worker coordinator/orchestrator (#4);
3. minimal Evidence Report and replayable run manifest;
4. one trivial heterogeneous second adapter;
5. only then broader external adapters/protocol integrations.

The central thesis cannot be tested until generation and verification are both executable.

---

# P1 — Turn ACE from activity accounting into descendant evidence

**Parent:** #10  
**Critical seed:** #25  
**Security seed:** #26  
**Community milestone:** #9

ACE already has a public Growth Ledger and five bootstrap Growth Seeds. Do **not** create a second large cohort merely to increase visible activity.

The next community-engine priorities are:

1. define deterministic parent -> seed -> descendant -> verified-descendant evidence links (#25);
2. threat-model the existing ACE GitHub workflow before stronger write capability (#26);
3. run real newcomer-path tests (#24);
4. measure whether Cohort 1 produces useful descendants and how much review attention they consume;
5. only then decide whether ACE should spawn another generation.

The growth engine should optimize:

```text
verified useful descendants
---------------------------
reviewer + maintainer attention
```

not issue count, comment count, commits, or stars.

---

# P1 — Publish one reproducible flagship experiment

**Issues:** #2, #13, #14, #29/#30

IDKMesh currently contains many strong hypotheses. The next credibility jump comes from one public, reproducible result.

The first flagship experiment should answer a bounded version of:

> Under a fixed budget, when does diversity + independent verification outperform simple worker replication?

Minimum arms:

- one capable baseline worker;
- replicated homogeneous workers;
- structurally diverse workers;
- diverse workers + independent verification.

Measure at least:

- verified success;
- hidden/independent test success;
- regressions/security failures;
- compute;
- latency;
- human review attention;
- pairwise error correlation.

The randomness-lab (#29) is useful insofar as it helps produce this evidence; it should not become a disconnected simulator framework before the real local worker/verifier path exists.

---

# P2 — Interoperability, ProjectManifest/DomainPack, and larger-scale simulation

Important, but do not let these block the first verified local loop:

- #17 A2A/MCP semantic mapping;
- #6 ProjectManifest/DomainPack interfaces;
- #31 large randomized scheduling simulations;
- #32 evolutionary orchestration;
- #1 10–20 laptop experiment.

These become much more valuable after the local runner + verifier + evidence schema are exercised by real tasks.

---

# What not to do now

Until the P0/P1 gates above move forward, avoid spending the main project attention on:

- additional grand-architecture documents without executable implications;
- new autonomous write/merge agents;
- blockchain/token mechanisms;
- a global scheduler;
- million-node implementation claims;
- many additional Growth Seeds without review capacity/evidence;
- additional competing Work Unit/result protocols;
- evolutionary policy promotion directly into production;
- social-growth metrics optimized independently of verified contribution.

---

# Recommended execution order

```text
1. Protect main (#35)
        |
2. Synchronize + validate PR #34
        |
3. Run Docker acceptance (#37)
        |
4. Merge canonical local node
        |
5. Retire/split obsolete PR #21
        |
6. Merge proposal-only repository observatory (#36) after safety review
        |
7. Build independent validator (#5)
        |
8. Build multi-worker local orchestrator (#4)
        |
9. Produce first complete Evidence Report / replayable swarm run (#16)
        |
10. Run flagship diversity + verification experiment (#2/#30)
        |
11. Use its evidence to update scheduler/randomness/community policies
```

In parallel, community contributors can work on #24–#28, but Cohort 2 should remain gated on actual descendant evidence and review capacity.

---

# Current project bottleneck

The repository is no longer bottlenecked by lack of ideas.

It is bottlenecked by the conversion:

```text
idea
 -> canonical contract
 -> protected integration
 -> executable implementation
 -> independent verification
 -> reproducible evidence
 -> outsider contribution
 -> measured descendant value
```

The next iteration should therefore maximize **evidence produced per unit of new complexity**.
