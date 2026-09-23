# Search Visibility Analytics Setup

**Status:** operational setup for the read-only visibility observatory.

This document configures the external search evidence needed by the IDKMesh
visibility/community self-growth loop. Search analytics are **discovery evidence**.
They never grant correctness, publication, policy, or merge authority.

## Google Search Console

IDKMesh uses the Search Console Search Analytics API through
`scripts/search_console_snapshot.py`.

The adapter requests:

- search type: `web`;
- dimensions: `query`, `page`;
- finalized data only;
- a 28-day window by default;
- a three-day lag by default;
- only rows whose page begins with `https://mskazemi.com/idkmesh/`;
- up to 100,000 rows locally, paginated in chunks no larger than 25,000.

The output separates:

- branded queries containing `idkmesh`;
- non-branded discovery queries;
- exact matches to the checked-in 100-query portfolio;
- exact-match observations by intent cluster.

The adapter records Google's documented limitation that Search Console may return
top rows rather than a complete exhaustive query inventory.

### Repository variable

Create:

```text
GSC_SITE_URL
```

Its value must be the property identity exactly as configured in Search Console.
Examples supported by Google's API include a URL-prefix property or a
`sc-domain:` property.

The workflow does not guess this value.

### Authentication option A — refresh credentials

Recommended for the scheduled workflow.

Create repository secrets:

```text
GSC_REFRESH_TOKEN
GSC_CLIENT_ID
GSC_CLIENT_SECRET
```

The OAuth grant must permit read access to the Search Console property. The adapter
exchanges the refresh token for a short-lived access token at runtime and never writes
the token to an artifact.

### Authentication option B — direct access token

For a short manual experiment, create:

```text
GSC_ACCESS_TOKEN
```

A direct access token takes precedence when present. Because access tokens expire,
this is not the preferred long-term scheduled configuration.

### Fail-quiet behavior

If `GSC_SITE_URL` and a complete credential set are absent, the weekly visibility
workflow still succeeds and reports:

```text
Search Console: not configured
```

Static SEO/AEO, GitHub discovery, community-acquisition, and query-portfolio
observations continue to run.

This prevents missing private credentials from disabling the public repository
observatory.

## Query portfolio

The non-branded hypothesis set lives at:

```text
config/discovery-query-portfolio-v0.1.json
```

It is validated by:

```text
python scripts/discovery_query_portfolio.py \
  --portfolio config/discovery-query-portfolio-v0.1.json \
  --root .
```

The current contract requires:

- exactly 10 intent clusters;
- exactly 10 queries per cluster;
- 100 unique non-branded queries total;
- an existing canonical target for every cluster;
- at least one existing evidence reference for every cluster;
- recommendation-only authority.

A query appearing in this file is a **hypothesis about useful search intent**, not
evidence that people actually search for it.

Search Console observations are what begin to convert that hypothesis into observed
demand.

## Bing Webmaster Tools

Do **not** implement or re-enable the historical SOAP/POX endpoints.

Microsoft's current documentation states that the legacy SOAP and POX APIs were
retired on **2026-08-31** and directs users to its REST APIs. The public documentation
surface available during this implementation did not expose enough authenticated REST
query-stat contract detail to add a production adapter without guessing.

The Bing slice therefore remains intentionally open:

1. obtain the current REST API contract from the authenticated Bing Webmaster
   documentation/account;
2. implement it as a separate read-only adapter;
3. normalize its aggregate query/page data into the same discovery evidence model;
4. test it with recorded synthetic responses;
5. never fall back to the retired legacy endpoint.

## Privacy boundary

The observatory should retain aggregate search-performance rows only.

Do not ingest:

- user identities;
- IP addresses;
- cookies;
- browser fingerprints;
- per-user clickstream histories.

The question is **which search intents produce discovery and durable community
capacity**, not who an individual visitor is.

## Authority boundary

These remain invariants:

```text
search impression != truth
search click       != adoption
search rank        != correctness
star               != correctness
query portfolio    != demand evidence
analytics result   != permission to publish
```

The data may recommend a bounded experiment. Existing verification and governance
still decide what becomes canonical.
