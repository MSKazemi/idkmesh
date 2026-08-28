# ACE Lineage Protocol v0.1

**Status:** Experimental evidence format for ACE.  
**Related:** #10, #23, #25, #27, PR #40, PR #44, `COMMUNITY_GROWTH_ENGINE.md`, `docs/community/ACE_GITHUB_CONSTRAINED_EVOLUTION.md`.

ACE cannot learn from community growth until it can distinguish **activity** from a **verified descendant of earlier useful work**. This document defines the smallest GitHub-native record needed to represent that lineage without adding a database.

The intended chain is:

```text
verified parent -> Growth Seed -> candidate descendant -> verification -> verified descendant
```

A verified descendant can later become a parent, so the records form a directed evidence graph.

This protocol deliberately defines **lineage evidence**, not a complete community database and not an autonomous actuator.

## 1. Canonical record

Store one compact JSON object inside an HTML comment in an issue or pull-request body:

```md
<!-- ACE_LINEAGE
{
  "version": "0.1",
  "parent": {"repo": "MSKazemi/idkmesh", "kind": "issue", "number": 10},
  "seed": {"repo": "MSKazemi/idkmesh", "kind": "issue", "number": 25},
  "descendant": {"repo": "MSKazemi/idkmesh", "kind": "pr", "number": 48},
  "descendant_type": "measure",
  "status": "candidate",
  "recorded_at": "2026-08-28T14:30:00Z"
}
ACE_LINEAGE -->
```

The machine-readable schema is [`schemas/ace-lineage-v0.1.schema.json`](../../schemas/ace-lineage-v0.1.schema.json).

Multiple `ACE_LINEAGE` blocks MAY appear in one artifact. This permits one parent to have several descendants without a central mutable table.

## 2. Required semantics

### `parent`

The earlier useful artifact/event whose downstream effect is being tested. A parent is **not automatically verified merely because it exists**. ACE metrics count it as an eligible verified parent only when the relevant project verification policy says it qualifies.

### `seed`

The bounded opportunity deliberately left by or derived from the parent. In ACE v0 this is normally a GitHub issue carrying the `growth-seed` label and an `ACE_SEED` marker.

### `descendant`

The issue, pull request, or commit produced downstream. Existence is activity; it is not proof of usefulness.

### `descendant_type`

One of the current ACE seed families:

- `reproduce`
- `extend`
- `challenge`
- `explain`
- `translate`
- `secure`
- `measure`
- `connect`
- `review`
- `onboard`
- `other`

### `status`

The evidence state:

- `candidate` — work exists but has not passed the project verification gate;
- `merged` — integrated, but not yet counted as verified useful descendant evidence;
- `verified` — explicitly accepted as descendant evidence by a verification mechanism;
- `rejected` — evaluated and not accepted as useful descendant evidence.

`merged != verified` is deliberate. Popularity, existence, a closed issue, a commit, or a merge alone must never silently become ACE fitness.

## 3. Verification object

A record with `status: verified` **MUST** include a schema-valid `verification` object:

```json
{
  "method": "review",
  "evidence_refs": ["pr:61", "workflow-run:987654"],
  "verified_at": "2026-09-04T11:20:00Z",
  "verifier": "github:independent-reviewer"
}
```

Allowed v0 methods are `label`, `tests`, `review`, `reproduction`, and `manual`. More rigorous domain-specific verification can be introduced later.

The verification object is an **evidence pointer**, not authority to merge or change canonical project state. A future observer should retain the verifier identity/provenance and should detect obvious self-verification when actor identity is available.

For higher-risk descendants, IDKMesh's broader independent-verification rules still apply. ACE lineage must never weaken Work Unit, security, governance, or integration policy.

## 4. Stable references

References use repository + artifact kind + identifier, for example:

```text
MSKazemi/idkmesh#issue:25
MSKazemi/idkmesh#pr:48
MSKazemi/idkmesh#commit:b808e1b14c93175b27fca9170f26396ea7085014
```

Implementations SHOULD normalize references this way internally. This makes deduplication deterministic and allows future cross-repository ACE experiments.

GitHub URLs are useful provenance, but URL text is not the identity key. The typed normalized reference is.

## 5. Optional fields

The format intentionally keeps optional measurement fields outside the identity of the lineage edge:

```json
{
  "actor": "github:example-contributor",
  "reviewer_minutes": 18,
  "lineage_id": "optional-stable-id",
  "metadata": {
    "cohort": "bootstrap-1"
  }
}
```

`reviewer_minutes` is an estimate of scarce human attention, not a productivity score for a person.

## 6. Concrete examples

These examples demonstrate syntax and current evidence states. They are not claims of verified usefulness unless `status` is explicitly `verified` with inspectable evidence.

### Example A — #25 candidate descendant

Issue #10 contains the repository-driven community-engine workstream, #25 is the bounded lineage-measurement Growth Seed, and PR #48 is the current implementation candidate for #25:

