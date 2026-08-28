# Protected `main` Integration Boundary

**Status:** Required P0 repository-admin configuration  
**Tracking issue:** #35

IDKMesh uses GitHub as both its public collaboration substrate and, increasingly, an execution/control surface for deterministic automation and bounded agents. Instructions inside those agents are not a security boundary. The canonical `main` branch therefore needs an explicit GitHub ruleset or branch-protection policy before autonomous write authority is increased.

## Safety invariant

> No autonomous actor may propose, approve, and merge the same protected change by itself.

A successful worker run, agent proposal, community-growth event, or repository-homeostasis proposal is evidence for review. It is not authority to mutate canonical state.

## Two-gate ACE autonomy rule

A GitHub branch response with `protected: true` is **necessary but not sufficient** to prove that the intended IDKMesh integration boundary is configured. A weak or partial ruleset could still set that bit.

ACE therefore requires two separate conditions before its bounded reproductive actuator becomes eligible:

```text
GitHub reports main protected
AND
repository variable ACE_AUTONOMOUS_ACTUATION_ENABLED == "true"
```

The repository variable is an explicit post-verification opt-in. It must remain unset/false while protection is absent, incomplete, untested, or under repair.

**Do not set the variable merely to make the workflow enter GROW/EXPLORE.** Set it only after the concrete protection behavior below has been configured and tested.

## Current bootstrap target

Configure a branch ruleset for the repository default branch, currently `main`, with these minimum properties:

1. **Require pull requests before merge** for code, workflow, schema, protocol, security, governance, and structural repository changes.
2. **Block force pushes.**
3. **Block branch deletion** except through an explicit maintainer recovery procedure.
4. **Require stable CI/status checks** before merge once those checks are present and reliable.
5. **Require independent review** for medium/high-risk security, workflow, governance, protocol, schema, and self-evolution changes.
6. **Do not allow automation to bypass the ruleset by default.** Any future bypass must be narrowly scoped, documented, deterministic, low-risk, and independently audited.
7. **Preserve a maintainer emergency-recovery path**, but treat it as exceptional rather than the normal integration workflow.

## Candidate required checks

Enable only checks that are stable on `main`; an unreliable required check becomes its own availability risk.

Initial candidates:

- `Phase 0 schema check`;
- `ACE safety contract` for privileged ACE workflow changes;
- `IDKMesh Node CI` after the canonical node lands;
- deterministic repository-observatory / homeostasis checks after that workflow is integrated and stable;
- future independent verifier/unit/security checks used by the Verified Swarm Runner.

Do not make a check required merely because it exists. Require it when its semantics are understood, it is deterministic enough for the protected path, and maintainers know how to recover from infrastructure failure without silently bypassing quality gates.

## Suggested GitHub UI procedure

Repository administrator:

1. Open **Settings** for `MSKazemi/idkmesh`.
2. Open **Rules** / **Rulesets** (or Branch protection if rulesets are unavailable for the account/repository configuration).
3. Create a ruleset targeting the default branch `main`.
4. Enable pull-request-based integration.
5. Disable force pushes and deletion.
6. Add stable required status checks as they become suitable.
7. Configure review requirements appropriate to the current small bootstrap team; do not create an impossible approval requirement while only one maintainer exists.
8. Avoid broad bypass actors. Keep emergency maintainer bypass narrow and auditable if one is necessary.
9. Save/enforce the ruleset.
10. Verify the concrete behaviors listed in **Verification after configuration** below.
11. Re-check public branch metadata and confirm `main` reports protected.
12. **Only after steps 1–11 pass**, create/set repository Actions variable `ACE_AUTONOMOUS_ACTUATION_ENABLED` to the exact string `true` if bounded ACE reproduction is intentionally being enabled.
13. Trigger/observe ACE and confirm the ledger reports both protection and explicit opt-in enabled before any bounded reproductive actuation is considered eligible.
14. Close #35 only after the intended GitHub controls—not merely the boolean branch bit—have been tested.

If protection is weakened, disabled, or under incident response, immediately remove/set false the ACE opt-in in addition to repairing the ruleset. Either failed gate keeps the workflow fail-closed.

## Bootstrap single-maintainer reality

IDKMesh currently has a bootstrap maintainer and does not yet have the contributor population needed for a permanent two-person approval rule on every change. Protection should therefore grow in stages rather than be configured into deadlock.

A reasonable bootstrap state is:

```text
PR required
+ stable CI required
+ force-push/deletion blocked
+ maintainer integration
+ independent review required where another trusted reviewer is available or where risk class demands external evidence
```

As trusted reviewers emerge, strengthen approval requirements and reduce single-person integration dependency.

## Automation behavior while either gate is disabled

Automation should fail closed for actions that cause autonomous reproduction, structural mutation, merge, or equivalent expansion of authority.

The ACE Community Growth workflow therefore enters `CONSOLIDATE` and disables its automatic Growth Seed reproductive actuator when either:

- GitHub does not report `main` protected; or
- `ACE_AUTONOMOUS_ACTUATION_ENABLED` is not exactly `true`.

Its evidence ledger may continue to update because that preserves observability without granting canonical code integration authority.

Repository Homeostasis remains proposal-first: observation may continue, but file moves, deletion, semantic rewrites, or stronger autonomous mutation should not be enabled before the protected boundary exists.

## Future autonomy tiers

A possible authority ladder is:

| Tier | Capability | Protected-main requirement |
| --- | --- | --- |
| 0 | Observe / report | recommended |
| 1 | Propose issue / PR | required before broad autonomous use |
| 2 | Deterministic low-risk metadata writes | required + explicit opt-in + audited workflow |
| 3 | Auto-merge narrowly defined deterministic changes | required + required checks + independent policy gate |
| 4 | Structural/self-evolution mutation | required + independent verifier + rollback/evidence policy |

IDKMesh should earn higher tiers from measured safety and usefulness rather than granting them in advance.

## Verification after configuration

Before enabling the ACE opt-in, verify at minimum:

- `main` reports as protected in GitHub branch metadata;
- a force-push is rejected under normal credentials;
- branch deletion is rejected outside the recovery path;
- direct integration outside the intended PR path is rejected where configured;
- required checks actually block a failing PR;
- the intended review requirement blocks a relevant high-risk change when an independent reviewer is available/required;
- automation does not have a broad bypass path;
- the emergency recovery path is documented and does not silently become the normal path.

After setting `ACE_AUTONOMOUS_ACTUATION_ENABLED=true`, also verify:

- ACE reports both protection and explicit actuation opt-in enabled;
- removing the variable (or setting any value other than exact `true`) returns ACE to fail-closed `CONSOLIDATE`;
- disabling branch protection also returns ACE to fail-closed behavior even if the variable is still present.

## Controller-state integrity

The ACE ledger is controller memory, not ordinary free-form documentation. The privileged workflow therefore also fails closed when:

- more than one open issue carries canonical `ace:ledger` identity;
- legacy migration finds multiple candidate ledgers;
- a legacy ledger was created by an untrusted external author;
- `ACE_STATE` is missing, malformed, wrong-version, contains non-finite/negative numeric state, invalid counters, or an invalid/implausibly future timestamp.

Manual repair should preserve evidence and explain what was corrected rather than silently resetting controller memory.

## Relationship to project architecture

This is not merely repository administration. It is the first concrete instance of the IDKMesh principle:

```text
proposal
 -> independent/deterministic evidence
 -> protected integration boundary
 -> explicit authority opt-in
 -> canonical state
```

The same separation should later exist between workers, verifiers, coordinators, and integrators in the Verified Swarm Runner.
