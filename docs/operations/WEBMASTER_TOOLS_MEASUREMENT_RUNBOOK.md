# Google Search Console and Bing Webmaster Measurement Runbook

**Scope:** `https://mskazemi.com/idkmesh/`

This runbook converts the repository-controlled SEO/AEO/GEO architecture into
first-party search and AI-citation evidence. It does not promise ranking and it
does not treat crawler health as proof of indexing.

The canonical target map is `config/seo-topics-v1.json`. The canonical observed
evidence ledger is `evidence/search-visibility/observations.json`.

## Google Search Console

### Property

Use a URL-prefix property for:

`https://mskazemi.com/idkmesh/`

Google documents that URL-prefix properties can include a path and contain only
URLs that begin with that exact protocol/host/path prefix. This keeps IDKMesh
measurement separate from unrelated content on `mskazemi.com`.

Official property guidance:
https://support.google.com/webmasters/answer/10432366
https://support.google.com/webmasters/answer/34592

Use an ownership-verification method available to the maintainer account. Do not
commit account cookies, OAuth tokens, passwords, or private account exports.

### Sitemap

Submit:

`https://mskazemi.com/idkmesh/sitemap.xml`

After submission, record the submission state and any processing error in issue
#665. The repository's public discovery monitor already verifies that the
sitemap is retrievable and contains the topic architecture; Search Console is
the first-party evidence for how Google processes it.

### URL inspection acceptance set

Inspect these 11 canonical topic URLs:

1. `https://mskazemi.com/idkmesh/topics/`
2. `https://mskazemi.com/idkmesh/topics/ai-agent-verification.html`
3. `https://mskazemi.com/idkmesh/topics/multi-agent-orchestration.html`
4. `https://mskazemi.com/idkmesh/topics/ai-code-review.html`
5. `https://mskazemi.com/idkmesh/topics/llm-judge-reliability.html`
6. `https://mskazemi.com/idkmesh/topics/verifier-panels.html`
7. `https://mskazemi.com/idkmesh/topics/agent-governance.html`
8. `https://mskazemi.com/idkmesh/topics/provenance-evidence.html`
9. `https://mskazemi.com/idkmesh/topics/mcp-a2a-interoperability.html`
10. `https://mskazemi.com/idkmesh/topics/verification-scaling.html`
11. `https://mskazemi.com/idkmesh/topics/verified-swarm-engineering.html`

For each URL record:

- indexed / not indexed;
- Google-selected canonical versus declared canonical;
- crawl/index reason when not indexed;
- last crawl when available;
- whether a live test reports the page as retrievable.

Do not turn a successful live test into an indexing claim.

### Search Performance exports

Use at least these time windows when data exists:

- 7 days for recent change detection;
- 28 days for the normal iteration loop;
- 3 months for trend context.

Export query and page data. Preserve Google's reported population and date
window. Do not convert average position into a probability of ranking.

For the 100-intent review:

1. normalize query text for comparison only; retain the original query;
2. map an observed query to the closest existing intent only when the semantic
   relationship is clear;
3. keep truly new intent classes separate rather than forcing a match;
4. prioritize pages with impressions but weak CTR/position for content/title
   review;
5. distinguish 'no impressions observed' from 'not indexed'.

## Bing Webmaster Tools

### Site property

Bing supports verification of an entire domain or a site limited to a branch or
directory. The preferred IDKMesh scope is the same public path:

`https://mskazemi.com/idkmesh/`

If the Google Search Console property above is verified, Bing can import a
verified Search Console site and its sitemap metadata. Otherwise use a supported
Bing verification method.

Official guidance:
https://www2.bing.com/webmasters/help/add-and-verify-site-12184f8b

### Sitemap and crawl health

Submit or confirm discovery of:

`https://mskazemi.com/idkmesh/sitemap.xml`

Record:

- submission/discovery method;
- processing status;
- last-read time;
- URL count reported by Bing;
- processing errors.

Bing documents both robots.txt sitemap discovery and direct Webmaster Tools
submission. IDKMesh already uses both the sitemap and IndexNow on the public
side.

Official sitemap guidance:
https://blogs.bing.com/webmaster/July-2025/Keeping-Content-Discoverable-with-Sitemaps-in-AI-Powered-Search/
https://www2.bing.com/webmasters/help/sitemaps-3b5cf6ed

