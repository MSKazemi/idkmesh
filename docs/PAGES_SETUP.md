# GitHub Pages Front Door — Activation Runbook

**Status:** active. Activation verified 2026-08-29; site surfaces and the
no-JavaScript claim re-measured against the live origin 2026-09-10. Retained as
the activation/reverification runbook.

The public site sources are:

- `docs/index.html` — the landing page;
- `docs/start.html` — the fifteen-minute quickstart: install the CLI, reproduce a
  measured verifier-panel result, run the suite and the contract harness, take a
  bounded task;
- `docs/concepts.html` — seven animated figures explaining bounded Work Units,
  the authority boundary, verification debt, correlated verifiers, effective
  independent votes, acceptance quorums, and the evidence ladder;
- `docs/pipelines.html` — animated flowcharts of the work/evidence path, the
  two-attempt orchestrator state machine, zero-project-spend compute admission,
  and the PR gate;
- `docs/research.html` — the experiment atlas, E011 to E042, each carrying its
  actual result rather than a summary of the programme;
- `docs/library.html` — every document and contract by category, generated from
  the tracked tree so an entry cannot name a file that is not there;
- `docs/topics/` — ten substantial question-oriented topic guides plus a hub,
  rendered by the same Jekyll path as the rest of the Markdown documentation;
- `docs/llms.txt` — a supplemental machine-readable map to canonical project,
  evidence, and topic sources;
- `docs/assets/site.css` — the one shared stylesheet.

The six top-level HTML pages are hand-written and dependency-free: no
JavaScript, external font, analytics, tracker, package build, or second
documentation framework. The only `<script>` element anywhere on them is an
inert `application/ld+json` structured-data block. The Markdown topic guides
are rendered by GitHub Pages/Jekyll like the rest of `docs/**/*.md`.

`pipelines.html` predates the shared stylesheet and keeps its rules inline,
because its diagram primitives are the page; it links no stylesheet and that is
allowed. Every other page loads `assets/site.css` and nothing else. Motion
toggles and the experiment-atlas filter are CSS-only (`:has()` on a checkbox or
radio) precisely so the no-JavaScript constraint holds, and every animation
honours `prefers-reduced-motion`.

## What the no-JavaScript claim does and does not cover

Measured against the live site on 2026-09-10, not assumed:

- the hand-written HTML pages above load no script and no external asset;
- **every other page on the site does.** GitHub Pages runs legacy Jekyll v3.10.0
  with the Primer theme, so each `docs/**/*.md` file is *also* rendered into a
  themed HTML page — and that rendering loads `anchor-js` from
  `cdnjs.cloudflare.com`. `docs/_config.yml` now pins the shared site identity
  used by those generated pages (IDKMesh title/description, canonical site URL,
  repository identity, language, author, and social image) so the long-tail
  documentation no longer inherits only the lowercase repository name. Verified
  live before this configuration was added:
  `https://mskazemi.com/idkmesh/WHAT_IS_IDKMESH.html` returned
  `<meta name="generator" content="Jekyll v3.10.0" />` and a `cdnjs` script tag.

So the constraint is a property of the pages this runbook owns, not of the whole
published origin. Adding `.nojekyll` would make the claim literally true and
would simultaneously strip the theme's canonical, OpenGraph and JSON-LD metadata
from every rendered document — a visibility loss, not a gain. The hand-written
pages therefore carry that metadata themselves.

### What URL a file gets

Measured against the live origin on 2026-09-10, one document at a time:

| source | published as | |
| --- | --- | --- |
| `docs/index.html` | `/idkmesh/` | 200 |
| `docs/<dir>/README.md` | `/idkmesh/<dir>/` | 200 |
| `docs/README.md` | *nothing* — `/idkmesh/README.html` | 404 |
| any other `docs/**/*.md` | `/x`, `/x.html` and `/x.md` | 200, 200, 200 (raw `text/markdown`) |

So an ordinary document gets three URLs, the two HTML forms canonicalising to
`/x.html`; a `README.md` gets its directory's URL instead; and a `README.md` or
`index.md` sitting next to an `index.html` gets no rendered page at all, because
the HTML file has taken that URL. `docs/index.md` is still served raw at
`/idkmesh/index.md`, which is the only trace of it a reader can reach.

A same-origin link to `<doc>.html` therefore resolves while the configured
Jekyll publication path remains active. `docs/_config.yml` now pins the theme
and shared site identity, but adding `.nojekyll` would still remove the rendered
Markdown pages and break those generated `.html` URLs. Hand-written HTML pages
therefore use repository URLs for most canonical technical documents, while the
search-oriented topic cards use absolute public Pages URLs deliberately: those
links are outcome surfaces whose availability must be verified after deployment.

