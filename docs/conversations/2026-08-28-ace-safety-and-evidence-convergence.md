# Conversation Record — Continue ACE Safety and Evidence Convergence

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Project-owner direction

The project owner instructed the assistant to continue improving IDKMesh in the public repository. The standing objective remains that repository activity should improve either verified system capability, project knowledge, safety/debt, or community reproduction rather than merely increase raw activity.

## Starting point

The previous continuation had strengthened the ACE lineage contract in PR #48 and synchronized the main ACE dependency stack:

- PR #40 — cohort/eligible-parent observation;
- PR #44 — offline population/carrying-capacity simulator;
- PR #48 — causal parent -> seed -> descendant lineage evidence;
- PR #68 — Activity Metabolism / shadow generational controller.

The remaining autonomy gates included:

- PR #51 — fail closed ACE actuation while `main` is unprotected;
- PR #62 — metadata-plane threat model and hardening of the same ACE workflow.

## New finding: two safety PRs changed the same privileged workflow

Both PR #51 and PR #62 modify `.github/workflows/ace-community-growth.yml`, but they protect different boundaries.

PR #51 contributes:

- read the actual GitHub protection state of `main`;
- force `CONSOLIDATE` while `main` is unprotected;
- prevent the reproductive Growth Seed actuator from running until protection exists;
- document the protected integration contract in governance/admin docs.

PR #62 contributes:

- pin `actions/github-script` to an immutable commit;
- treat `ACE_SEED` marker text as data, not authorization;
- require trusted `author_association` before marker-derived `growth-seed` labeling;
- identify the ACE ledger with workflow-owned `ace:ledger` label;
- fail closed on missing/malformed ledger state;
- paginate issue scans;
- require a labelled Growth Seed for dedupe-marker authority;
- avoid copying untrusted PR titles into generated issues;
- document a detailed ACE workflow threat model.

Merging these independently in the wrong order could discard one set of protections. Therefore the correct repository evolution is **convergence**, not two competing safety variants.

## Consolidation decision

PR #51 is promoted as the canonical ACE safety boundary because branch/ruleset protection is the hard prerequisite for stronger autonomy. The useful #62 hardening is folded into the same workflow and security documentation rather than maintained as a competing implementation.

The combined safety contract is:

```text
untrusted GitHub metadata
 -> typed/trusted metadata gates
 -> fail-closed ledger state
 -> capacity state
 -> actual main-protection check
 -> bounded issue-only actuator
```

with hard rules:

```text
pull_request_target never executes PR code
marker text != authorization
malformed state != reset-to-default
main unprotected => CONSOLIDATE + no reproduction
contents write/merge authority absent
```

## Executable safety contract

Added `tests/test_ace_safety_contract.py` and `.github/workflows/ace-safety-contract.yml`.

The contract test checks that the privileged ACE workflow:

- contains no `actions/checkout` step and no shell `run:` step;
- pins `actions/github-script` to the reviewed immutable SHA;
- reads actual `main` protection state;
- gates actuation on protection and forces consolidation when protection is absent;
- uses trusted author association for marker-derived seed labeling;
- uses `ace:ledger`, pagination, and fail-closed ledger parsing;
- requires the `growth-seed` label for dedupe-marker authority;
- does not interpolate untrusted PR titles into generated issues;
- does not grant `contents: write`.

This is intentionally a contract test over the privileged workflow surface. It does not claim to replace independent security review or GitHub rulesets.

## Project-level lesson

The self-improvement law should include **cross-branch convergence cost**. Two locally useful changes that modify the same control surface can create net risk if their integration order is ambiguous.

A useful future structural signal is therefore:

```text
SafetyOverlap(PR_i, PR_j)
  = shared privileged files
    * semantic safety importance
    * branch divergence
```

High overlap should trigger consolidation/review before either branch is treated as independently ready.

## Safety status

At the time of this continuation, public branch metadata still reports `main` as unprotected. Repository documentation and workflow gates can fail closed, but they cannot replace the repository administrator enabling the real GitHub ruleset/branch protection.

No autonomous merge, code execution, secret access, governance mutation, or broad recursive actuator is enabled by this work.

## Community impact

Consolidating the safety patches reduces reviewer ambiguity and prevents contributors from having to reason about two competing versions of the same privileged workflow. The explicit safety test also makes future workflow changes easier to review: a contributor can see which invariants are expected to remain true.

## Next step

1. Run the consolidated safety contract CI.
2. Review the canonical safety PR as one coherent control-plane change.
3. Configure actual GitHub `main` protection/ruleset and verify branch metadata.
4. Keep ACE Phase-B actuation off until lineage, cohort observation, security, protection, and real descendant evidence are all accepted.
5. Then make the shadow controller consume canonical lineage receipts rather than a parallel descendant format.
