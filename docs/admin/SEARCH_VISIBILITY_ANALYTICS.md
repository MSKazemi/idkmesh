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

### Safe API failure diagnostics

Google Search Console and OAuth token refresh failures report the HTTP status and
which authorization/configuration path to inspect, without logging API response
bodies, request URLs, bearer credentials, OAuth refresh values, or chained HTTP
exceptions. A configured collector **fails visibly** on HTTP 403/401 instead of
turning an authentication failure into a zero-traffic measurement. Check the
repository secret/property permissions privately; never paste an exception
response body into a public issue or PR.

### Fail-quiet behavior

If `GSC_SITE_URL` and a complete credential set are absent, the visibility
workflow still succeeds and reports:

```text
Search Console: not configured
```

Static SEO/AEO, GitHub discovery, community-acquisition, and query-portfolio
observations continue to run.

This prevents missing private credentials from disabling the public repository
observatory.

### Workflow cadence

The observatory runs in three modes:

- **weekly** at `06:11 UTC` on Monday for longitudinal measurement;
- **manual** through `workflow_dispatch` for an owner-requested read-only check;
- **contract-triggered** on protected `main` when the observatory workflow,
  canonical 100-query contract, analytics companion, growth policy, or
  measurement scripts change.

The push trigger is intentionally path-bounded. Ordinary product/docs commits do
not repeatedly query Search Console. A measurement-contract change does run the
observer immediately, which proves the workflow remains executable and makes
missing Search Console configuration visible without waiting for the next weekly
window.

## Query portfolio

There is one canonical 100-query source:

```text
config/seo-topics-v1.json
```

It owns the ten semantic clusters, their 100 query strings, and the ten canonical
topic targets.

The visibility observatory consumes an analytics companion:

```text
config/discovery-query-portfolio-v0.1.json
```

That companion adds evidence references and recommendation-only analytics
metadata, but its cluster ids, labels, query strings, and canonical targets are
required by CI to match `config/seo-topics-v1.json` exactly. This prevents the
site from optimizing one "top 100" list while Search Console measures another.

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
- exact query/cluster/target equality with `config/seo-topics-v1.json`;
- an existing canonical target for every cluster;
- at least one existing evidence reference for every cluster;
- recommendation-only authority.

A query appearing in this file is a **hypothesis about useful search intent**, not
evidence that people actually search for it.

Search Console observations are what begin to convert that hypothesis into observed
demand.

## GitHub repository Traffic API (optional owner-authorized evidence)

The existing public GitHub API reports stars, forks, and subscribers but **not**
GitHub Insights visitor/clone traffic. `scripts/github_traffic_snapshot.py`
adds an opt-in read-only collector to the *same* weekly
`Visibility and Community Observatory`. It is not enabled without credentials.

GitHub exposes rolling ~14-day repository traffic through authenticated endpoints
(`traffic/views`, `traffic/clones`, and `traffic/popular/referrers`). The
adapter stores aggregate totals, window-level unique visitors/cloners, per-day
counts, and top referrer aggregates. It never collects visitor identities,
IP addresses, raw headers, cookies, or individual visits.

### Owner setup

1. Decide whether publishing aggregate traffic in repository Actions artifacts is
   acceptable for this public open-source project. The workflow's existing
   `results/visibility/` artifact has a **30-day retention** policy.
2. Create a **fine-grained GitHub personal access token** scoped to
   `MSKazemi/idkmesh`, with the minimum repository permission required for
   GitHub's Traffic API: **Administration: read-only**. GitHub labels this
   permission "Administration" even though the selected access is read-only.
   It exposes more repository administration metadata than ordinary read access;
   use a dedicated, revocable token. Repository-owner approval may be required.
3. Add it as the Actions **repository secret** `GITHUB_TRAFFIC_READ_TOKEN`
   (Settings → Secrets and variables → Actions). Do **not** put it in a
   workflow variable, code, issue, PR, documentation, chat, or uploaded data file.
4. Manually run **Visibility and Community Observatory** from trusted `main`
   once, or allow the normal weekly run. It writes
   `results/visibility/github-traffic.json` inside the retained workflow
   artifact and shows total views/unique visitors and clones/unique cloners
   in the job summary.

The collector is skipped when the secret is absent; the summary says
**unavailable**, never zero. When a configured token is rejected (for example
HTTP 403), the workflow fails visibly and does not publish a misleading traffic
observation. Credential contents and API response bodies are never written to
error output. The collector does not attempt a fallback to the ordinary
`GITHUB_TOKEN`, which lacks the required Traffic API authorization.

Standalone use (requires an owner-authorized environment secret):

```bash
python scripts/github_traffic_snapshot.py \
  --repository MSKazemi/idkmesh \
  --output results/visibility/github-traffic.json
```

GitHub's traffic history is limited to the last 14 days and **daily unique
counts must not be added together** to estimate 14-day unique visitors. The
weekly snapshots overlap. Historical uniqueness cannot be recovered simply by
summing them. GitHub repo views are not website page views, search impressions,
Search Console clicks, installations, or verified contributions.

