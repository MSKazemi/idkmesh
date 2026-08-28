# Post-merge evolution hardening

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Owner direction

Continue professional repository work, build a strong GitHub-native evolution system from the mathematical/biological/control/graph ideas developed throughout the project, expose externally blocked work as public issues, and preserve useful chat-derived decisions/results in the repository.

## Canonical state reached

PR #148 merged the current mathematical composition:

```text
persistent Bayesian history (#137)
 + recomputed live Repository Evolution Observatory (#144)
 + live Pareto/UCB Repository Mathematical Portfolio (#143)
 -> conjunctive non-compensation control (#148)
```

The conjunctive controller preserves the hard invariant that current blockers cannot be offset by historical Bayesian confidence. GitHub still reports `main` unprotected, so the truthful current posture remains `GUARD` and issue #35 remains the external administrative gate.

## Important timing detail

During review of #148, an artifact-minimization defect was identified and fixed on the PR branch, but #148 merged concurrently **before that fix and the final chat record reached the merged head**.

The project therefore did not claim the correction was already on `main`.

A small post-merge hardening branch was created from exact merge commit:

`99e6c36f02a8eaeba417c433ccb02f6d599df45e`

## Artifact-minimization finding

The Repository Mathematical Portfolio constructs a temporary snapshot containing issue/PR bodies because its deterministic classifier/reference logic currently uses that text.

The merged workflow copied that snapshot into the retained replay artifact.

This duplication is unnecessary. Public source text is still untrusted text, and the derived portfolio output/state is sufficient for the retained checkpoint contract.

The hardening changes the boundary to:

```text
raw public issue/PR text
 -> ephemeral /tmp snapshot
 -> deterministic portfolio calculation
 -> derived checkpoint only
```

The uploaded checkpoint now excludes `repository-snapshot.json`, and the workflow explicitly asserts that it is absent before upload.

A normative note was added at:

`docs/architecture/EVOLUTION_ARTIFACT_MINIMIZATION.md`

## Project-memory distinction

Artifact minimization does **not** weaken the standing chat-to-repository preservation rule.

There are two different classes of text:

1. arbitrary external GitHub issue/PR/comment input, which should be retained only when a versioned evidence contract requires it;
2. curated IDKMesh project decisions/reasoning, which should be deliberately preserved under `docs/conversations/` and promoted into canonical code/docs/issues when they change the project.

This turn is itself preserved through this record plus the workflow/architecture changes it produced.

## External work that automation cannot substitute for

- #35: actual GitHub-enforced protection/ruleset for `main`;
- #138: genuinely separate human review of the canonical node PR #91.

The project should continue creating or updating bounded issues when a required action needs admin authority, physical evidence, or independent human judgment that automation cannot honestly provide.

## Supersession/convergence rule reinforced

Multiple evolution PRs appeared concurrently during the turn (#139, #142, #146, #148). The professional rule remains:

> integrate before reinventing; keep one canonical responsibility per layer; close stale intermediate branches once their unique value is preserved elsewhere.

The correct response to concurrent stronger work is convergence, not branch ownership.

## Next evidence step

The post-merge hardening itself must go through normal PR CI/review. It should not be directly written to `main` merely because #148 already merged.

After the control-plane mechanics stabilize, the next important mathematical improvement should be **empirical calibration from delayed outcomes**, not another new controller: connect retained predictions/recommendations to regressions, reverts, verifier disagreements, review latency, benchmark movement, newcomer completion, contributor retention, security findings, and time-to-verified-useful-work.
