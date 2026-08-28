# Branch and PR convergence postscript

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

This postscript extends `docs/conversations/2026-08-28-branch-pr-convergence-continuation.md` with repository changes that landed while the live branch/PR graph continued moving.

## EvaluatorPlan v0.4 integration completion

Merged PR #171 established the canonical versioned transition semantics:

```text
v0.2 / verifier 0.1.1 = exact added-line equality
v0.3 / verifier 0.2.0 = added-line substring semantics
v0.4 / verifier 0.3.0 = required added + removed line substring transition semantics
```

Candidate code remains non-executed by the metadata-only verifier; the new version is still a static textual proxy, not behavioral proof.

PR #175 then merged the small benchmark-cohort validator routing update for EvaluatorPlan schema v0.4 without changing the burned first-five benchmark or creating a successor cohort.

## Canonical Task-001 calibration extraction

PR #176 was created to extract only the useful Task-001 behavioral/adversarial calibration from divergent closed PR #170 onto the canonical #171 verifier.

Two early #176 runs exposed compatibility assumptions from the old duplicate verifier:

1. the calibration expected a particular finding sentence;
2. it expected a private extension explicitly set to `behavioral_correctness_claim=false`.

Canonical #171 already emitted stronger machine-readable evidence:

- verifier adapter `0.3.0`;
- transition mode `added_and_removed_line_substring_all`;
- evidence id `removed-substring-semantic-observation`;
- `semantic_removed_substrings` diagnostics;
- required/matched removal metrics;
- correctness finding when the unsafe removal transition is missing;
- no positive behavioral-correctness claim.

The final #176 branch wrapper therefore deferred only those two old implementation-shape assertions and replaced them with canonical structured checks. Candidate construction, behavioral matrix, pass/reject expectations, exact source binding, and verifier semantics were unchanged.

Exact final source head:

`2fc8b6391f06e12c769dd2b9db6a375f35f43c0f`

Exact-head checks:

- Task 001 canonical v0.4 calibration `33195020674` / job `98929838420` — success;
- Phase 0 `33195020735` — success;
- IDKGraph `33195020668` — success;
- Evolution `33195020623` — success.

Final calibration matrix:

```text
straightforward candidate:
  metadata verifier   -> passed / accept_candidate
  behavioral matrix   -> all unsafe absolute/traversal paths rejected

inert decoy:
  metadata verifier   -> failed / reject_candidate
  behavioral matrix   -> vulnerable absolute/traversal paths still accepted
```

The summary also records:

```text
metadata_only_verifier_executes_candidate_code = false
behavioral_execution_is_separate_evidence_channel = true
automatic_candidate_selection = false
merge_authority = false
```

PR #176 merged as:

`5bb42560c58fb90a534635ff9dee8e11ccc983c0`

This completes the calibration boundary recorded in issue #157 without introducing a second verifier stack.

## Research leaf #179

PR #179 (`E015: cost-weighted quorum selection`) was reviewed as research-only evidence.

It adds:

```text
weighted_error = (w * false_accept + false_reject) / (1 + w)
```

with unit tests proving `w=1` exactly reproduces the existing balanced metric and that asymmetric false-accept cost can flip the preferred quorum in the tested configuration.

The report explicitly limits the result to the tested q=0.5 versus q=0.7 sweep and documents quorum-rounding effects. It does not change repository scheduling, review, approval, or merge authority.

All relevant exact-head repository checks were green and #179 merged as:

`7a0381696422f8eb79f444f7246a484009372589`

## Latest branch audit

The canonical read-only branch auditor was rerun again after the evaluator/calibration convergence and while #179 was still in review.

- workflow run `33187644986`;
- job `98930236277` — success;
- artifact `9695442734`;
- artifact digest `sha256:f46836b67ad08e5c882b43852c724ec8390dc027b0fc55ac8d91950f1677c743`.

Point-in-time result:

```text
branches observed                      136
non-default branches                   135
cleanup-eligible                        72
direct branch merges allowed             0

canonical                                1
active draft PR                          1
active review PR                         1
integrated via merged PR                66
orphan / no unique commits               6
orphan diverged                          8
post-merge branch moved                  5
closed-unmerged evidence branch          9
closed-unmerged unique work              39
```

The one review PR in that snapshot was #179, which merged after the auditor classified the repository. A fresh open-PR search after the merge showed only draft #159.

This demonstrates why branch audit results are point-in-time decision support rather than deletion authority. Every actual ref deletion must exact-head revalidate immediately beforehand.

The connected GitHub maintenance surface in this session still does not expose a delete-ref operation. Physical retirement of the 72 cleanup-eligible branches was therefore not simulated by force-moving refs. Issue #127 remains the canonical deletion/convergence ledger for a deletion-capable admin pass.

## Remaining canonical worker gate

PR #159 remains the only intentional open integration candidate at the end of this postscript.

Exact replacement head:

`61cafa86f7e0e86343d73182862e3cead1080ab9`

It already has:

- fresh exact-head Node / Phase 0 / randomness / Evolution CI;
- fresh controlled Docker positive + A-E2 acceptance from run `33193838388` / job `98925820770`;
- `all_acceptance_checks_passed=true`;
- `worker_acceptance_authority=false`.

It remains draft because issue #138 still requires a genuinely separate human/reviewer witness. Neither worker success, blob equality to old #91, CI, the acceptance harness, the PR author, nor project automation can manufacture that approval.

## Still-external gates

- issue #35: protect `main` through actual GitHub branch/ruleset settings;
- issue #127: physically retire exact cleanup-safe branches through a deletion-capable admin surface;
- issue #138: separate human review of #159;
- issue #173: repository description/topics/Discussions/Pages discovery settings;
- issue #17: rebuild A2A/MCP interoperability on current canonical contracts rather than merging the stale `interop-runtime-integration` branch.

The repository should continue to optimize for verified durable progress per unit of reviewer/maintainer attention, not raw branch, PR, commit, star, or workflow volume.