```json
{
  "version": "0.1",
  "parent": {"repo": "MSKazemi/idkmesh", "kind": "issue", "number": 10},
  "seed": {"repo": "MSKazemi/idkmesh", "kind": "issue", "number": 25},
  "descendant": {"repo": "MSKazemi/idkmesh", "kind": "pr", "number": 48},
  "descendant_type": "measure",
  "status": "candidate",
  "recorded_at": "2026-08-28T14:30:00Z",
  "metadata": {"cohort": "bootstrap-1"}
}
```

### Example B — #27 candidate descendant

Issue #27 is the population-simulator Growth Seed and PR #44 is its current implementation candidate:

```json
{
  "version": "0.1",
  "parent": {"repo": "MSKazemi/idkmesh", "kind": "issue", "number": 10},
  "seed": {"repo": "MSKazemi/idkmesh", "kind": "issue", "number": 27},
  "descendant": {"repo": "MSKazemi/idkmesh", "kind": "pr", "number": 44},
  "descendant_type": "measure",
  "status": "candidate",
  "recorded_at": "2026-08-28T14:30:00Z",
  "metadata": {"cohort": "bootstrap-1"}
}
```

The two candidate examples are intentionally separate. PR #48 should not duplicate the simulator implementation already proposed in PR #44.

### Example C — hypothetical verified second generation

```json
{
  "version": "0.1",
  "parent": {"repo": "MSKazemi/idkmesh", "kind": "pr", "number": 48},
  "seed": {"repo": "MSKazemi/idkmesh", "kind": "issue", "number": 52},
  "descendant": {"repo": "MSKazemi/idkmesh", "kind": "pr", "number": 61},
  "descendant_type": "reproduce",
  "status": "verified",
  "recorded_at": "2026-09-04T10:00:00Z",
  "verification": {
    "method": "reproduction",
    "evidence_refs": ["pr:61", "workflow-run:987654"],
    "verified_at": "2026-09-04T11:20:00Z",
    "verifier": "github:independent-reviewer"
  },
  "reviewer_minutes": 14
}
```

This example is intentionally hypothetical; it shows how a descendant can later become a parent.

Rejected lineage evidence should also be retained rather than erased so later policy experiments can learn from failed descendants.

## 7. Computing community reproduction without survivorship bias

A lineage edge exists only after a candidate descendant exists. Therefore **lineage edges alone must not define the denominator** of `R_community(W)`. If they did, parents that produce zero descendants would disappear from the dataset and reproduction would be biased upward.

The denominator must come from an independent inventory of eligible verified parents / Growth Seeds. During Bootstrap Cohort 1, PR #40's cohort observer is a natural source. A future unified IDKGraph can provide the same inventory.

For observation time `t` and reproduction window `W`, define:

- `P_W(t)` = unique eligible verified parents whose observation window has matured by `t`;
- `D_W(t)` = unique descendants attributed to those parents that become `verified` within their allowed reproduction window.

Then:

```text
R_community(W, t) = |D_W(t)| / |P_W(t)|
```

A parent whose window has not yet matured is **right-censored** and should not be treated as a zero merely because it is new.

Important constraints:

1. **Independent denominator inventory.** Parents with zero descendants remain visible and count once their observation window matures.
2. **Deduplicate by normalized artifact reference.** Repeated comments/blocks do not create extra descendants.
3. **No silent multi-parent double counting.** If one descendant plausibly has multiple parents, v0 should select one explicit primary attribution for the reproduction metric or mark the attribution ambiguous and exclude it from the scalar metric until reviewed. The richer graph may preserve all causal/support relationships.
4. **Activity is not descendant fitness.** Stars, forks, comments, commits, issues, PRs, and merges are observations only; none automatically become `D_W`.
5. **Verification time matters.** Use the transition to `verified`, not the time a candidate was first opened, for descendant fitness.
6. **Growth is capacity-constrained.** `R_community > 1` is not sufficient for health. ACE must still apply review-capacity, security, conduct, and quality gates.
7. **Preserve negative evidence.** Rejected descendants remain part of experiment history even though they do not count in `D_W`.

This gives ACE a defensible way to estimate reproduction without rewarding only the lineages that happened to succeed.

## 8. Relationship to the IDKGraph evidence model

The lineage protocol is intentionally small enough to map into the existing IDKGraph model rather than compete with it.

A future importer can represent:

- parent / seed / descendant artifacts as typed graph nodes;
- the lineage relation as a `derived_from`, `implements`, or future ACE-specific relation;
- the verification object as an evidence node plus `verifies` relation;
- timestamps and actor/tool identifiers as provenance;
- cohort and review-attention values as attributes/metrics.

Natural-language issue/PR text remains untrusted input. An `ACE_LINEAGE` block is structured metadata to validate, not executable instructions.

## 9. Why this stays small

GitHub remains the durable event/artifact store. A future observer can scan these blocks, validate them, join them to the independent parent/seed inventory, construct the lineage graph, and calculate reproduction metrics while making very few public writes.

That preserves the ACE principle:

```text
many observations -> one quiet state update -> very few bounded actions
```

No autonomous policy-selection or spawning authority should be enabled merely because this schema exists. The next step after review is to collect real lineage outcomes and test whether they are sufficiently reliable for generational policy experiments.