### Evidence interpretation

| Question | Trustworthy metric | Not measured by this adapter |
| --- | --- | --- |
| Did visitors view GitHub repository pages? | `views.count`, `views.uniques` in one GitHub 14-day window | Visits to `mskazemi.com/idkmesh/` |
| Were repository clones observed? | `clones.count`, `clones.uniques` | Successful installations or active users |
| Where are GitHub visitors referred from? | Aggregated top referrers only | Complete channel attribution or user journeys |
| Is non-brand Google discovery improving? | Google Search Console read-only query/page report (separately configured) | GitHub Traffic figures |
| Are visitors becoming repeat contributors? | Requires independent issue/PR/contribution funnel evidence | Repository views alone |

No traffic metric grants repository correctness, integration, automatic publication,
or merge authority. Do not invent baseline values if no authorized token exists.

## Read-only funnel coverage (V5)

The weekly observatory emits `results/visibility/funnel-coverage.json` after
Search Console and GitHub Traffic collection. It does not need any new
credential or hosted service. It runs even when neither optional provider
is configured, reporting `unavailable` rather than zero.

It reports separate observations for non-branded Google search, GitHub repository
views, and a limited snapshot of external commit contributors. It explicitly
marks website visits, identifiable first interactions, independently verified
first contributions, and repeat-contributor cohorts as **not observed**.

**Conversion rates are not calculated.** Search Console query clicks are not
website visits; GitHub's 14-day view counter is not a time-matched cohort of
Search Console searchers; lifetime contributors are not a first-contribution
cohort. No visitor identities, cookies, fingerprints, or synthetic joins
are collected.

Run it manually against real retained evidence:

```bash
python scripts/visibility_funnel_coverage.py \
  --visibility results/visibility/observatory.json \
  --output results/visibility/funnel-coverage.json
```

Supply `--search-console` and `--github-traffic` with paths to real JSON
snapshots if present. The collector validates provider identity, repository,
canonical page scope, final-data state, date windows, counters, and observed
population bounds. An invalid or explicitly supplied missing file fails,
rather than becoming a fictional zero. See
[the V5 measurement boundary](../community/VISIBILITY_AND_COMMUNITY_GROWTH_LOOP.md#v5--funnel-attribution)
for the stage-by-stage interpretation.

## Evidence-aware growth recommendation (V6)

The weekly workflow first creates `results/visibility/funnel-coverage.json`,
then calls `scripts/visibility_growth_selector.py` with the exact versioned
V4 reference ledger, ten canonical topic targets and V5 funnel-coverage
snapshot. The resulting `growth-experiment.json` includes aggregated evidence
readiness and **one recommendation**, not a permission to publish.

For manual replay from repository root, after collecting real observatory and
query-portfolio snapshots:

```bash
python scripts/visibility_growth_selector.py \
  --visibility results/visibility/observatory.json \
  --portfolio results/visibility/query-portfolio.json \
  --policy config/visibility-growth-policy-v0.1.json \
  --authority-ledger evidence/search-visibility/authority-references.json \
  --authority-topics config/seo-topics-v1.json \
  --funnel-coverage results/visibility/funnel-coverage.json \
  --output results/visibility/growth-experiment.json
```

Only supply `--search-console results/visibility/google-search-console.json`
when that authenticated evidence actually exists. Explicit missing files,
malformed counters, wrong provider/page scope, unfinalized Search Console
data, or funnel reports that claim conversion rates **fail closed**.
If Search Console reports a locally truncated query rowset, the controller
recommends a measurement-quality review before altering titles/keywords.

The V4 direct-link counts are owner-reviewed claims, not independently
authenticated backlinks. V5 commit contributors are not independently
verified first contributions; there are no visitor-to-contributor conversion
rates. All numerical thresholds remain hand-authored bootstrap priors.

## Bing Webmaster Tools

Do **not** implement or re-enable the historical SOAP/POX endpoints.

Microsoft's current documentation states that the legacy SOAP and POX APIs were
retired on **2026-08-31** and directs users to its REST APIs. The public documentation
surface available during this implementation did not expose enough authenticated REST
query-stat contract detail to add a production adapter without guessing.

The authenticated REST adapter remains intentionally open:

1. obtain the current REST API contract from the authenticated Bing Webmaster
   documentation/account;
2. implement it as a separate read-only adapter;
3. normalize its aggregate query/page data into the same discovery evidence model;
4. test it with recorded synthetic responses;
5. never fall back to the retired legacy endpoint.

Bing AI Performance does provide owner-downloadable CSV/Excel exports. Those do
not require repository credentials. Normalize a reviewed CSV offline with
`scripts/bing_ai_performance_import.py`; the command accepts explicit column
names for grounding-query, page, date, and citation-count exports rather than
guessing vendor headers. Exact grounding-query matches are compared with the same
canonical 100-query portfolio used by Search Console.

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
