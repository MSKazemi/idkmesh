# Search and Answer-Engine Discovery Matrix

**Date:** 2026-09-24  
**Site:** `https://mskazemi.com/idkmesh/`

This matrix records the discovery path IDKMesh should keep healthy for the major
search and answer engines. It is an engineering checklist, **not a guarantee of
ranking or citation**. Search systems decide independently what to crawl, index,
rank, summarize, or cite.

## Engine matrix

| Surface | Primary discovery path to keep healthy | Repository-controlled support |
| --- | --- | --- |
| Google Search | Googlebot, crawlable HTML, canonical URLs, internal links, XML sitemap | static HTML/Markdown, canonical metadata, topic hub, complete sitemap |
| Gemini Apps / Google AI experiences | Google Search index plus the `Google-Extended` robots.txt product token for Gemini/Vertex AI use and grounding | Googlebot crawl/index foundation plus an explicit Google-Extended robots-permission check; no invented separate Gemini crawler UA |
| Bing / Microsoft Copilot | Bingbot, XML sitemap, IndexNow freshness | sitemap + scheduled IndexNow notifier |
| Yahoo Search / Yahoo Scout discovery | Yahoo `Slurp` plus Bing-supplied search infrastructure; open-web crawl/index signals | explicit Slurp robots/HTTP probe, Bing/IndexNow coverage, sitemap, canonicals |
| ChatGPT search | `OAI-SearchBot` plus public crawlable/indexable pages | static pages, direct answers, topic hubs, `llms.txt` supplement |
| Claude web search | `Claude-SearchBot`; user-directed retrieval may use `Claude-User` | public static content and answer-oriented topic pages |
| Perplexity | `PerplexityBot`; user-directed retrieval may use `Perplexity-User` | public static content, topic/Q&A structure, sitemap |
| DuckDuckGo | `DuckDuckBot` plus downstream index/search sources | explicit DuckDuckBot robots/HTTP probe, crawlable static HTML, sitemap |
| Apple Search / Siri / Spotlight | `Applebot` | explicit Applebot robots/HTTP probe, semantic static HTML, metadata, sitemap |
| Brave Search / AI Answers | Brave intentionally does not advertise a differentiated crawler user agent; Googlebot crawlability is a prerequisite | Googlebot/robots/noindex health plus crawlable static HTML and sitemap |
| Amazon Alexa / Amazon search experiences | `Amzn-SearchBot` for search indexing and `Amzn-User` for user-requested fresh web retrieval | explicit robots + live HTTP probes for both published Amazon search/user agents |
| Meta AI | Meta documents web-backed search/research in Meta AI; no dedicated search crawler identity is assumed from the checked official guidance | manual product observation plus open-web crawlability, self-canonical pages, sitemap, evidence-linked content |
| Mistral Vibe / Mistral search | `MistralAI-Index` for search indexing and `MistralAI-User` for user-requested retrieval | explicit robots + live HTTP probes for both published Mistral search/user agents |
| Grok / xAI web search | Grok's documented web-search tool browses the public web and returns citations; no separate site crawler identity is assumed here | manual/API observation surface plus open-web crawlability, self-canonical pages, sitemap, evidence-linked content |
| You.com Answer / Research | You.com search/answer products operate over a live web index; no separate crawler UA is assumed from the checked product docs | manual/API observation surface plus open-web crawlability, self-canonical pages, sitemap, evidence-linked content |
| Other search/answer engines | open-web standards | semantic HTML, crawlable links, canonical URLs, sitemap, evidence-linked content |

## Current content architecture

The public discovery architecture deliberately separates three layers:

1. **100 semantic query intents** in `config/seo-topics-v1.json`;
2. **10 substantial topic pillars** in `docs/topics/`;
3. **100 explicit natural-language questions** — ten per pillar — so
   conversational search systems can retrieve concise passages answering the
   same underlying intents without creating 100 thin doorway pages;
4. **one generated question map** at `https://mskazemi.com/idkmesh/questions.html`
   that indexes those actual question headings and points every question back to
   its substantial pillar rather than duplicating answers.

The machine-readable query list is for measurement and maintenance. It is not
published as a meta-keyword dump.

## Package and software-index discovery

The installable Python package is a separate discovery surface from the full
research repository. Its metadata in `pyproject.toml` therefore follows a
narrower truth boundary:

- the package description names the shipped AI review-gate / verifier-audit
  capability rather than claiming the unfinished Verified Swarm Runner;
- keywords cover AI-agent verification, AI code review, evaluator reliability,
  verifier panels, evidence, and provenance;
- project URLs point package/software indexes back to the canonical docs, topic
  hub, research atlas, repository, and issue tracker.

This makes package-index discovery reinforce the same semantic graph without
turning repository ambitions into package capability claims.

## Crawler health contract

After deployment, `tools/check_public_discovery.py` should be able to verify:

- domain-root `robots.txt` is reachable;
- the IDKMesh sitemap is reachable and contains the topic hub;
- the homepage returns real IDKMesh content to representative search/answer
  crawler user agents rather than a block, challenge, or empty shell;