### Search Performance

Export page/query performance for the same 7-day, 28-day, and 3-month windows
when available. Bing Search Performance reports impressions, clicks, and query
phrases across supported search surfaces.

Official guidance:
https://www.bing.com/webmasters/help/search-performance-c680da36

### AI Performance

Bing AI Performance is the first-party Microsoft evidence source for IDKMesh
citations in supported AI experiences including Copilot, Bing AI-generated
answers, and selected partner integrations.

Record/export:

- total citations;
- cited pages;
- grounding queries;
- grounding-query to page mappings;
- time-series citation activity;
- intents/topics when available;
- citation share when available.

Keep Bing's evidence boundary intact: citation activity is not ranking,
authority, importance, or proof of causation.

Official guidance:
https://www.bing.com/webmasters/help/ai-performance-9f8e7d6c

Exports are available in CSV/Excel according to Bing's current documentation.
Retain the original export outside the repository if it contains account/private
metadata; commit only the minimum normalized observations needed for the public
evidence ledger.

### Offline AI Performance CSV normalization

Because the authenticated Bing Webmaster REST contract is not fully available
from the public documentation surface, IDKMesh does not guess API endpoints or
payloads. Owner-downloaded AI Performance CSV exports can instead be normalized
offline with:

```bash
python scripts/bing_ai_performance_import.py \
  --kind grounding \
  --input /path/to/bing-grounding.csv \
  --window-start 2026-08-25 \
  --window-end 2026-09-23 \
  --query-column "Grounding Query" \
  --citations-column "Citations" \
  --output results/visibility/bing-ai-grounding.json
```

The export headers are supplied explicitly through CLI arguments. The importer
does not assume Bing's CSV column names.

Supported export shapes:

- `grounding`: grouped grounding phrase + citation count;
- `pages`: IDKMesh page URL + citation count;
- `mapping`: grounding phrase + IDKMesh page URL + citation count;
- `timeline`: date + citation count.

The importer:

- uses only the Python standard library;
- fingerprints the source CSV with SHA-256;
- rejects page rows outside `https://mskazemi.com/idkmesh/`;
- validates the declared date window;
- maps a grounding phrase to the canonical 100-query portfolio only when the
  normalized phrase is an **exact** match;
- does not infer semantic equivalence, ranking, traffic, endorsement, or
  causation.

Keep the raw account export outside the public repository when it contains
private/account metadata. A normalized output may be retained as evidence only
after reviewing that it contains the minimum public aggregate information
needed for the observation.


## Recording evidence in IDKMesh

Every committed search/answer-engine observation must conform to:

`schemas/search-visibility-observation-v0.1.schema.json`

The canonical ledger is:

`evidence/search-visibility/observations.json`

Regenerate:

```bash
python tools/search_visibility_report.py > evidence/search-visibility/REPORT.md
python -m pytest -q tests/test_search_visibility_report.py
```

Evidence classes:

- `webmaster_export` for Search Console / Bing Webmaster exported metrics;
- `index_inspection` for URL inspection/index status;
- `manual_reproduction` for a dated reproducible search/AI-answer observation;
- `referral_log` only when an actual referral observation exists.

Do not store:

- account email addresses;
- OAuth/access tokens;
- cookies;
- private browsing/search history;
- personal identifiers;
- screenshots containing unrelated account data.

## 28-day review loop

1. export Google query/page performance;
2. export Bing query/page performance;
3. export Bing AI Performance citation/grounding data;
4. update only reproducible observations in the ledger;
5. regenerate `REPORT.md`;
6. compare observed queries/grounding phrases with the 100-intent map;
7. improve pages where evidence shows a real gap;
8. avoid creating thin pages for spelling or exact-match variants;
9. record the decision and supporting evidence in issue #665.

## Interpretation rules

- Crawlable is not indexed.
- Indexed is not ranked.
- An impression is not a click.
- A citation is not an endorsement.
- A grounding query is not necessarily the user's exact prompt.
- A short-term change after a content update does not establish causation.
- Different engines and surfaces remain different measurement populations.

## Current external actions

Issue #665 is the visibility/indexing/citation measurement tracker.

Issue #769 is the separate PyPI distribution activation tracker.