**`docs/index.html` shadows `docs/index.md`.** Jekyll serves the HTML file at
`/idkmesh/` and the Markdown one is never rendered there. An edit to `index.md`
does not reach the live front door: PR #391 (`59d6e39`) pointed `index.md` at
`gate-audit` and the live page continued to contain no mention of it. Edit
`index.html`.

## Directory index convention

A repository directory README and a public website directory index are not the
same publication contract.

When a public URL is intended to resolve at `/idkmesh/<directory>/`, the source
must be `docs/<directory>/index.md` (or `index.html`). Do not rely on
`README.md` being promoted to a directory index by GitHub Pages/Jekyll.

The SEO topic hub follows this rule:

```text
docs/topics/index.md
  -> https://mskazemi.com/idkmesh/topics/
```

The public-discovery monitor checks that URL after the Pages deployment
workflow completes. This rule exists because the first live 100-query rollout
published all ten pillar pages correctly while `/topics/` remained a 404 when
the hub source was named `README.md`.

## Search and answer-engine discovery

The discovery surface is intentionally layered rather than dependent on one
crawler or one vendor:

- `docs/sitemap.xml` declares every published HTML page with truthful per-source
  `lastmod` dates;
- `docs/_config.yml` supplies a consistent IDKMesh identity, canonical origin,
  repository, language, author, and social image to Jekyll-rendered Markdown;
- each hand-written HTML page carries its own canonical, Open Graph, Twitter,
  robots, and JSON-LD metadata;
- `docs/topics/` maps ten substantial topic guides to the 100 semantic query
  intents in `config/seo-topics-v1.json`;
- `docs/llms.txt` is a supplemental machine-readable navigation surface, not a
  substitute for ordinary crawling or indexing;
- `.github/workflows/indexnow-discovery.yml` submits recently changed sitemap
  URLs to IndexNow on a daily recovery schedule. The notification is only a
  freshness hint; it is not evidence that a URL was indexed or ranked.

The implementation and measurement rules are recorded in
[`planning/SEO_AEO_GEO_100_QUERY_PLAN_2026-09-22.md`](planning/SEO_AEO_GEO_100_QUERY_PLAN_2026-09-22.md).
Actual Google/Bing index coverage, search queries, and answer-engine citations
must be measured externally after deployment rather than inferred from repository
configuration.

## What is guarded, and what is not

`tests/test_pages_site_links.py` resolves what no other gate does. IDKGraph T2
(`tools/idkgraph_link_check.py`) reads Markdown only;
`tests/test_local_asset_link_integrity.py` closes T2's non-Markdown hole but
only for links written *inside* Markdown; and `tools/idkgraph_health_checks.py`
scans a suffix allowlist that excludes `.html`. Before that guard existed, a
site page could link to a deleted document, drop its stylesheet, or grow a
navigation bar disagreeing with its siblings, and every gate stayed green.

The guard asserts that every page-relative link resolves against the git index,
every `blob/main` and `tree/main` link names a tracked file or directory of the
right kind, every fragment exists on the page it names, the navigation bar is
identical across pages and reaches all of them, each page is styled and declares
its canonical URL, no page contains executable JavaScript, and no page carries a
Liquid delimiter.

### One stray delimiter takes down the whole site

Jekyll expands Liquid's tags — double-brace output and brace-percent statement
delimiters — **before** Markdown, before the theme, before anything. A fenced
code block does not protect them. Neither does an HTML comment. And the failure
is not scoped to the offending page: the build dies and *nothing* deploys.

This page deliberately does not write those delimiters literally anywhere, which
is why they are described rather than shown. Writing the example out is what
breaks the build, and a runbook that breaks the thing it documents is worse than
one that spells it out in words.

This is not hypothetical. A single GitHub Actions concurrency key documented in
[`architecture/REPOSITORY_MATHEMATICAL_PORTFOLIO_CONCURRENCY.md`](architecture/REPOSITORY_MATHEMATICAL_PORTFOLIO_CONCURRENCY.md)
— a `group:` key interpolating `github.event_name` through Actions' dollar-brace
syntax, which shares Liquid's opening delimiter — arrived with #414 and broke the
site build 58 seconds later. Liquid read the Actions interpolation as one of its
own variables, found no terminator, and stopped.

The last successful build before it was `f4142f9` at `2026-09-09T23:52:36Z`.
Every build after it failed — six of them, `7307b41` through `c798726`, with one
further run cancelled before it started. Nothing published to `docs/` reached the
live site for that whole window. #426 (`d1e2705`) fixed it by wrapping the
snippet in Liquid's raw tags, and the build went green again at
`2026-09-10T01:49:04Z`.

Note what the fix could not rely on: the pull request carried 18 green checks and
none of them was the Pages build. The only evidence that the site could build
again was the deployment run on the merge commit. No repository test noticed, because
`pages-build-deployment` is a GitHub-managed workflow: it is not in
`.github/workflows/`, so a green check wall says nothing about it. Check it with:

```bash
gh run list --workflow=pages-build-deployment
```

