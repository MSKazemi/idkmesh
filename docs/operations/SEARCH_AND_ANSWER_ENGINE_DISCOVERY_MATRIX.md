# Search and Answer-Engine Discovery Matrix

**Date:** 2026-09-23  
**Site:** `https://mskazemi.com/idkmesh/`

This matrix records the discovery path IDKMesh should keep healthy for the major
search and answer engines. It is an engineering checklist, **not a guarantee of
ranking or citation**. Search systems decide independently what to crawl, index,
rank, summarize, or cite.

## Engine matrix

| Surface | Primary discovery path to keep healthy | Repository-controlled support |
| --- | --- | --- |
| Google Search | Googlebot, crawlable HTML, canonical URLs, internal links, XML sitemap | static HTML/Markdown, canonical metadata, topic hub, complete sitemap |
| Gemini / Google AI search experiences | Google Search index plus Google's Gemini-related crawling controls | same Google Search foundation; no separate keyword-stuffing path |
| Bing / Microsoft Copilot | Bingbot, XML sitemap, IndexNow freshness | sitemap + scheduled IndexNow notifier |
| Yahoo Search / Yahoo Scout discovery | Yahoo `Slurp` plus Bing-supplied search infrastructure; open-web crawl/index signals | explicit Slurp robots/HTTP probe, Bing/IndexNow coverage, sitemap, canonicals |
| ChatGPT search | `OAI-SearchBot` plus public crawlable/indexable pages | static pages, direct answers, topic hubs, `llms.txt` supplement |
| Claude web search | `Claude-SearchBot`; user-directed retrieval may use `Claude-User` | public static content and answer-oriented topic pages |
| Perplexity | `PerplexityBot`; user-directed retrieval may use `Perplexity-User` | public static content, topic/Q&A structure, sitemap |
| DuckDuckGo | `DuckDuckBot` plus downstream index/search sources | explicit DuckDuckBot robots/HTTP probe, crawlable static HTML, sitemap |
| Apple Search / Siri / Spotlight | `Applebot` | explicit Applebot robots/HTTP probe, semantic static HTML, metadata, sitemap |
| Brave Search / AI Answers | Brave intentionally does not advertise a differentiated crawler user agent; Googlebot crawlability is a prerequisite | Googlebot/robots/noindex health plus crawlable static HTML and sitemap |
| Other search/answer engines | open-web standards | semantic HTML, crawlable links, canonical URLs, sitemap, evidence-linked content |

## Current content architecture

The public discovery architecture deliberately separates three layers:

1. **100 semantic query intents** in `config/seo-topics-v1.json`;
2. **10 substantial topic pillars** in `docs/topics/`;
3. **100 explicit natural-language questions** — ten per pillar — so
   conversational search systems can retrieve concise passages answering the
   same underlying intents without creating 100 thin doorway pages.

The machine-readable query list is for measurement and maintenance. It is not
published as a meta-keyword dump.

## Crawler health contract

After deployment, `tools/check_public_discovery.py` should be able to verify:

- domain-root `robots.txt` is reachable;
- the IDKMesh sitemap is reachable and contains the topic hub;
- the homepage returns real IDKMesh content to representative search/answer
  crawler user agents rather than a block, challenge, or empty shell;
- the topic hub is publicly reachable;
- no tested crawler receives a `403`, `429`, or crawler-specific decoy page.

The scheduled workflow is a **visibility regression monitor**, not a ranking
monitor. A green run means the public site is technically retrievable from a
GitHub-hosted network path; it does not mean an engine has indexed or cited it.

## Representative crawler identities

The monitor uses representative current user-agent identities for:

- `Googlebot`
- `bingbot`
- Yahoo `Slurp`
- `DuckDuckBot`
- `Applebot`
- `OAI-SearchBot`
- `Claude-SearchBot`
- `Claude-User`
- `PerplexityBot`
- `Perplexity-User`

Crawler identities can change. Vendor documentation is the source of truth; do
not freeze a user-agent string as a permanent protocol guarantee.

## Vendor guidance checked

- Google generative-search optimization:
  https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
  - Google clarified in June 2026 that `llms.txt` is not needed for Google Search and does not positively or negatively affect Google visibility/rankings; IDKMesh keeps it only as a supplement for systems that choose to use it.
- Google crawler / Gemini control overview:
  https://developers.google.com/crawling
- OpenAI publisher/developer discovery FAQ:
  https://help.openai.com/en/articles/12627856-publishers-and-developers-faq
- Anthropic crawler controls:
  https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler
- Perplexity crawler documentation:
  https://docs.perplexity.ai/docs/resources/perplexity-crawlers
- Bing sitemap + AI-search freshness guidance:
  https://blogs.bing.com/webmaster/2025/7/Keeping-Content-Discoverable-with-Sitemaps-in-AI-Powered-Search/
- Yahoo Search crawler guidance (`Slurp`) and Bing-powered search-result guidance:
  https://help.yahoo.com/kb/SLN22600.html
  https://help.yahoo.com/kb/SLN2245.html
- DuckDuckGo crawler guidance:
  https://duckduckgo.com/duckduckgo-help-pages/results/duckduckbot
- Applebot search / Siri / Spotlight / AI-context guidance:
  https://support.apple.com/119829
- Brave Search crawler guidance (no differentiated user agent; Googlebot crawlability prerequisite):
  https://search.brave.com/help/brave-search-crawler

## Visibility evidence loop

Crawler eligibility is only the input. Actual visibility is recorded separately
under the versioned evidence contract in
`schemas/search-visibility-observation-v0.1.schema.json`.

The canonical ledger is
`evidence/search-visibility/observations.json`; its deterministic report is
`evidence/search-visibility/REPORT.md`. This prevents a manual AI-answer check,
a Search Console impression, an index inspection, and a Bing citation from being
collapsed into one misleading score.

For the Microsoft ecosystem, Bing Webmaster Tools now exposes first-party AI
Performance data for citations across Copilot, Bing AI-generated answers, and
selected partners. Its 2026 preview includes cited URLs and grounding queries,
and later preview additions include intents, topics, citation share, and compare.
Those observations should be recorded as `webmaster_export` evidence rather
than reconstructed by scraping result pages.

Repository evidence location:
https://github.com/MSKazemi/idkmesh/tree/main/evidence/search-visibility

## What this does not solve

Technical crawl eligibility cannot manufacture authority. Competitive visibility
still depends on useful content, independent references/backlinks, real users,
repository adoption, reproducible research, and observed engagement. Track those
outcomes in issue #665 rather than asserting them from configuration.
