# 2026-10-13 — Visibility funnel measurement-coverage implementation

## Owner request

Continue implementing IDKMesh search visibility, traffic measurement,
and repository/community growth, saving code and documents to this repository.

## Problem

Search Console and GitHub Traffic snapshots are separate first-party
sources with incompatible populations and measurement windows. The existing
community observatory can report GitHub commit-contributor counts but
cannot attribute individual discovery events to contributors.
It would be misleading to divide 14-day repository views by 28-day search
clicks or lifetime contributor counts and call the result conversion.

## Implementation

- New `scripts/visibility_funnel_coverage.py` produces a deterministic,
  aggregate-only coverage map of seven funnel stages and six transitions.
- Optional Google Search Console and GitHub Traffic inputs are independently
  validated. Missing credentials preserve `unavailable` rather than zero;
  measured zero remains a real observed zero.
- Contributor counts remain a bounded GitHub commit-attribution proxy,
  not accepted/verified first contributions. Saturated contributor pages
  remain explicitly marked partial.
- Every transition has `not_attributable` status and null conversion
  rate because no supported cross-source cohort exists.
- The existing weekly `Visibility and Community Observatory` self-tests,
  computes, uploads, and summarizes the new JSON report without new secrets
  or repository write permissions.
- Updated V5 community design and analytics/operator documentation.

## Verification

Nine focused standard-library tests executed successfully in an isolated
local environment before publication. Workflow-contract checks were updated
to assert that the new measurement is wired into CI. The exact candidate
must pass protected-branch PR gates and review before merging.

This implementation does not provide a credible cross-source conversion
rate, independent contributor-retention evidence, website sessions, or any
private Google/GitHub account metrics. Those remain external measurement gaps.

## Community impact

Measured gaps are actionable without equating SEO traffic with trustworthy
software, recruiting metrics with accepted contributions, or popularity with
verification. It does not enable tracking pixels, hidden analytics,
personalized outreach, automatic posting, or merge authority.

Related: [#664](https://github.com/MSKazemi/idkmesh/issues/664),
[#665](https://github.com/MSKazemi/idkmesh/issues/665),
[#807](https://github.com/MSKazemi/idkmesh/issues/807).

**Provenance:** AI-assisted implementation and synthetic local tests. No live
owner-account traffic data was available.
