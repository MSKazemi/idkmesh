---
description: "Dated GitHub Actions source, trigger, write-permission, and documentation traceability audit."
---
# Workflow-to-code audit — 2026-10-13

**Initial source revision:** `main@3ae17662500a798bafffeb087bbe3910a07bb8d2`; **refreshed** against `main@0cdf0519dd937f04a4e0a98d077719b659f0e5d6` (after merged [PR #1091](https://github.com/MSKazemi/idkmesh/pull/1091)). **Review mode:** static configuration/source-interface inspection via connected GitHub APIs, not production execution, runner penetration testing, or independent security certification.

## Scope and method

1. Enumerated all **61** directly tracked `.github/workflows/*.yml` definitions at the pinned tree; reviewed each file's declared `on:` events, explicit workflow/job write scopes, and primary code/action entry points.
2. Verified one-to-one workflow filenames in [the operational GitHub Actions reference](../reference/GITHUB_ACTIONS_CODE_MAP.md). Its new deterministic test detects new/removed workflows and changed top-level event keys or declared write scopes.
3. Read the critical write/provider paths in context with their owning source and documentation: `tools/jules_dispatcher.py`, `tools/auto_draft_pr_steward.py`, `scripts/issue_model_router.py`, `tools/benchmark_publication.py`, `tools/openhands_pilot.py`, `tools/submit_indexnow.py`, [the PR Gate](https://github.com/MSKazemi/idkmesh/blob/main/.github/workflows/pr-gate.yml), [the evolution loop](https://github.com/MSKazemi/idkmesh/blob/main/.github/workflows/evolution-loop.yml), and [PyPI release workflow](https://github.com/MSKazemi/idkmesh/blob/main/.github/workflows/publish-pypi.yml).
4. Distinguished explicit GitHub token permissions from external service secrets and outbound network calls. **No** workflow was invoked, rerun, or made to publish/dispatch as part of this documentation pass.

## Concrete code-to-workflow findings

| Boundary | As-built observation | Interpretation limit |
| --- | --- | --- |
| PR quality gate | `pr-gate.yml` runs an unfiltered Python 3.11/3.13 matrix with `scripts/testkit.py unit`, link and schema/API checks | Passing this is necessary under current project merge rules, **not** autonomous integration approval |
| GitHub issue writers | ACE cohort observer, ACE community growth, issue model router, and Jules dispatch declare `issues: write` | Workflow triggers alone cannot be read as consent to dispatch; review source checkout, policy and labels |
| Draft PR steward | `auto-draft-pr.yml` has `pull-requests: write` and checks out trusted main | A Draft PR is a proposal, never acceptance, integration, or a green-check exemption |
| Benchmark publication | `benchmark-publication.yml` has `contents: write` | Git commit/publication privileges are scoped to this workflow; a publication is not stronger scientific evidence |
| Security scanners | CodeQL and OpenSSF Scorecard declare `security-events: write` | Security findings upload is distinct from repository contents-write or acceptance authority |
| PyPI | `publish-pypi.yml` declares job-level `id-token: write`, `attestations: write`, and `contents: write` | OIDC trusted-publisher and environment approvals are external prerequisites; the workflow is not proof that a release published |
| Provider and discovery egress | Jules/OpenHands use provider secrets; IndexNow, search observatory and public discovery probes can contact external endpoints | `contents: read` or no explicit GitHub write scopes **does not** mean offline or no side effects |
| E2E / verification | Frozen `real-*-e2e.yml` workflows run pinned node candidates with controlled Docker setup and separate evaluator-owned source | Not a general arbitrary-agent sandbox and not a merge permit |
| Synthetic research | ACO, emergence, ACE, R1/R2 and verifier-error sweeps execute experimental models | Synthetic trends, simulated accepted defects or read artifacts do not establish external validity |

## Refresh on newer main

The intervening feature commit adds `scripts/visibility_funnel_coverage.py`, its tests and an invocation in `visibility-observatory.yml`. Its trigger families and GitHub write scopes are unchanged. The workflow catalog has been updated to point to the new read-only aggregate report. The PR's sitemap must preserve the new feature's published documentation.

## Checks and evidence

- GitHub source enumeration: 61 directly tracked workflow YAML files, with matching reference rows. Static source/path inspection only.
- Workflow source-linked document and regression test added; **test suite not executed locally** because direct GitHub clone was unavailable in this environment. Exact PR-head GitHub Actions results must be inspected before integration.
- This catalog does **not** evaluate all YAML expression paths and conditions, inherited GitHub platform privileges, permissions of installed external service identities, repository settings, manual environment protections, or every line of each shell/JavaScript step. Those require an independent execution and security review.
- The prior [non-package Python map](../reference/OPERATIONS_MODULE_MAP.md) remains the owner/source index. The new workflow map adds triggering and GitHub token permission context; neither replaces the canonical [capability truth matrix](../CAPABILITY_MATRIX.md).

## Follow-up work

1. **P0:** Review and validate any new `pull_request_target`, `workflow_run`, or GitHub-write job at exact head, especially checkout refs, tainted input handling, condition guards and external credentials. Pin action revisions and retain static guards.
2. **P1:** Build a bidirectional per-code-module test/workflow/evidence matrix. The 61-workflow inventory is complete at the declared-configuration level, **not** the 300+ test module mapping or line-by-line call-graph verification.
3. **P1:** Exercise the documented contributor and API golden paths on a clean interpreter and capture reproducible artifacts; distinguish passing unit gates from controlled Docker integration and external service availability.
4. **P2:** Reconcile experimental outcome claims with preregistered and frozen datasets, then update public research assertions only when independently checked evidence warrants them.

**Provenance:** AI-assisted repository reading and code/doc reconciliation through the connected GitHub interface. No independent human reviewer or production deployment was used for this audit. Related repository stewardship issue: [#471](https://github.com/MSKazemi/idkmesh/issues/471).
