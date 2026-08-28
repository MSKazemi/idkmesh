# Protected `main` Integration Boundary

**Status:** Required P0 repository-admin configuration  
**Tracking issue:** #35

IDKMesh uses GitHub as both its public collaboration substrate and, increasingly, an execution/control surface for deterministic automation and bounded agents. Instructions inside those agents are not a security boundary. The canonical `main` branch therefore needs an explicit GitHub ruleset or branch-protection policy before autonomous write authority is increased.

## Safety invariant

> No autonomous actor may propose, approve, and merge the same protected change by itself.

A successful worker run, agent proposal, community-growth event, or repository-homeostasis proposal is evidence for review. It is not authority to mutate canonical state.

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
6. Add the stable required status checks listed above as they become available.
7. Configure review requirements appropriate to the current small bootstrap team; do not create an impossible approval requirement while only one maintainer exists.
8. Avoid broad bypass actors. Keep emergency maintainer bypass narrow and auditable if one is necessary.
9. Save/enforce the ruleset.
10. Re-check public branch metadata and close #35 only after `main` reports protected and the intended behaviors have been tested.

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

## Automation behavior while `main` is unprotected

Automation should fail closed for actions that cause autonomous reproduction, structural mutation, merge, or equivalent expansion of authority.

The ACE Community Growth workflow therefore treats an unprotected `main` as `CONSOLIDATE` mode and disables its automatic Growth Seed reproductive actuator. Its evidence ledger may continue to update because that preserves observability without granting canonical code integration authority.

Repository Homeostasis remains proposal-first: observation may continue, but file moves, deletion, semantic rewrites, or stronger autonomous mutation should not be enabled before the protected boundary exists.

## Future autonomy tiers

A possible authority ladder is:

| Tier | Capability | Protected-main requirement |
| --- | --- | --- |
| 0 | Observe / report | recommended |
| 1 | Propose issue / PR | required before broad autonomous use |
| 2 | Deterministic low-risk metadata writes | required + audited workflow |
| 3 | Auto-merge narrowly defined deterministic changes | required + required checks + independent policy gate |
| 4 | Structural/self-evolution mutation | required + independent verifier + rollback/evidence policy |

IDKMesh should earn higher tiers from measured safety and usefulness rather than granting them in advance.

## Verification after configuration

After the ruleset is enabled, verify at minimum:

- `main` reports as protected in GitHub branch metadata;
- a force-push is rejected under normal credentials;
- direct integration outside the intended PR path is rejected where configured;
- required checks actually block a failing PR;
- the emergency recovery path is documented and does not silently become the normal path;
- ACE reports that main protection is enabled before its bounded reproductive actuator becomes eligible.

## Relationship to project architecture

This is not merely repository administration. It is the first concrete instance of the IDKMesh principle:

```text
proposal
 -> independent/deterministic evidence
 -> protected integration boundary
 -> canonical state
```

The same separation should later exist between workers, verifiers, coordinators, and integrators in the Verified Swarm Runner.
