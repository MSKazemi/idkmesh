# ACE Phase-B Activation Gate

**Status:** Experimental fail-closed contract.

ACE already has a community-growth loop, lineage work, cohort observation, security review, and a shadow generational controller. The missing safety boundary is an **external activation gate** that answers one question:

> Is the repository actually ready to allow the controller to leave shadow mode?

The answer must be derived from independent evidence, not from a local configuration flag inside the controller.

## Why this exists

A self-improving community system creates a dangerous temptation:

```text
algorithm looks promising -> enable actuation -> collect evidence later
```

ACE reverses that order:

```text
independent evidence
  -> verified lineage
  -> capacity health
  -> security review
  -> protected integration
  -> controller review
  -> activation gate
  -> only then may Phase B be considered
```

A controller cannot activate itself.

## Gate formula

Let the binary independent gates be:

- `O` = observer reviewed/accepted;
- `L` = lineage protocol reviewed/accepted;
- `S` = ACE security review accepted with no blocking finding;
- `C` = generational controller reviewed/accepted;
- `P` = protected integration boundary enforced;
- `D` = at least one real independently verified descendant exists;
- `K` = review-capacity state is readable, fresh, single-writer, and above the minimum threshold;
- `B` = public-write budget is at most one per generation;
- `F` = forbidden high-impact capabilities remain disabled.

Then v0 is deliberately conjunctive:

```text
Activation = O AND L AND S AND C AND P AND D AND K AND B AND F
```

This is not a weighted score. A high score in one dimension cannot compensate for a missing security or protection gate.

## Fail-closed semantics

`scripts/ace_activation_gate.py` rejects malformed or incomplete snapshots rather than guessing. A valid snapshot with any failed check returns:

```json
{
  "decision": "BLOCK",
  "activation_gate_passed": false,
  "required_controller_mode_if_blocked": "SHADOW"
}
```

A BLOCK result is not a project failure. It is the expected result whenever evidence or carrying capacity is insufficient.

## Independent components

### Observer

The observer supplies the eligible-parent/community-evidence inventory. PR #40 is the current candidate implementation.

### Lineage

The lineage layer distinguishes activity from descendant evidence and prevents survivorship bias. PR #48 is the current candidate implementation.

### Security

The security layer evaluates the metadata/write boundary, token permissions, fork/PR trust, state corruption, event storms, and future autonomy risks. PR #62 is the current candidate implementation for Growth Seed #26.

### Controller

The Phase-A controller computes evidence-only fitness, replicator-mutator strategy weights, and homeostatic capacity bias. PR #68 is the current canonical candidate.

### Protected integration

Repository files cannot substitute for actual GitHub branch protection/rulesets. PR #51 documents and enforces the fail-closed relationship to this external boundary, but an administrator must still configure the GitHub setting itself.

### Real descendant evidence

A merged PR, issue, star, comment, or claim is not automatically a verified descendant. At least one descendant must be independently verified under the accepted lineage/observer rules before the gate can pass.

### Review capacity

The capacity check requires all of:

- capacity state readable;
- one canonical writer/source of truth;
- snapshot fresh enough for the configured window;
- capacity at or above the configured minimum.

This prevents a stale or overloaded community from activating growth merely because older evidence looked healthy.

## Forbidden capabilities in v0

The gate blocks if any of the following are enabled:

- autonomous merge;
- governance/constitutional mutation;
- execution of untrusted contributor code in the privileged control plane;
- secrets access for the ACE actuator;
- mass-notification behavior.

These are intentionally outside the first Phase-B authority envelope.

## Current repository snapshot

The committed fixture `examples/community/ace-activation-gate-current.example.json` captures a point-in-time snapshot from **2026-08-28 around 14:55 UTC**.

At that moment the public ACE Growth Ledger (#23) reported approximately:

```text
Mode: CONSOLIDATE
Review-load proxy: 35.55
Capacity multiplier: 0.000
```

The observer (#40), lineage (#48), security (#62), controller (#68), and protected-integration (#51) paths were still review candidates rather than accepted dependencies, and the Bootstrap Cohort had no independently verified descendant evidence recorded by ACE.

Therefore the correct activation decision for that snapshot is:

```text
BLOCK
```

This fixture is **not** a claim that the repository will remain blocked. It is a reproducible record of why stronger autonomy was not justified at that point in time.

## Relationship to the controller

The gate is external to the controller on purpose.

```text
repository / observer / protection evidence
                |
                v
        ACE Activation Gate
                |
        activation_gate_passed
                |
                v
    Phase-A generational controller
                |
      shadow recommendation only
                |
      future separately reviewed adapter
```

A future GitHub integration may feed this boolean to the controller, but the controller must never infer or override it from raw activity.

## Next experiment

After the observer, lineage, security, controller, and protection paths are reviewed, generate a read-only activation snapshot from actual repository state and replay it through the gate.

If it remains BLOCK because review capacity or descendant evidence is insufficient, ACE should consolidate rather than manufacture activity to make the gate pass.

## Non-goals

This change does not:

- call GitHub APIs;
- create issues/comments/PRs;
- merge anything;
- change repository settings;
- enable Phase B;
- declare an open PR equivalent to accepted evidence;
- treat popularity as correctness.

## Related

- #10 repository-driven community engine
- #23 ACE Growth Ledger
- #25 / PR #48 lineage evidence
- #26 / PR #62 security review
- PR #40 Bootstrap Cohort observer
- PR #51 protected-integration guard
- #57 ACE v1 controller
- PR #68 ACE activity metabolism / Phase-A controller
- `COMMUNITY_GROWTH_ENGINE.md`
- `docs/community/ACE_GITHUB_CONSTRAINED_EVOLUTION.md`
