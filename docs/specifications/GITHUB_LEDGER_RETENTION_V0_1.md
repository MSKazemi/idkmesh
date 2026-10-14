---
description: "C9-H retention and reference policy for the GitHub-native durable ledger: which compact evidence is mandatory and never expires, which raw artifacts may expire and when, how references stay interpretable after expiry, and how ledger growth is bounded without rewriting history."
---
# GitHub Ledger Retention and Reference Policy v0.1

**Status:** experimental C9-H implementation contract  
**Issue:** #597 (slice C9-H), parent #570  
**Authority:** advisory only; it deletes, expires, compacts, rewrites, dispatches, verifies, accepts, integrates, pushes and merges nothing.

## Purpose

GitHub Actions artifacts, logs and caches have finite retention; the dedicated
ledger branch ([C9-G](GITHUB_LEDGER_GITHUB_STORAGE_V0_1.md)) does not expire.
#597 requires that "essential ResultManifest/VerificationResult references
survive Actions-run expiration" and that Actions artifacts are "never the only
copy of evidence required for later interpretation/replay". This slice states
that as a policy and as checks. Code: `idkmesh/github_ledger_retention.py`.

The numbers in the policy (minimum age, size thresholds) are **IDKMesh policy
values**. They are not claims about what GitHub itself retains or enforces.

## Two classes of evidence

| Class | Kinds | Rule |
|---|---|---|
| Durable | `ledger_record`, `admission_record`, `candidate_reference`, `result_manifest`, `verification_result`, `human_decision_record` | retained for the life of the ledger; never expired, compacted or rewritten |
| Transient | `actions_artifact`, `actions_log`, `actions_cache`, `provider_transcript`, `raw_candidate_bundle` | may expire, only under the rules below |

Any other kind is **unclassified** and is retained (fail closed).

## Mandatory compact evidence

`check_run_retention(state, policy)` takes a `RecoveredRunState`
([C9-E](GITHUB_LEDGER_RECOVERY_V0_1.md)) and returns a `RetentionReport` whose
`findings` are empty only when the run carries what its state requires. The
requirements follow the Product Spine invariants:

| State reached | Required reference |
|---|---|
| `candidate_observed` and later | `candidate_reference` |
| `normalized` and later | `result_manifest` |
| `evidence_ready`, `awaiting_human_decision`, `decided` | at least one `verification_result` |
| `decided` | `human_decision_record` |

`cancelled` and `admission_blocked` runs require nothing further, but any
reference they carry is still checked. Failures and cancellations are never a
finding: negative evidence stays visible.

## Keeping references interpretable after expiry

Every carried reference is checked, so that the compact copy is enough once the
raw one is gone:

| Finding | Meaning |
|---|---|
| `malformed_digest` | the digest is not `sha256:` plus 64 lowercase hex characters |
| `unlocatable_reference` | a kind in `require_storage_path` (default: `result_manifest`, `verification_result`, `human_decision_record`) has a digest but no repository-relative path |
| `unsafe_path` | the path fails the same safe-path rules as the C14-C durable evidence link (no absolute, empty, `.`/`..` segments, backslashes, control characters) |
| `transient_locator` | the path contains a transient runner segment (default `_temp`, `_work`, `_actions`, `actions-artifacts`, `artifacts`, `runner`, `tmp`, `cache`), so it points into a location that does not outlive the runner |

`transient_locator` is a path-shape heuristic, not proof of where a file lives;
the segment list is part of the policy. A digest or reference is not a verdict.
Findings carry the slot name and a fixed message and never echo the offending
value.

## Raw artifact expiry

`plan_artifact_expiry(artifacts, referenced_digests=, durable_digests=, now=, policy=, active_run_ids=)`
returns one `ExpiryDecision` per raw artifact. It never expires anything; the
caller owns deletion. `now` is passed in (no hidden clock) and must be timezone
aware. The first matching rule wins:

| Decision | Condition |
|---|---|
| `retain_durable_kind` | the kind is durable |
| `retain_unclassified` | the kind is not a known transient kind |
| `retain_active_run` | its `run_id` is in `active_run_ids` (still being observed) |
| `retain_sole_copy` | its digest is referenced by the ledger and is not in `durable_digests` |
| `retain_young` | younger than `transient_min_age_days` (default 30), or created in the future |
| `may_expire` | none of the above |

`durable_digests` is the subset of referenced digests the caller has *confirmed*
present in the durable store. Confirming that is the caller's job; this module
only refuses to let a raw artifact be the sole copy of referenced evidence.

## Bounded ledger growth, without rewriting

`assess_ledger_size(total_bytes, record_count, policy)` compares ledger size with
`ledger_warn_bytes` (default 100 MiB) and `ledger_limit_bytes` (default 500 MiB)
and returns `ok`, `warn` or `exceeded` with the only remedy the policy offers:
`none`, `plan_new_shard`, or `operator_decision_new_shard`. Deleting, compacting
or rewriting ledger history is never a remedy; C9-C's linear, never-rewritten
history and #597's "no history rewrite to hide failed/cancelled attempts" stand.
Sharding itself is not implemented here.

## Policy parsing

`RetentionPolicy.from_mapping` is strict: `schema_version` must be
`github-ledger-retention-policy-v0.1`, unknown keys are refused, integers are
bounded (`bool` is not an integer), `require_storage_path` may name only durable
kinds, and the warn threshold must be below the limit. There is no policy file on
disk yet; the defaults are in code.

## Non-goals

This slice does not delete or expire any artifact, call the GitHub API, read a
clock, confirm that a path actually exists in the ledger branch, implement ledger
sharding, or grant any authority. It also does not prove provider-side evidence
retention beyond the compact references held in ledger records. Wiring these
checks into a scheduled workflow is future work and would need its own
authority review.
