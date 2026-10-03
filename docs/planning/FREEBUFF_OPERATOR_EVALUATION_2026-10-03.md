# Freebuff operator evaluation for IDKMesh

**Status:** operator guidance; not a canonical provider calibration  
**Date:** 2026-10-03  
**Scope:** human-initiated use of Freebuff Cloud/CLI against `MSKazemi/idkmesh`

## Decision

Freebuff is useful **now** as a human-operated external coding worker for bounded IDKMesh issues.

It should **not** be wired into unattended GitHub CI/dispatch as if it were a provider API. Freebuff's current Terms of Service say a human must initiate each session and remain actively present, and prohibit bots/scripts/macros/headless automation from operating the product. If Freebuff later exposes an official automation API with compatible terms, evaluate it through the normal IDKMesh connector boundary instead of scripting the UI.

References:

- https://freebuff.com/
- https://freebuff.com/blog/free-cloud-coding-agent
- https://freebuff.com/terms-of-service
- `config/llm-routing-policy.json`
- `docs/planning/PRODUCT_GOALS_COMPONENT_SLICE_MAP_2026-09-22.md`

## Fit with the existing IDKMesh routing model

IDKMesh already chooses a **capability tier before a provider**:

- T0 deterministic
- T1 small
- T2 standard
- T3 strong
- T4 peak

Freebuff should therefore be treated as another candidate worker surface, not as "the model for IDKMesh".

The repository also keeps these concepts separate:

```text
model capability != coding agent
coding agent != execution backend
worker success != verification
verification != human decision
human decision != merge authority
```

That boundary remains unchanged when Freebuff is used.

## Provisional model-use guide

The table below is operational guidance only. These Freebuff model names are **not yet calibrated IDKMesh tier declarations** and should not be added to `llm-routing-policy.json` as canonical mappings without measured evidence.

| Work class | Suggested first choice | Alternate | Notes |
| --- | --- | --- | --- |
| T1 mechanical/docs/tests | MiMo 2.6 Flash | Solar Mini 4 | Prefer the recommended balanced model for a first pilot; unlimited/cheap models are useful for repetitive edits. |
| T2 bounded multi-file coding | MiMo 2.6 Flash | GLM 5.3 Flash | Good default lane for clear acceptance criteria and normal regression tests. |
| T3 architecture-aware/debugging | DeepSeek V4.1 Flash | MiMo 2.6 Pro | Use when the issue needs broader repository reasoning; re-check scope carefully. |
| T4 control-plane/research/release/security | no single Freebuff model is pre-approved | highest-capability available + separate review | Do not infer T4 from marketing/model naming. Keep the repository's independent-review/human-gate rules. |

A second model can provide useful **advisory review**, but another owner-controlled Freebuff session does not satisfy an issue that explicitly requires independent human/external evidence.

## Recommended first pilot

Use open issue **#901 — Usage examples in `--help` for `idkmesh run` and `idkmesh control-tower`**.

Why:

- currently routed as a T1/small agent-candidate task;
- bounded files and explicit acceptance criteria;
- no open PR was found for #901 at this checkpoint;
- the issue explicitly welcomes a contributor's own coding agent while carrying `do-not-automate` for the repository-owned Jules dispatcher.

Recommended first model: **MiMo 2.6 Flash**.

Paste-ready Freebuff prompt:

```text
Work on MSKazemi/idkmesh issue #901 only.

Before editing:
1. Read AGENTS.md completely.
2. Read CONTRIBUTING.md and the relevant CLI/tests/docs.
3. Refresh current main and record the exact base SHA.
4. Read issue #901 and check for open PRs/comments so you do not duplicate work.

Implementation boundary:
- Add argparse Examples blocks only for the commands named in #901.
- Add/adjust the narrow parser tests required by the issue.
- Update only documentation that actually quotes the affected help.
- Do not rename commands or flags.
- Do not broaden scope into unrelated CLI cleanup.
- Do not merge, approve, or push directly to main.

Verification:
- run the focused pytest command from #901;
- run make smoke;
- run make gate;
- report the exact commands and actual results.

Publication:
- one focused branch/PR;
- include AI/tool provenance: Freebuff + selected model;
- state remaining uncertainty explicitly.
```

## Human-operated workflow

1. Connect `MSKazemi/idkmesh` in Freebuff Cloud (or clone locally and run the Freebuff CLI).
2. Pick one bounded issue that is not already implemented and has no active PR.
3. Select a model appropriate to the task tier.
4. Give Freebuff the issue-specific prompt and repository safety instructions.
5. Inspect the plan before broad edits.
6. Review the Changes pane and terminal output.
7. Require focused tests plus the repository gate appropriate to the diff.
8. Publish one focused PR, not a stream of incremental branch-head updates.
9. Treat the result as an untrusted candidate until normal CI/review completes.
10. Use a different model only as advisory review unless the issue's evidence contract explicitly allows model-based verification.

## Future integration path

If an official Freebuff machine API becomes available and permits unattended automation:

```text
Freebuff provider/API
  -> provider-neutral connector
  -> explicit capability declaration
  -> WorkUnit admission
  -> candidate output
  -> ResultManifest
  -> independent VerificationResult
  -> human/integration authority
```

Do not add UI automation, browser scraping, or a provider-specific coordinator branch as a shortcut.

## Evaluation to run before canonical routing

Before Freebuff model names become formal tier mappings, run a small frozen cohort of representative T1/T2/T3 issues and record:

- success against acceptance tests;
- regression rate;
- wall time;
- model/session consumption;
- number of human interventions;
- scope violations;
- first-pass vs final-pass success;
- cross-model disagreement on review.

Use that evidence to update routing policy rather than choosing a permanent project-wide model.
