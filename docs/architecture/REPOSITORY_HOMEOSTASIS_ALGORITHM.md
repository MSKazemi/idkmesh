# Repository Homeostasis Algorithm (RHE)

Date: 2026-08-28  
Status: experimental / proposal-only  
Related: issue #20 and `SELF_EVOLVING_REPOSITORY.md`

## Decision

IDKMesh should **restructure progressively**, but it should not periodically reshuffle the repository just because a fixed number of commits occurred.

The repository should behave more like a homeostatic system:

1. observe structural health continuously;
2. accumulate structural pressure as new files, links, research tracks, and code appear;
3. enter a structural evolution epoch only when enough change or pressure has accumulated;
4. generate bounded restructuring candidates;
5. evaluate candidates before changing canonical structure;
6. execute structural changes only in a branch / pull request;
7. measure whether an accepted restructure actually improved repository health;
8. learn which rewrite policies are useful and which create churn.

The objective is **stable adaptability**, not maximum reorganization.

---

## 1. State model

At iteration `t` define repository state

`R_t = (F_t, G_t, I_t, C_t, H_t)`

where:

- `F_t` = files/directories and their sizes/types;
- `G_t` = documentation/task/evidence/link graph;
- `I_t` = issues, decisions, Work Units, and active milestones;
- `C_t` = recent change history;
- `H_t` = measured structural-health vector.

The first deterministic health vector is

`H = (root_pressure, broken_links, orphan_ratio, oversized_docs, directory_pressure)`.

Later versions should add semantic duplication, concept consistency, change coupling, dependency centrality, navigation distance, provenance coverage, and newcomer activation cost.

---

## 2. Structural pressure

RHE v0 computes a diagnostic pressure score in `[0,100]`:

`P = 100 * (`
`  0.35 * RootPressure`
`+ 0.25 * BrokenLinkPressure`
`+ 0.20 * OrphanPressure`
`+ 0.10 * OversizedDocumentPressure`
`+ 0.10 * DirectoryPressure`
`)`.

This score is a trigger signal, **not a definition of correctness**.

A proposal that lowers `P` can still be rejected if it damages discoverability, history, semantics, security, reviewability, or contributor experience.

---

## 3. Evolution epochs

A full restructuring analysis becomes due when **any** configured epoch trigger fires:

- at least `25` commits since the last accepted structural baseline;
- at least `15` distinct files changed since that baseline;
- structural pressure reaches `60/100`.

The architecture uses a high/low band:

- `P_high = 60` — structural intervention can be proposed;
- `P_low = 35` — healthy/reset region.

This is hysteresis. A future automated controller should not repeatedly restructure around one exact boundary. Once restructuring starts, the system should not trigger another structural epoch until pressure has fallen into the lower band or a new epoch budget has accumulated.

The exact values are experimental configuration, not universal constants.

---

## 4. Typed rewrite operators

RHE should never ask an unrestricted model to "clean up the repository." It proposes typed transformations with preconditions and postconditions.

Initial rules:

### `MoveRootDocument`

Use when a non-entrypoint document has accumulated at repository root and has a clear semantic home.

Required postconditions:

- all inbound relative links repaired;
- README/navigation still reaches the document;
- Git history preserved;
- no duplicate canonical copy remains.

### `GenerateIndex`

Create a directory index when a module has many important artifacts but no stable navigation entrypoint.

### `ReviewCrowdedDirectory`

Propose submodules when one directory exceeds a configured file-count threshold. File count alone never authorizes a split.

### `ReviewOversizedDocument`

Look for coherent conceptual subgraphs inside a large document. Size alone never authorizes a split.

### `ArchiveSuperseded`

Allowed only when an explicit successor exists and active references have been redirected. History is retained.

### `PromoteRepeatedFinding`

Turn repeatedly copied material into a canonical specification/decision/foundation document plus references.

### `MergeDuplicateConcepts`

High-risk semantic operation. It requires evidence that definitions are compatible and must retain conflicting evidence instead of deleting it.

---

## 5. Candidate evaluation

For candidate restructuring plan `a`, estimate

`Gain(a) = HealthImprovement(a) - MigrationCost(a) - ChurnRisk(a) - SemanticRisk(a)`.

A more useful multi-objective representation is:

