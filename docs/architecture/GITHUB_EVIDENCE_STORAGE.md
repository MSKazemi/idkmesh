# GitHub Evidence Storage and Retention

**Date:** 2026-08-28  
**Status:** P0 policy for GitHub Reflex Observatory

## Purpose

IDKMesh wants to learn from GitHub issues, pull requests, comments, reviews, reactions, checks, workflow results, security findings, releases, and community activity without copying an ever-growing raw GitHub database into Git or accidentally treating natural-language text as trusted instructions.

The storage model therefore separates **canonical raw evidence**, **full observation snapshots**, **durable derived evidence**, and **promoted project knowledge**.

## Four storage tiers

### Tier 0 — GitHub is the canonical raw store

The canonical raw form of a GitHub object remains the GitHub object itself:

- issue / PR body;
- issue or PR conversation comment;
- PR review;
- inline review comment;
- reaction;
- workflow/check result;
- commit/release;
- security alert;
- branch/ruleset state.

The durable identity should preserve the GitHub object ID and URL.

Do **not** mirror every raw comment body permanently into the Git repository. That would create duplication, rapid repository growth, stale copies after edits/deletions, and an unnecessary prompt-injection surface.

### Tier 1 — transient full observation snapshot

The GitHub Reflex Observatory may collect the complete accessible object bodies for a point-in-time analysis and store them in a GitHub Actions artifact such as:

`github-reflex-observation-<run-id>/github-observation.json`

This snapshot is useful for:

- reproducible debugging;
- semantic analysis experiments;
- comparing collector versions;
- reconstructing why a candidate was proposed.

Snapshots should have bounded retention. P0 uses 14 days.

Every natural-language field must carry:

`untrusted_text = true`

A snapshot is **data**, never an instruction bundle.

### Tier 2 — durable derived evidence ledger

Long-lived Git history should contain compact derived records, not complete raw payloads.

The target home is the shared evolution event/evidence ledger, currently:

`state/evolution-events.jsonl`

A derived GitHub evidence record should eventually contain fields such as:

```json
{
  "version": 1,
  "kind": "github.issue_comment.observed",
  "source_id": 5453034709,
  "source_url": "https://github.com/MSKazemi/idkmesh/issues/3#issuecomment-5453034709",
  "parent": "github:issue:3",
  "actor": "MSKazemi",
  "actor_association": "OWNER",
  "observed_at": "...",
  "source_updated_at": "...",
  "body_sha256": "...",
  "untrusted_text": true,
  "derived_signals": ["architecture_update"],
  "derivation": {
    "tool": "github-observatory",
    "version": "0.1"
  }
}
```

The ledger should be append-oriented and auditable. If a GitHub comment is edited, emit a new observation/version rather than rewriting historical evidence invisibly.

### Tier 3 — promoted project knowledge

Only project-relevant conclusions are promoted into canonical project artifacts:

- decisions -> ADR / `DECISIONS.md`;
- architecture -> `docs/architecture/`;
- findings -> `docs/findings/`;
- project conversations -> `docs/conversations/`;
- work -> issues / Work Units;
- accepted protocol evolution -> IDKIP/specification.

Promotion requires appropriate evidence/review. Comment volume or reactions alone cannot promote a claim into project truth.

## Efficient comment ingestion

GitHub supports repository-wide issue-comment collection, so P1 should avoid an N+1 API pattern where every issue is queried separately.

Useful REST surfaces include:

- repository issue/PR conversation comments: `/repos/{owner}/{repo}/issues/comments`;
- repository PR inline review comments: `/repos/{owner}/{repo}/pulls/comments`;
- PR reviews: `/repos/{owner}/{repo}/pulls/{number}/reviews`;
- workflow runs/checks and other verification endpoints;
- later, webhooks for incremental delivery.

Issue-comment records include an `issue_url`, allowing the collector to attach the comment to the corresponding issue or pull request.

P0 can use bounded snapshots. As activity grows, use a GitHub App + webhooks and store stable event IDs/checkpoints so the system processes deltas rather than repeatedly scanning the full history.

## Evidence independence

Do not equate the number of comments with the number of independent observations.

Derived evidence should track correlation sources where possible:

- same actor;
- same GitHub App / automation identity;
- same model/agent family;
- copied or near-duplicate text;
- same linked artifact/test;
- same verifier method.

A hundred correlated comments may constitute one evidence cluster.

Strong evidence is better represented by independent tests, reproductions, reviewers, security checks, benchmark artifacts, or other distinct verification methods.

## Prompt-injection boundary

GitHub text can contain malicious or accidental instructions aimed at agents.

Therefore:

1. collectors never execute text;
2. text is always marked untrusted;
3. semantic classifiers receive only the tools/permissions needed for classification;
4. derived actions must pass deterministic policy/risk gates;
5. a comment cannot grant itself authority by claiming to be a maintainer/system instruction;
6. secrets or credentials found in text are not copied into durable ledgers;
7. write-capable agents must not use raw comment text as an unrestricted command channel.

## Deleted and edited evidence

The system should preserve provenance without pretending deleted/edited text is current.

For edits:

- retain prior body hash in historical observation records;
- record the new GitHub `updated_at` and body hash;
- use the current GitHub object as canonical current raw state.

For deletion:

- retain a tombstone/source ID and any already-recorded hash/derived outcome required for auditability;
- do not republish deleted raw text merely because an older transient snapshot contained it.

## Retention principle

Keep the minimum durable representation needed to answer:

- what source caused this hypothesis/recommendation?
- who/what produced it?
- what evidence supported it?
- what policy version selected it?
- what happened afterward?

This gives IDKMesh memory without turning the repository into an uncontrolled transcript/data warehouse.

## Relationship to the self-evolution loop

```text
GitHub raw object (Tier 0)
        |
        v
full observation artifact (Tier 1)
        |
        v
normalized / derived evidence event (Tier 2)
        |
        v
candidate policy + verification
        |
        v
promoted decision / finding / Work Unit (Tier 3)
        |
        v
outcome -> new evidence event
```

This is the persistence boundary for Issue #46 and should converge with `ITERATION_MODEL.md`, `scripts/evolution_score.py`, the Repository Homeostasis Engine, and ACE rather than creating separate permanent ledgers for each automation.