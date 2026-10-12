# 2026-10-11 — Independent external-authority reference evidence

## Owner request and context

Continue implementation of genuine IDKMesh discoverability, SEO, and traffic
improvement after merging the read-only GitHub Traffic collector in PR #1003.

## Investigated gap

The public site has technical SEO checks and an intent portfolio, but the
external-reference axis under issue #780 has no reproducible classification
record. Public search surfaces apparent summaries and syndications of the
project's own posts; a search hit alone does not prove editorial independence,
a direct backlink, an actual click, or a verified research reproduction.

## Bounded implementation

Add a strict offline JSON ledger under
`evidence/search-visibility/authority-references.json`, a deterministic
report, `scripts/authority_reference_ledger.py`, and nine focused tests.
Map each observation to one of ten canonical topic URLs. Distinguish authored,
syndicated, externally unknown, and purported independent references; require
explicit owner-reviewed **and** direct-link-checked status before including it
in the claimed independent bucket.

This is owner attestation, not proof of independence; the initial ledger is
empty. No synthetic backlinks, downloaded private data, scraping, outreach,
publication, change of integration authority, or rank prediction is introduced.
Source URL validation excludes owned site/GitHub paths and unsupported private
endpoint formats; the report groups by intent cluster and distinct source host
without manufacturing an authority score.

## Test evidence and outcome

A local isolated standard-library test run passed all nine tests against
synthetic examples and verified report generation with a ten-cluster fixture.
The full PR Gate remains the final check against repository data. The new tests
also check that the committed report matches the ledger and canonical portfolio.

## Follow-ups

Issue [#780](https://github.com/MSKazemi/idkmesh/issues/780) tracks earning and
recording genuine third-party references, not just the ledger foundation.
Search Console activation in [#807](https://github.com/MSKazemi/idkmesh/issues/807)
and independent adoption/reproduction evidence remain separate owner/external
dependencies.

## Community impact

Reviewers can reproduce the difference between genuine cited work,
project-authored distribution, and uncertain external mentions. No popularity
signal can become evidence of correctness or confer publication/merge authority.

**Provenance:** AI-assisted implementation and synthetic fixture testing.
No independent human classification of real-world backlinks is claimed.
