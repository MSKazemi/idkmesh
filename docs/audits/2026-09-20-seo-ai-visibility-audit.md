# SEO + AI-Visibility Audit — mskazemi.com/idkmesh/

**Date:** 2026-09-20 · **Baseline:** `main` at `999bc26d68913233a37695e7b93c792b20bc6a32`
**Target:** `https://mskazemi.com/idkmesh/` (homepage-first pass, per audit convention)
**Question answered:** is this page visible to search engines and AI answer engines, and if not, why?

## Method

Homepage-first CLI audit: dual/triple-UA fetch (normal browser, `OAI-SearchBot`,
`PerplexityBot`) of the raw HTML, domain-root and sub-path `robots.txt`,
`sitemap.xml` reachability, on-page metadata (title/description/canonical/H1/
JSON-LD/OG), and visible content sampling. **No live browser tools were used in
this pass** — Core Web Vitals and actual Google/Bing index status are explicitly
marked unmeasured below rather than guessed, per audit policy.

## Overall: 86/100 — zero P0 blockers

| Dimension | Score | Weight |
| --- | ---: | ---: |
| Technical SEO | 95/100 | 30% |
| Content quality | 90/100 | 25% |
| LLM-citability | 88/100 | 25% |
| Trust / entity | 65/100 | 20% |

## Root-cause tree result

| Check | Result |
| --- | --- |
| 1. Indexed in GSC? | Unverified this pass (needs a live console check). |
| 2. AI-crawler UA gets real content? | Yes — identical 26,680-byte HTML across a normal browser UA, `OAI-SearchBot`, and `PerplexityBot`. Static Jekyll build, no JS-rendering gap. |
| 3. Edge/WAF returns 200 to AI bots? | Yes — no 403/429 on any tested UA. |
| 4. Any entity/authority signal? | Weak — `Person` schema with `sameAs` exists; off-site corroboration (backlinks, Wikidata, YouTube, community mentions) is essentially absent, expected for a repository created 2026-08-28 (~3 weeks old at audit time). |
| 5. Right content/intent, not thin? | Yes — dense, concrete, honestly-labeled content (see below). |

No hard blocker suppresses visibility. The limiting factor is accumulated off-site authority, which is a time problem, not a configuration problem.

## Evidence

- **`robots.txt` (domain root, `https://mskazemi.com/robots.txt`, HTTP 200):** explicitly allows every major search-index (`Googlebot`, `Bingbot`, `OAI-SearchBot`, `Claude-SearchBot`, `PerplexityBot`, etc.), user-fetch, and training-crawler tier, plus regional engines (Baidu, Yandex, Naver/Daum, Seznam, Mojeek…). Declares `Sitemap: https://mskazemi.com/idkmesh/sitemap.xml` correctly among the other project subpaths. This is close to a reference implementation.
- **Sub-path `robots.txt` (`https://mskazemi.com/idkmesh/robots.txt`):** HTTP 404 — no decoy file; crawlers correctly fall through to the domain-root policy above. (This exact sub-path-robots.txt trap is called out as a common false-positive source in the audit playbook; verified absent here.)
- **`sitemap.xml`:** HTTP 200, reachable.
- **On-page:** `<title>IDKMesh — Verified swarm engineering</title>`, accurate non-boilerplate meta description, self-referencing `<link rel="canonical" href="https://mskazemi.com/idkmesh/">`, no `noindex`, exactly one `<h1>`, viewport tag present, 9 Open Graph tags, one JSON-LD block (`WebPage` + `Person` author with `sameAs` to GitHub/GitLab/homepage, `codeRepository`, `license`).
- **Content:** opens with a direct, confident, un-hedged answer to "what is this and why does it matter" within the first 40 words. Contains a concrete, cited, falsifiable claim ("twenty-five independently seeded test oracles, run over a real 72-candidate corpus, were measured to be worth about one — and the standard N/(1+(N−1)ρ) correction overstated even that by 1.66×... Source: E017") and explicitly distinguishes that real measurement from a bundled example output labeled `"evidence_class": "synthetic"` in its own JSON — most project homepages blur exactly this distinction. Visible freshness date 2026-09-10 (10 days old at audit time).
- **Off-site authority:** `gh api repos/MSKazemi/idkmesh` — 1 star, 1 fork, repo created 2026-08-28. No Wikidata item, no YouTube presence, no independent brand mentions found.

## Findings and fixes

| ID | Severity | Finding | Fix |
| --- | --- | --- | --- |
| SEO-001 | P1 | Core Web Vitals unmeasured — no Lighthouse/PageSpeed tool available in this CLI-only pass. | Run a live Lighthouse pass on `https://mskazemi.com/idkmesh/`. The static 26.7KB HTML payload makes a pass likely, but unconfirmed. **Not applied — needs a live browser check.** |
| SEO-002 | P1 | Actual Google/Bing index status unverified; the last recorded submission (project memory, ~2026-09-10) is 10 days stale at audit time. | Check GSC Page Indexing and Bing Webmaster Tools for the property; re-submit the sitemap if the indexed count looks stale. **Not applied — needs a live console check.** |
| SEO-003 | P2 | Homepage JSON-LD is generic `WebPage`; no `SoftwareSourceCode`/`SoftwareApplication` type for the project itself. | Add a `SoftwareSourceCode` block naming the repo, license, `programmingLanguage: Python`, and the same `Person` author/`sameAs`. **Applied in this change.** |
| SEO-004 | P2 | No FAQ or comparison page — the most-cited AI-answer-engine format — and this overlaps directly with a real onboarding gap already surfaced this session (issue #542: the documented support path leads to a near-empty Discussions Q&A). | Once real questions accumulate in Discussions Q&A, turn the recurring ones into `docs/FAQ.md`, self-contained 80-200 token answers each. **Not applied — needs real questions to answer first; premature to write one now.** |
| SEO-005 | P2 | Off-site authority is the lowest-scoring dimension (65/100) and the real bottleneck: 1 star, 1 fork, no backlinks/Wikidata/YouTube yet. | Not a configuration fix — an accumulation target (genuine community mentions, a YouTube walkthrough, eventual awesome-list inclusion, continuing the contributor-growth funnel already shipped this session). No manufactured signals, per the project's own `docs/community/CONTRIBUTOR_PSYCHOLOGY.md`. **Not applied — ongoing, not a single change.** |

## A suspected finding that turned out not to be one

Earlier in this session, `docs/sitemap.xml` diffs appeared to bump `lastmod` for
unrelated sibling pages inside a touched directory, which looked like a
directory-level-timestamp bug. Checked directly against `tools/build_sitemap.py`
and `git log` before writing it up: the script already derives `lastmod` per
file from `git log -1 --format=%cs -- <path>` (see its own docstring, "not from
the build clock"), and both apparent "bumps" were genuine content changes —
`docs/architecture/README.md` and `docs/planning/README.md` were each actually
edited in the commits that changed their `lastmod`. No fix needed; recorded here
so the same false lead isn't re-investigated later.

## What was deliberately not touched

- `robots.txt` at the domain root — already near-reference-quality.
- `FAQPage`/`HowTo` schema — both lost SERP rich-result eligibility (FAQPage 2026-05-07, HowTo since 2023); not worth adding for a rich result, only relevant for AEO parsing once real FAQ content exists.
- Raw backlink accumulation or any manufactured star/mention — both correlate weakly with AI visibility, and the latter would violate the project's own stated community-growth ethics.

## Follow-up

SEO-001 and SEO-002 need a live browser/console pass (Claude-in-Chrome or manual) and are not applied here. SEO-004 and SEO-005 are ongoing, not single changes.