Documenting an Actions snippet therefore requires wrapping it in Liquid's raw
tags, or not writing the delimiters at all. The guard for Markdown lives in `tests/test_pages_liquid_safety.py`; the
one for the hand-written `.html` pages and `assets/site.css` is a test in
`tests/test_pages_site_links.py`, because the Markdown scan does not reach them.

There is no repository-owned HTML build step or template engine for the hand-written pages, so the navigation bar is copied
into each page by hand. That is the honest cost of the no-framework constraint,
and it is only safe because divergence is a test failure.

## The pipeline diagrams have three renderings

The four flows on `pipelines.html` are also maintained in
[`architecture/PIPELINE_DIAGRAMS.md`](architecture/PIPELINE_DIAGRAMS.md), which
carries both an animated SVG rendering (for readers browsing the repository,
where GitHub strips inline SVG and so cannot show this page's version) and the
Mermaid source underneath it. That document is the in-repository source. The
Pages rendering is a presentation surface for the same flows and must not
diverge into a separate contract.

Three renderings of one drawing can drift. Nothing enforces their agreement, so
a change to any flow means changing this page, the SVG files under
`architecture/diagrams/`, and the Mermaid block together.

The figures on `concepts.html` are deliberately *not* a fourth rendering of
those four flows. They illustrate concepts — the authority boundary, the
correlation collapse, the evidence ladder — and each one names the experiment or
contract it was read from. Keep it that way: a diagram that restates a pipeline
contract adds a fourth thing to keep in sync.

## Purpose

The page is a short first-contact surface for visitors who do not yet understand the full repository. It should answer only:

1. what is IDKMesh?;
2. why does it exist now?;
3. what can someone do in about 15 minutes?;
4. what evidence already exists?;
5. where is the live work?.

The sibling pages go further than the landing page, but under the same rule:
they present and link, never restate. `library.html` is generated from the
tracked tree and carries no prose of its own beyond a category blurb;
`research.html` gives each experiment one sentence drawn from that experiment's
own stated result and links the record; `start.html` reproduces commands that
were run against the tree before being written down. No page copies a contract,
a schema, or an acceptance rule, so no page can silently disagree with one.

Canonical technical and project documentation remains in the repository. The Pages site must not become a competing source of truth.

## Current live state

Repository evidence recorded in issue #173 confirms:

- Pages enabled from protected `main:/docs`;
- HTTPS enforced;
- repository homepage set to `https://mskazemi.com/idkmesh/`;
- the live page returned the expected IDKMesh landing page;
- the first public research-preview release was published from the same reviewed repository state.

Do not treat this runbook's historical activation steps as evidence that activation is still pending.

### Welcome-discussion pinning is optional

Pinning the welcome discussion (#302) is **presentation polish, not a completion
gate**. The repository API exposes no reliable pin mutation/verification surface,
so pin state cannot be independently witnessed from repository evidence. The
project must not fabricate that witness, and a pin carries no authority,
correctness, security, reproducibility, or external-participation control.

Pinning may still be performed through the GitHub UI as a first-contact usability
improvement. Its absence does not block discovery-surface completion. See
[ADR-0011](decisions/ADR-0011-discovery-surface-completion.md).

## Activation / recovery procedure

If Pages must be recreated or repaired:

1. open repository **Settings → Pages**;
2. choose **Deploy from a branch**;
3. select branch `main`;
4. select folder `/docs`;
5. save;
6. verify GitHub publishes the site;
7. set the repository homepage field to the published Pages URL;
8. verify the public page from a logged-out/private-browser session.

Do not configure a custom domain unless there is a concrete need.

## Post-activation checks

Verify that:

- the published page loads without authentication;
- current contribution links resolve to open/relevant GitHub surfaces;
- repository, README, CONTRIBUTING, and docs-map links resolve;
- mobile layout remains readable;
- no external trackers/scripts are loaded;
- the page does not claim production readiness or external adoption without evidence.

Record materially changed observations in the canonical tracker rather than leaving stale status prose here.

## Maintenance rule

The landing page should change much less frequently than `main`.

Prefer stable contribution categories and canonical trackers over transient PR numbers. If a highlighted issue closes, replace it only with another genuinely open bounded task. Avoid turning the page into a live dashboard; GitHub Issues and repository observatories already serve that purpose.

## Success metric

Do not optimize page views or stars in isolation.

The first useful funnel is:

```text
discover
 -> understand enough to choose a path
 -> open/claim/question a bounded task
 -> produce inspectable evidence
 -> receive review
```

The immediate experiment succeeds when at least one genuinely external person reaches a bounded project surface through the public front door and leaves an inspectable question, claim, review, or contribution. That external-participation evidence remains tracked by the community-growth work (#9, #10, #23, #109) and is not implied by Pages activation.

Related: #9, #10, #23, #109, #167, #173.
