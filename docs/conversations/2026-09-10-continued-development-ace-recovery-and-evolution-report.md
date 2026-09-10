# Continued development — ACE recovery and auditable evolution report

**Date:** 2026-09-10  
**Repository:** `MSKazemi/idkmesh`

## Owner request

The project owner asked ChatGPT to continue helping with development after the
Repository Mathematical Portfolio concurrency fix had been integrated.

## Work completed before this report change

The session first completed issue #379 through PR #419.

The measured problem was that `ace-community-growth.yml` uses one global
concurrency group to serialize its singleton Growth Ledger, while GitHub may
replace a run that is still pending in that group. Event-only Growth Seed effects
could therefore be skipped even though parallelizing the ledger writer would have
introduced a different lost-update risk.

The integrated repair kept one serialized ledger writer and made the external
seed effects convergent from current repository state:

- trusted `ACE_SEED` issues missing `growth-seed` are re-discovered and labelled
  idempotently;
- merged pull requests explicitly carrying `growth:spawn` are reconciled against
  existing descendants;
- ordinary missing-descendant bursts are recovered in a bounded batch;
- a backlog above the automatic cap fails before descendant creation;
- the existing trust, actuation, no-PR-code-execution, and integration-authority
  boundaries remain unchanged.

PR #419 passed the exact-head PR Gate, CodeQL, observatory, Evolution Loop, ACE
security/hardening checks, and the three-version randomness matrix before squash
merge. Issue #379 was then explicitly closed as completed.

## Next selected issue

The session then selected issue #373: make `EVOLUTION_REPORT.md` a reliable,
auditable current-state entrypoint.

The audit found two separate concerns sharing one filename:

1. the checked-in root `EVOLUTION_REPORT.md` should be a reviewed synthesis of
   current state, evidence classes, active gates, the weakest bottleneck, and the
   next bounded decision;
2. `scripts/evolution_score.py` also writes a volatile persistent-history report,
   and the Evolution Loop invoked it without `--report`, so the Actions workspace
   reused the checked-in root path as generated runtime output.

The durable report and the runtime report therefore needed an explicit boundary.

## Implementation decision

The repository-authored `EVOLUTION_REPORT.md` is rewritten as a current-state
index rather than a controller artifact. It records:

- the North Star from `ROADMAP.md`;
- a dated repository baseline;
- implemented, synthetic/test, observed, and accepted/independent evidence as
  distinct classes;
- current open evidence gates (#151, #57, and research track #86);
- independent/real-world evidence as the current weakest layer;
- one bounded next intervention: a genuinely independent current-main review
  under #151;
- provenance and an explicit update procedure.

The Evolution Loop is changed so the persistent Bayesian runtime report is
written to:

`results/evolution/PERSISTENT_EVOLUTION_REPORT.md`

The live repository observatory keeps its separate runtime report at:

`results/evolution/EVOLUTION_REPORT.md`

The root authored report is removed from runtime artifact and job-summary
consumption. Focused tests pin both the workflow boundary and the report's
synthesis contract.

## Evidence discipline

This change deliberately does not copy volatile posterior numbers into the
checked-in report. Current machine values remain exact-run evidence tied to a
workflow run and artifact. It also does not claim that open independent-review or
real-descendant gates have been satisfied.

## Community impact

A contributor or reviewer now has one progressively disclosed current-state
entrypoint instead of having to infer project status from a bootstrap seed file
or a generated workflow artifact with the same name. Separating authored
synthesis from runtime evidence also reduces the chance that future maintainers
mistake controller output for a reviewed repository conclusion.

## AI/tool provenance

The repository audit, implementation, tests, documentation, and pull-request
preparation were performed with ChatGPT through the repository owner's authorized
GitHub connector. Integration remains subject to the repository's exact-head CI
and protected-branch rules.
