# ACE Phase-B Activation Gate

**Status:** Experimental, fail-closed, offline gate.  
**Authority:** none by itself.

ACE now has canonical observation, causal lineage, recoverable capacity, shadow policy, and privileged-workflow safety layers on `main`. The activation gate answers a separate question:

> **Is the repository actually allowed and evidenced well enough to leave shadow mode?**

A controller cannot activate itself.

## Conjunctive rule

Let:

- `O` = observer accepted;
- `L` = lineage protocol accepted;
- `S` = security boundary accepted;
- `C` = shadow controller accepted;
- `P` = protected integration boundary actually enforced;
- `D` = at least one real independently verified descendant exists;
- `K` = review-capacity state is readable, fresh, single-writer, and above threshold;
- `B` = public-write budget is at most one per generation;
- `F` = forbidden high-impact capabilities remain disabled.

Then:

```text
Activation = O AND L AND S AND C AND P AND D AND K AND B AND F
```

This is deliberately not a weighted score. Healthy capacity cannot compensate for missing protection. High activity cannot compensate for absent verified descendants. Model confidence cannot authorize GitHub writes.

## Canonical evidence stack

As of the current convergence:

```text
merged #106 cohort observer
  -> trusted bootstrap exposure / eligible-parent evidence

merged #48 causal lineage
  -> parent -> seed -> descendant receipts + verification evidence

merged #104 live-open-work capacity
  -> recoverable current integration/review pressure

merged #68 shadow controller
  -> R_community + strategy fitness + replicator-mutator policy

merged #98 safety/protected-integration workflow guards
  -> fail-closed metadata-plane authority boundary

this activation gate
  -> independent PASS / BLOCK before future Phase B
```

The gate does not replace GitHub rulesets, lineage verification, or the controller. It composes their evidence states.

## Current repository fixture

`examples/community/ace-activation-gate-current.example.json` is a point-in-time reproducible snapshot, not a live API collector.

The current fixture records:

```text
observer                 accepted (#106)
lineage                  accepted (#48)
security                 accepted (#98)
controller               accepted (#68)
integration protection   accepted (#35: main protected, required checks gate (3.11)/gate (3.13))
verified descendants     0
live capacity            ~0.913 (healthy against current 0.6 gate)
```

The capacity value is taken from the Bootstrap Cohort Observatory (#109), which reported at its snapshot:

```text
ACE review load: 3.3
ACE capacity: 0.912934227...
external participants: 0
bootstrap verified descendant PRs: 0
recommendation: HOLD_COHORT_1
```

This is an important control-system result: consolidation can recover capacity, but recovered capacity does **not** create authority or evidence.

Therefore the expected decision remains:

```text
BLOCK
```

with the single meaningful current blocker:

```text
real_verified_descendant_evidence
```

`review_capacity` should **not** be a blocker in this fixture.

## Fail-closed semantics

`scripts/ace_activation_gate.py` rejects malformed or incomplete snapshots rather than guessing. A valid snapshot with any failed check returns:

```json
{
  "decision": "BLOCK",
  "activation_gate_passed": false,
  "required_controller_mode_if_blocked": "SHADOW"
}
```

A BLOCK result is expected whenever one independent prerequisite is missing.

## Review capacity

The gate consumes a normalized capacity value in `[0,1]`; it does not calculate repository pressure itself.

The canonical source is now #104's recoverable `live-open-work-v1` model rather than the obsolete cumulative historical event-load scalar. Future snapshot builders should bind the value to a timestamp/source and keep the capacity computation independently inspectable.

A capacity check passes only when:

- the source is readable;
- there is one authoritative state source;
- the snapshot is fresh enough;
- `capacity >= minimum_capacity`.

## Real descendant evidence

Stars, comments, commits, issue volume, merged unrelated PRs, and owner-driven implementation do not satisfy `D`.

At least one descendant must be independently verified under the accepted observer/lineage semantics. The current cohort observatory reports zero external participants and zero bootstrap verified descendants, so this gate remains blocked even though the infrastructure PRs themselves are merged.

## Integration protection

Repository files cannot substitute for actual GitHub branch protection/rulesets, so this component is read from public branch metadata, never from documentation.

As of 2026-08-29 that metadata reports `main` as protected, with `gate (3.11)` and `gate (3.13)` required, force-pushes and deletions denied, and conversation resolution required. The repository-admin procedure tracked by #35 is therefore complete, and the `integration_protection` component reads `accepted`.

This component is re-derived from live metadata whenever the fixture is refreshed; it is not a permanent grant. If protection were removed, the component would return to `blocked` and the gate would fail closed for a second, independent reason.

The explicit ACE actuation opt-in introduced by #98 is an additional authority gate; neither it nor branch protection is by itself an activation authority.

## Forbidden capabilities in v0

The gate blocks if any of these are enabled:

- autonomous merge;
- governance/constitutional mutation;
- execution of untrusted contributor code in the privileged control plane;
- secrets access for the ACE actuator;
- mass-notification behavior.

These remain outside the first Phase-B authority envelope.

## Tests

`tests/test_ace_activation_gate.py` covers:

- current fixture remains BLOCK;
- current recovered capacity is **not** itself a blocker;
- recovered/maximal capacity cannot bypass missing protection or descendants;
- complete evidence can produce PASS in a synthetic fixture;
- pending component blocks;
- independent descendant verification is required;
- low/stale capacity blocks;
- public-write budget > 1 blocks;
- forbidden capabilities block;
- malformed/missing component fails closed;
- fixed input is deterministic.

## Non-goals

This change does not:

- call GitHub APIs;
- modify repository settings;
- create issues/comments/PRs;
- merge anything;
- enable Phase B;
- infer protection from documentation;
- infer descendants from raw activity;
- treat a healthy capacity score as authorization.

## Next step

Integrate this gate as an offline canonical contract. Branch protection is now configured and verified, so the single remaining blocker is real external cohort evidence: at least one independently verified descendant. Only after every independent check passes should a separately reviewed metadata adapter even be considered.

## Related

- #10 repository-driven community engine
- #23 ACE Growth Ledger
- #35 protected `main` (completed 2026-08-28)
- #48 causal lineage
- #57 ACE v1 controller
- #68 shadow controller
- #89 activation-gate PR
- #98 converged security/protection guards
- #104 recoverable capacity
- #106 cohort observer
- #109 Bootstrap Cohort Observatory
