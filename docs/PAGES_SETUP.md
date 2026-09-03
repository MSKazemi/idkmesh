# GitHub Pages Front Door — Activation Runbook

**Status:** active and verified as of 2026-08-29; retained as the activation/reverification runbook.

The public site sources are:

- `docs/index.html` — the landing page;
- `docs/pipelines.html` — animated flowcharts of the work/evidence path, the
  two-attempt orchestrator state machine, zero-project-spend compute admission,
  and the PR gate.

Both are intentionally dependency-free: no JavaScript, external fonts, analytics, trackers, package build, or second documentation framework is required.

`pipelines.html` inherits the landing page's palette and system-font stack, and
its motion toggle is CSS-only (`:has()` on a checkbox) precisely so the
no-JavaScript constraint holds. Its diagrams are inline SVG animated with CSS,
so they honour `prefers-reduced-motion` and load no external asset.

The same four flows are maintained in
[`architecture/PIPELINE_DIAGRAMS.md`](architecture/PIPELINE_DIAGRAMS.md), which
carries both an animated SVG rendering (for readers browsing the repository,
where GitHub strips inline SVG and so cannot show this page's version) and the
Mermaid source underneath it. That document is the in-repository source. The
Pages rendering is a presentation surface for the same flows and must not
diverge into a separate contract.

Three renderings of one drawing can drift. Nothing enforces their agreement, so
a change to any flow means changing this page, the SVG files under
`architecture/diagrams/`, and the Mermaid block together.

## Purpose

The page is a short first-contact surface for visitors who do not yet understand the full repository. It should answer only:

1. what is IDKMesh?;
2. why does it exist now?;
3. what can someone do in about 15 minutes?;
4. what evidence already exists?;
5. where is the live work?.

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
