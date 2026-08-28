# GitHub Pages Front Door — Activation Runbook

**Status:** prepared repository-side source; GitHub Pages remains an explicit repository-owner/admin activation.

The public landing page source is:

`docs/index.html`

It is intentionally dependency-free: no JavaScript, external fonts, analytics, trackers, package build, or second documentation framework is required.

## Purpose

The page is a short first-contact surface for visitors who do not yet understand the full repository. It should answer only:

1. what is IDKMesh?;
2. why does it exist now?;
3. what can someone do in about 15 minutes?;
4. what evidence already exists?;
5. where is the live work?.

Canonical technical and project documentation remains in the repository. The Pages site must not become a competing source of truth.

## Owner activation

After the landing-page PR is merged and reviewed:

1. open repository **Settings → Pages**;
2. choose **Deploy from a branch**;
3. select branch `main`;
4. select folder `/docs`;
5. save;
6. wait for GitHub to publish the site;
7. set the repository homepage field to the published Pages URL;
8. verify the public page from a logged-out/private-browser session.

Do not configure a custom domain for the first experiment unless there is a concrete need.

## Post-activation checks

Verify that:

- the published page loads without authentication;
- the three current contribution links resolve to open/relevant GitHub surfaces;
- repository, README, CONTRIBUTING, and docs-map links resolve;
- mobile layout remains readable;
- no external trackers/scripts are loaded;
- the page does not claim production readiness or external adoption without evidence.

Then update issue #173 with the exact published URL and observed repository metadata.

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

The immediate experiment succeeds when at least one genuinely external person reaches a bounded project surface through the public front door and leaves an inspectable question, claim, review, or contribution.

Related: #10, #109, #167, #173.
