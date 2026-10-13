# 2026-10-13 — Search Console HTTP error confidentiality hardening

## Request

Continue implementing SEO and traffic visibility improvements in IDKMesh,
including code, tests, and documentation updates.

## Finding

The Search Console API and OAuth-refresh error handlers copied the first
500 characters of the remote HTTP error body into exceptions. That remote
response was not a safe logging boundary for credential-adjacent workflows.

## Change

Both error paths now report only the HTTP status plus a bounded diagnostic,
without response bodies, request URLs, token contents, or chained
`HTTPError` exceptions. Mocked HTTP 403 tests assert redaction for both
paths, including opaque URL, reason, bearer and refresh values.

Missing owner-provided credentials still skip optional collection. A
configured but rejected credential must fail visibly and must never be
interpreted as zero clicks/impressions.

## Evidence and limitations

The change includes deterministic unit coverage and is subject to the
repository PR Gate. No live Google Search Console property or private
credentials were accessed. It does not claim real search traffic, indexed
pages, or ranking improvements.

## Community impact

First-party measurements can be activated without exposing error response
content to shared CI logs. No correctness, publication, or merge authority
is granted by search data.
