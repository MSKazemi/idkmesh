# 2026-10-13 — enterprise cross-layer conformance review

**Owner request:** work on ten issues; strengthen implementation, enterprise
quality, user documentation and architecture, saving changes in the repository.

**Scope selected:** #670, #672, #673, #676, #743, #750, #598, #597,
#609 and #682. These are existing open issues, not ten closed or production-
qualified milestones.

## Observations

- The repository already contains separate authorization, decision-cache,
  tenant isolation, data policy, audit, claims, public projection and local
  API boundary kernels. Reimplementing them would create competing authority
  semantics rather than enterprise quality.
- The E9 harness previously left stale claim and provider outage scenarios
  entirely UNKNOWN even though local claim fencing and connector error
  classification were available for partial, repeatable in-process evidence.
- The E9 identity-cache scenario previously described cache support as
  absent despite the real bounded cache module. That is now corrected.
- The existing conformance harness cannot prove real G2/G3 authenticated
  service operation, provider effects, live GitHub role binding, backups after
  storage failure, external outage behaviour or human approval.

## Implementation decisions

- Extend the existing in-process E9 harness without creating a second
  conformance service or changing the source/verification/merge authority
  split.
- Exercise real existing kernels against temporary, credential-free fixtures.
  A scenario with remaining live-integration gaps reports WARN, never PASS.
- Keep live release-provenance qualification UNKNOWN; do not manufacture
  provenance verification or independent human observations.
- Add fault-injection regression tests for five critical boundary failures.
- Cross-link each of the ten issue slices to the exact remaining operational
  evidence in the canonical enterprise architecture document.

## Validation and provenance

AI-assisted coding and source review; requires exact-head PR Gate and CodeQL,
independent human review, and (where applicable) real external deployment
trials. Container checkout could not be cloned in this environment because
GitHub DNS resolution failed, so the full repository pytest suite was not
run locally. A passing CI check proves tests ran at its recorded head only.

**Authority:** no automatic dispatch, credential materialization, evidence
acceptance, human decision, Git push, protected merge or certification.
