# SEO / AEO / GEO Discovery Plan — 100 Query Intents

**Date:** 2026-09-22  
**Scope:** public documentation at `https://mskazemi.com/idkmesh/`  
**Machine-readable map:** `config/seo-topics-v1.json`

## Objective

Make IDKMesh easy to discover for the most important questions around AI-agent
verification, multi-agent orchestration, coding-agent review, evaluator
reliability, provenance, governance, interoperability, and verification-first
agentic software engineering.

This is an **eligibility and authority-building plan, not a ranking guarantee**.
Search engines and answer engines choose what to crawl, index, rank, quote, or
cite. The repository can make pages technically eligible, useful, specific,
well-linked, current, and easy to attribute; it cannot force a top result.

## Why 10 pillar pages instead of 100 exact-match pages

The target map contains exactly **100 unique query intents** in ten semantic
clusters. Closely related phrasings map to one useful canonical topic page.

That avoids doorway pages and keyword stuffing. Each target page:

- answers the topic directly in the opening paragraph;
- explains the practical model, not only a definition;
- includes concise question-and-answer sections for conversational search;
- links to executable contracts, experiments, architecture, or governance;
- states evidence boundaries where a claim could otherwise be overstated;
- links back to the topic hub and related topic pages.

The target phrases are retained in `config/seo-topics-v1.json` for measurement,
not dumped onto public pages as a keyword list.

## The ten semantic clusters

1. AI agent verification and validation
2. Multi-agent orchestration and coordination
3. AI code review and coding-agent verification
4. LLM-as-a-judge reliability
5. Verifier panels and independent review
6. Human oversight and agent governance
7. AI provenance, evidence, and reproducibility
8. MCP, A2A, and agent interoperability
9. Verification debt, backpressure, and agent scaling
10. Verified swarm and agentic software engineering

The public hub is `docs/topics/README.md`, published at
`https://mskazemi.com/idkmesh/topics/`.

## Discovery surfaces

### Google Search, Gemini-grounded search, AI Overviews, and AI Mode

Keep pages indexable, crawlable, useful to humans, internally linked, and
consistent about titles, descriptions, canonical URLs, and structured data.
Google's current generative-search guidance says the same core Search indexing
and quality systems remain the foundation for generative features.

Primary references:

- https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
- https://developers.google.com/search/docs/appearance
- https://developers.google.com/search/docs/appearance/structured-data/breadcrumb

### Bing, Copilot, and engines consuming standard web indexes

Keep the XML sitemap complete, use truthful per-page `lastmod`, maintain
crawlability, and use IndexNow for faster notification when important content
changes. Bing explicitly recommends sitemaps plus IndexNow for AI-powered search
freshness.

Primary references:

- https://blogs.bing.com/webmaster/July-2025/Keeping-Content-Discoverable-with-Sitemaps-in-AI-Powered-Search
- https://www.bing.com/webmasters/help/sitemaps-3b5cf6ed
- https://www.indexnow.org/

### ChatGPT search

The domain-root crawler policy must continue to allow `OAI-SearchBot`. OpenAI
states that any public website can appear in ChatGPT search and recommends
allowing that crawler so content can be discovered, summarized, cited, and
linked.

Primary reference:

- https://help.openai.com/en/articles/12627856-publishers-and-developers-faq

### Claude search and user-directed retrieval

The domain-root crawler policy must continue to allow `Claude-SearchBot` and
`Claude-User` when search/retrieval visibility is desired. Anthropic documents
those separately from `ClaudeBot`, which is used for model-development
crawling.

Primary reference:

- https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler

### Perplexity and other answer engines

Keep the same pages public, server-rendered, indexable, citation-friendly, and
reachable through ordinary links and the sitemap. The 2026-09-20 repository
audit already verified that the domain-root robots policy allowed
`PerplexityBot` and that the homepage returned full static content to crawler
user agents.

`docs/llms.txt` is retained as a supplemental machine-readable navigation
surface. It is not treated as a substitute for normal crawling, indexing,
sitemaps, internal links, or useful page content.

## Content design for answer engines

Each topic page uses a retrieval-friendly structure:

```text
clear title
 -> one-sentence direct answer
 -> practical model / lifecycle
 -> limitations and evidence boundary
 -> 5 common questions with concise answers
 -> links to canonical technical evidence
```

The goal is to make a useful passage independently understandable when a search
or answer engine retrieves only part of the page.

## Internal-link architecture

```text
homepage
  -> /topics/
       -> 10 pillar pages
       -> related pillar pages
       -> canonical repo contracts/evidence

llms.txt
  -> /topics/
  -> 10 pillar pages
  -> core docs/evidence

docs/README.md
  -> /topics/
```

Every new pillar is also present in the XML sitemap.

## Measurement loop

Once sufficient impressions exist, replace semantic priority guesses with
observed data.

Measure at least:

- Google Search Console queries, impressions, clicks, CTR, indexed URLs, and
  generative-AI visibility where available;
- Bing Webmaster Tools query and index coverage;
- referral traffic/citations from ChatGPT, Perplexity, Claude, Copilot, Gemini,
  and other answer engines where referrer data is available;
- backlinks and independent references to the research/tooling;
- which topic pages produce repository visits, installs, issues, discussions,
  reproductions, or contributions.

Do **not** optimize raw impressions alone. The useful outcome is qualified
discovery that leads readers to inspect evidence, run the tool, reproduce work,
or contribute.

## Maintenance rules

1. Keep exactly one primary target page per semantic cluster unless search data
   proves a distinct intent needs its own substantial page.
2. Do not create near-duplicate pages for spelling or phrasing variants.
3. Update the machine-readable map when a query target changes.
4. Keep topic claims within the repository's evidence boundary.
5. Regenerate the sitemap whenever a published page is added or removed.
6. Re-audit crawler access and metadata after material Pages configuration
   changes.
7. Re-rank the 100-query list quarterly from observed search/citation data once
   enough data exists.

## Acceptance criteria for this implementation

- exactly 100 unique target queries exist in `config/seo-topics-v1.json`;
- exactly ten clusters each own ten queries;
- every cluster target resolves to a substantial published topic page;
- the topic hub links every target page;
- homepage, docs map, and `llms.txt` link the topic hub;
- the sitemap declares the topic hub and all ten pages;
- tests fail if the 100-query mapping or topic-page quality contract drifts.