- the topic hub is publicly reachable;
- the flagship E017 reproducibility authority page is publicly reachable, self-canonical, indexable, and renders the expected research marker;
- the generated 100-question map is publicly reachable, self-canonical, indexable, present in the sitemap/`llms.txt`, and retrievable with every representative search/answer crawler identity;
- the topic hub, all ten topic pillars, and a normal Jekyll-rendered sentinel page each expose exactly one canonical URL and that canonical equals the URL being monitored;
- the rendered 100-question map contains exactly 100 `#q-...` passage links and each topic pillar renders exactly 10 matching `id="q-..."` answer anchors;
- none of those pages contains a rendered `noindex` directive for `robots`, `googlebot`, or `bingbot`;
- the robots.txt `Google-Extended` product token is not blocked from the homepage, topic hub, or 100-question map;
- no tested crawler receives a `403`, `429`, or crawler-specific decoy page;
- Jekyll social/JSON-LD image paths resolve under the site base path exactly once, never as `/idkmesh/idkmesh/...`.

The workflow is a **visibility regression monitor**, not a ranking monitor. It
runs from GitHub's Pages-native `page_build` event and also has scheduled/manual
recovery paths. On a Pages event it requires a `built` status and binds the
checkout/probe to that event's exact commit. A green run means the public site
is technically retrievable from a GitHub-hosted network path; it does not mean
an engine has indexed or cited it.

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
- `MistralAI-Index`
- `MistralAI-User`
- `Amzn-SearchBot`
- `Amzn-User`

Crawler identities can change. Vendor documentation is the source of truth; do
not freeze a user-agent string as a permanent protocol guarantee.

Robots-only product controls:

- `Google-Extended` — Gemini Apps / Vertex AI Gemini training and grounding
  control. Google documents that it has **no separate HTTP request user-agent
  string**; existing Google crawler user agents perform the crawl, while
  `Google-Extended` is evaluated as a robots.txt product token.


## Vendor guidance checked

- Google generative-search optimization:
  https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
  - Google clarified in June 2026 that `llms.txt` is not needed for Google Search and does not positively or negatively affect Google visibility/rankings; IDKMesh keeps it only as a supplement for systems that choose to use it.
- Google crawler / Gemini control overview:
  https://developers.google.com/crawling
  - Google documents `Google-Extended` as the standalone robots product token
    controlling whether Google-crawled content may be used for Gemini Apps /
    Vertex AI Gemini model improvement and grounding. It does not affect Google
    Search inclusion or ranking and does not have its own request UA string.
- OpenAI publisher/developer discovery FAQ:
  https://help.openai.com/en/articles/12627856-publishers-and-developers-faq
  - OpenAI's current publisher guidance also makes `noindex` operationally important: OAI-SearchBot must be allowed to crawl a page in order to read its meta tags, and a `noindex` directive is the control for preventing even title/link surfacing when a URL is otherwise discovered.
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
- Amazon search/user crawler guidance:
  https://developer.amazon.com/amazonbot
- Mistral search/user crawler guidance:
  https://docs.mistral.ai/robots
- Meta AI web-backed search/research guidance:
  https://about.fb.com/news/2025/04/introducing-meta-ai-app-new-way-access-ai-assistant/
  https://about.fb.com/news/2026/07/meta-ai-muse-spark-doesnt-just-think-it-acts/
- xAI Grok web-search and citation guidance:
  https://docs.x.ai/developers/tools/web-search
  https://docs.x.ai/developers/tools/citations
- You.com live web-search / answer product guidance:
  https://you.com/docs/welcome

## First-party webmaster measurement

The account-owner workflow for Google Search Console and Bing Webmaster Tools is
documented in
[`WEBMASTER_TOOLS_MEASUREMENT_RUNBOOK.md`](WEBMASTER_TOOLS_MEASUREMENT_RUNBOOK.md).

Use the URL-prefix / branch-scoped property
`https://mskazemi.com/idkmesh/`, submit the canonical sitemap, inspect the
eleven topic URLs, export query/page performance, and export Bing AI Performance
citation/grounding data. Commit only normalized observations that satisfy the
visibility evidence schema; do not commit account credentials or private
account data.

## Cross-engine 100-intent observation plan

Technical eligibility and webmaster dashboards do not by themselves show whether
all answer-engine products surface IDKMesh for the intended questions.

Generate a deterministic observation worklist from the **same** canonical
100-query source:

```bash
# One head query from each of the ten clusters across sixteen primary surfaces:
python scripts/search_visibility_observation_plan.py \
  --sample heads \
  --format csv \
  --output results/visibility/answer-engine-heads.csv

# All 100 intents across the same fifteen surfaces:
python scripts/search_visibility_observation_plan.py \
  --sample full \
  --format csv \
  --output results/visibility/answer-engine-full.csv
```

The primary surfaces are Google Search, Bing Search, Yahoo Search, DuckDuckGo,
Brave Search, Apple Siri / Spotlight web answers, Amazon Alexa web answers,
Meta AI, ChatGPT search/answers, Gemini Apps, Claude web search, Perplexity,
Microsoft Copilot, Grok web search, Mistral Vibe, and You.com Answer / Research.

The head sweep contains **160 work items** (10 intents x 16 surfaces). The full
sweep contains **1,600 work items** (100 intents x 16 surfaces).

The generated worklist is **not evidence**. It contains no surfaced result,
position, citation URL, or observation time. Only an actually reproduced result
may be added to the visibility ledger under the schema-backed evidence contract.

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
