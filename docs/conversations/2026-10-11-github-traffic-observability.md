# 2026-10-11 — Add optional first-party GitHub Traffic evidence

## Owner request

Continue work on improving IDKMesh repository visibility, SEO, and traffic and
save the implementation and documentation in the canonical repository.

## Investigation and decision

The technical crawl/discovery foundation is already implemented. The public
GitHub API exposes stars/forks/subscribers but *not* the repository's unique
visitors, views, or clones. The connected GitHub repository fetch API does not
allow access to the private Traffic endpoint, and Search Console remains a
separate owner-account setup under [#807](https://github.com/MSKazemi/idkmesh/issues/807).

Do not manufacture visits, infer traffic from SEO readiness, or add another
generic keyword-page generator. Implement a small **opt-in, read-only GitHub
Traffic API adapter** in the existing visibility observatory instead.

## Implementation

- `scripts/github_traffic_snapshot.py`: validates and normalizes aggregate
  `views`, `clones`, and top-referrer API responses, keeping 14-day window-level
  uniqueness distinct from per-day uniqueness. Does not write credentials.
- `tests/test_github_traffic_snapshot.py`: deterministic synthetic response
  fixtures, API path validation, malformed counter/timestamp/referrer rejection,
  absent-data vs measured-zero distinction, and redaction of HTTP errors.
- `.github/workflows/visibility-observatory.yml`: trusted `main` workflow
  checks optional `GITHUB_TRAFFIC_READ_TOKEN` and collects traffic only when
  present; publishes a bounded summary and the normal 30-day retained artifact.
  No extra GitHub write authority is introduced.
- `docs/admin/SEARCH_VISIBILITY_ANALYTICS.md`: least-privilege credential
  configuration, limitations, output fields, privacy, and operational guidance.

The collector is **not configured** on behalf of the owner. A real observation
requires the owner's dedicated fine-grained token with Administration: read-only
access to `MSKazemi/idkmesh`. This permission is repository-admin metadata
read, so enabling it is a deliberate owner choice.

## Verification and evidence boundary

Six focused standard-library unit tests and Python compilation passed in an
isolated local execution environment before publishing. GitHub PR Gate is still
required to validate integration against the current full repository. Source
data in the tests is deliberately synthetic; no real unique-visitor or clone
counts were obtained.

`views != website visits`; `clones != adoption`; `traffic != correctness`.

## Related issues

[#664](https://github.com/MSKazemi/idkmesh/issues/664) (visibility funnel),
[#665](https://github.com/MSKazemi/idkmesh/issues/665) (search observations),
[#807](https://github.com/MSKazemi/idkmesh/issues/807) (Google setup), and
[audit PR #1003](https://github.com/MSKazemi/idkmesh/pull/1003).

## Community impact

The project can observe whether real people arrive at the repository without
exposing per-user data or granting an automated controller publication or merge
authority. It remains the maintainers' job to interpret these aggregate
numbers and seek genuine adoption and independent evidence, not manufactured
engagement.

**Provenance:** AI-assisted implementation with local synthetic tests; no
external credentials, independent human review, or real GitHub Traffic
measurements were available in this session.
