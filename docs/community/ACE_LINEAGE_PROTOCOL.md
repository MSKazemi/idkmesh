# ACE Lineage Protocol v0.1

**Status:** Experimental evidence format for ACE.  
**Related:** #10, #23, #25, #27, `COMMUNITY_GROWTH_ENGINE.md`, `docs/community/ACE_GITHUB_CONSTRAINED_EVOLUTION.md`.

ACE cannot learn from community growth until it can distinguish **activity** from a **verified descendant of earlier useful work**. This document defines the smallest GitHub-native record needed to represent that lineage without adding a database.

The intended chain is:

```text
verified parent -> Growth Seed -> candidate descendant -> verification -> verified descendant
```

A verified descendant can later become a parent, so the records form a directed evidence graph.

## 1. Canonical record

Store one compact JSON object inside an HTML comment in an issue or pull-request body:

```md
<!-- ACE_LINEAGE
{
  "version": "0.1",
  "parent": {"repo": "MSKazemi/idkmesh", "kind": "issue", "number": 10},
  "seed": {"repo": "MSKazemi/idkmesh", "kind": "issue", "number": 25},
  "descendant": {"repo": "MSKazemi/idkmesh", "kind": "pr", "number": 40},
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

The earlier useful artifact/event whose downstream effect is being tested. A parent is **not automatically verified merely because it exists**. ACE metrics should count it as an eligible verified parent only when the surrounding project evidence says it passed the relevant verification policy.

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
- `merged` — integrated, but not necessarily independently verified as a useful descendant;
- `verified` — explicitly accepted as descendant evidence by a verification mechanism;
- `rejected` — evaluated and not accepted as useful descendant evidence.

`merged != verified` is deliberate. Popularity, existence, a closed issue, a commit, or a merge alone must never silently become ACE fitness.

## 3. Verification object

A verified record SHOULD include a `verification` object:

```json
{
  "method": "tests",
  "evidence_refs": ["pr:40", "workflow-run:123456"],
  "verified_at": "2026-08-30T12:00:00Z",
  "verifier": "github:reviewer-login"
}
```

Allowed v0 methods are `label`, `tests`, `review`, `reproduction`, and `manual`. More rigorous domain-specific verification can be introduced later.

A `verified` record without inspectable evidence should be treated as lower-confidence evidence by future policy layers.

## 4. Stable references

References use repository + artifact kind + identifier, for example:

```text
MSKazemi/idkmesh#issue:25
MSKazemi/idkmesh#pr:40
MSKazemi/idkmesh#commit:b808e1b14c93175b27fca9170f26396ea7085014
```

Implementations SHOULD normalize references this way internally. This makes deduplication deterministic and allows future cross-repository ACE experiments.

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

## 6. Examples

These examples demonstrate syntax and evidence states. They MUST NOT be interpreted as retrospective claims that an existing artifact is already verified unless the record itself says `status: verified` and supplies evidence.

### Example A — current candidate relationship

Issue #10 is the parent community-engine objective; #25 is a bounded measurement seed; PR #40 is related measurement infrastructure. At this stage it is only candidate evidence for the broader lineage mechanism:

```json
{
  "version": "0.1",
  "parent": {"repo": "MSKazemi/idkmesh", "kind": "issue", "number": 10},
  "seed": {"repo": "MSKazemi/idkmesh", "kind": "issue", "number": 25},
  "descendant": {"repo": "MSKazemi/idkmesh", "kind": "pr", "number": 40},
  "descendant_type": "measure",
  "status": "candidate",
  "recorded_at": "2026-08-28T14:30:00Z",
  "metadata": {"note": "illustrates candidate state; not verified lineage"}
}
```

### Example B — hypothetical verified reproduction

```json
{
  "version": "0.1",
  "parent": {"repo": "MSKazemi/idkmesh", "kind": "pr", "number": 40},
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

### Example C — rejected descendant

```json
{
  "version": "0.1",
  "parent": {"repo": "MSKazemi/idkmesh", "kind": "issue", "number": 10},
  "seed": {"repo": "MSKazemi/idkmesh", "kind": "issue", "number": 27},
  "descendant": {"repo": "MSKazemi/idkmesh", "kind": "pr", "number": 70},
  "descendant_type": "measure",
  "status": "rejected",
  "recorded_at": "2026-09-05T08:00:00Z",
  "verification": {
    "method": "tests",
    "evidence_refs": ["workflow-run:112233"],
    "verified_at": "2026-09-05T09:00:00Z",
    "verifier": "github:reviewer"
  }
}
```

Rejected evidence is useful: an evolutionary system should learn from failed descendants instead of erasing them.

## 7. Computing community reproduction

For a window `W`, let:

- `P_W` be unique eligible verified parents whose reproduction opportunity is observed in the window;
- `D_W` be unique descendants linked to those parents whose lineage status becomes `verified` within the measurement policy.

Then:

```text
R_community(W) = |D_W| / |P_W|
```

Important constraints:

1. Deduplicate by normalized artifact reference; duplicated comments/blocks do not create extra descendants.
2. A descendant linked to multiple parents may require fractional or attribution-aware accounting later. v0 should expose the ambiguity rather than double-count silently.
3. Stars, forks, comments, commits, issues, and PRs are observations only; none are automatically `D_W`.
4. `R_community > 1` is not sufficient for health. ACE must still apply review-capacity, security, conduct, and quality gates.

## 8. Why this stays small

The protocol is deliberately an evidence edge, not a community database. GitHub remains the durable event/artifact store. A future observer can scan these blocks, validate them, construct the lineage graph, and calculate reproduction metrics while making very few public writes.

That preserves the ACE principle:

```text
many observations -> one quiet state update -> very few bounded actions
```
