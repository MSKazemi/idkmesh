# 2026-10-13 — Evidence-aware growth selection and quality gates

## Owner request

Continue implementing IDKMesh SEO, real traffic and community visibility
capability after merging the read-only visibility and contributor-funnel
measurement contracts.

## Finding

The V6 experiment selector previously ignored the V4 external reference
ledger and the V5 funnel-coverage report. It could also recommend changing
search snippets from truncated Search Console query evidence, and implicitly
coerce some malformed search metrics to zero.

## Change

The V6 recommendation-only selector now validates optional finalized
Google Search Console query/page evidence, its canonical site prefix, local
pagination cap and finite counters. Truncated evidence selects a
measurement-quality review before any content/snippet edit.

It also consumes the existing V4 owner-attested reference ledger and V5
coverage-only funnel report. A zero independent-link count means zero
*reviewed, recorded* claims, not zero external backlinks. The V5 report
cannot establish cross-source conversions and is forbidden from claiming
non-null conversion rates.

The existing read-only weekly observatory now assembles V5 evidence before
V6 selection, validates the V4 record and includes an aggregate quality
summary in retained artifacts. No new credentials, personal visitor IDs,
tracking, issue/PR writes, outreach or merge authority are added.

## Verification

Existing and new deterministic selector tests cover old fallback behavior,
truncated GSC, malformed/NaN/negative source data, empty versus reviewed
authority references, syndication exclusions, invalid funnel attribution,
and explicit missing-file failure. Workflow tests assert correct stage
ordering and preserved read-only permissions.

No owner Google Search Console property, confidential traffic logs, or
independent external reviews were accessed. Exact-head repository CI and
standard human review remain required before integration.

## Community impact

This prevents spurious SEO changes and makes recommendations about evidence
gaps instead of pretending the site has measured conversions or independent
citations. Thresholds remain uncalibrated bootstrap assumptions, not an
autonomous optimization policy.

Related: [issue #664](https://github.com/MSKazemi/idkmesh/issues/664),
[issue #665](https://github.com/MSKazemi/idkmesh/issues/665),
[issue #807](https://github.com/MSKazemi/idkmesh/issues/807).

**Provenance:** AI-assisted source inspection and change; no verified
external traffic or independently authenticated review claimed.