`Q(a) = (`
`  broken_links_delta,`
`  orphan_delta,`
`  navigation_delta,`
`  root_pressure_delta,`
`  modularity_delta,`
`  links_to_rewrite,`
`  files_moved,`
`  reviewer_effort,`
`  semantic_risk`
`)`.

Candidates should be Pareto-ranked rather than collapsed immediately into one magic score.

A large restructure that improves one structural metric but rewrites dozens of links may lose to three small independently reviewable migrations.

---

## 6. Safety invariants

RHE v0 is **Level 1: recommend/propose**.

It cannot:

- move files automatically;
- delete files automatically;
- merge its own pull requests;
- modify security/governance policy as part of a generic cleanup;
- merge semantically similar documents automatically;
- hide or delete contradictory/negative evidence;
- change tests merely to make its restructure pass.

Every structural migration must be reversible and reviewed independently.

The write-capable GitHub Actions job never executes pull-request code.

---

## 7. Proposed IDKMesh target topology

The repository currently has a growing number of substantial research/architecture documents at root. That is manageable at small size but becomes expensive for newcomers and automation as the project grows.

The target should be a **thin root and typed subtrees**.

Suggested long-term shape:

```text
/
  README.md
  LICENSE
  CONTRIBUTING.md
  COMMUNITY.md
  CODE_OF_CONDUCT.md
  SECURITY.md
  SUPPORT.md
  GOVERNANCE.md
  MAINTAINERS.md
  ROADMAP.md
  PROJECT_RULES.md
  IDKIPS.md

  src/                    # installable product when Phase 1 begins
  tests/
  schemas/
  examples/
  experiments/
  tools/
  idkips/

  docs/
    foundations/          # vision, goals, scientific/math foundations, core questions
    architecture/         # system architecture and evolution mechanisms
    research/             # active research programs and experiment roadmaps
    specifications/       # protocol/contract specifications
    community/            # contributor/community mechanisms
    security/             # threat models and security architecture
    decisions/            # ADRs and decision history
    findings/             # research/landscape findings
    audits/                # point-in-time audits
    conversations/        # public-safe project conversation archive
```

This is a **candidate topology**, not an immediate bulk-move instruction.

The first structural migration should move only a small coherent set of root research/foundation documents, repair links, add `docs/foundations/README.md`, and measure the navigation effect.

---

## 8. Evolution algorithm

```text
on every repository-relevant change:
    H <- deterministic structural observation
    P <- structural pressure(H)
    update epoch counters

    if not epoch_due(P, commits, changed_files):
        publish report only
        stop

    anomalies <- deterministic findings(H)
    candidates <- typed_rewrite_rules(anomalies)

    for candidate in candidates:
        estimate deltas and migration cost
        reject if hard invariant would be violated

    frontier <- pareto_rank(candidates)

    if frontier is empty:
        record healthy/no-action epoch
        stop

    update one Repository Structure Ledger

    human/independent agent selects a bounded plan
    execute plan in branch
    rerun observatory + tests + link checks

    if verified and independently approved:
        merge
        record new structural baseline

    after observation window:
        compare before/after health and contributor friction
        update rewrite-policy evidence
```

---

## 9. Why not restructure every N iterations?

A fixed-period cleanup causes structural oscillation and unnecessary link churn.

Two repositories can have the same number of new commits while one remains perfectly organized and the other accumulates severe fragmentation.

Therefore iteration count should trigger **observation**, while measured structural pressure determines whether restructuring is justified.

This combines:

- control theory: feedback + hysteresis;
- graph theory: connectivity/modularity;
- Minimum Description Length: avoid both flat chaos and over-abstraction;
- biology: homeostatic target ranges;
- evolutionary search: compare alternative structures;
- software safety: branch, verify, review, rollback.

---

## 10. Next stages

### RHE v0 — now

- deterministic scan;
- root pressure;
- internal-link validation;
- orphan warnings;
- oversized/crowded-module signals;
- epoch decision;
- proposal-only GitHub ledger.

### RHE v0.2

- stable document/heading IDs;
- full IDKGraph export;
- link-fragment validation;
- change-coupling graph from Git history;
- generated indexes;
- baseline before/after comparison.

### RHE v0.3

- semantic candidate generation with confidence/provenance;
- duplicate/concept detection;
- simulated alternative directory structures;
- Pareto comparison of restructure plans.

### RHE v1

Allow auto-merge only for proven deterministic, low-risk maintenance such as generated indexes or mechanical link repair under branch protection. Structural/semantic moves remain independently approved.
