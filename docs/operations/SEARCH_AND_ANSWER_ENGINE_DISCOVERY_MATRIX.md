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
| Yahoo and other engines consuming major web indexes | standards-based crawl/index signals | public HTML, robots-compatible crawling, sitemap, canonicals |
| ChatGPT search | `OAI-SearchBot` plus public crawlable/indexable pages | static pages, direct answers, topic hubs, `llms.txt` supplement |
| Claude web search | `Claude-SearchBot`; user-directed retrieval may use `Claude-User` | public static content and answer-oriented topic pages |
| Perplexity | `PerplexityBot`; user-directed retrieval may use `Perplexity-User` | public static content, topic/Q&A structure, sitemap |
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

## What this does not solve

Technical crawl eligibility cannot manufacture authority. Competitive visibility
still depends on useful content, independent references/backlinks, real users,
repository adoption, reproducible research, and observed engagement. Track those
outcomes in issue #665 rather than asserting them from configuration.
