---
description: "Read-only C12 GitHub governance preflight: evaluate normalized protection evidence, lint workflow authority boundaries, and fail closed on missing required observations."
---
# GitHub Governance Preflight v0.1

**Status:** experimental implementation contract  
**Tracking issue:** #607  
**Authority:** observation and admission preflight only; no GitHub administration, dispatch, acceptance, verification, or merge authority.

## Purpose

The C12-A policy in `idkmesh/github_governance_policy.py` names the GitHub
controls IDKMesh expects for each operation. This contract turns that policy
into a deterministic preflight without creating a second security vocabulary.

The preflight answers a narrow question:

> Given trusted observations about repository rules, workflow source,
> environments, CODEOWNERS and connector authentication, is the requested
> operation adequately guarded under the canonical C12 policy?

It does **not** configure GitHub. It never edits rulesets, branch protection,
Actions permissions, environments, secrets, apps, or CODEOWNERS.

## Command

```bash
idkmesh doctor --github examples/github-governance/governance-pass-v0.1.json \
  --operation integration --json
```

Workflow source can tighten the normalized observation:

```bash
idkmesh doctor --github examples/github-governance/governance-pass-v0.1.json \
  --operation cloud_dispatch \
  --workflow examples/github-governance/oidc-cloud-dispatch.yml \
  --json
```

A CODEOWNERS recommendation can be rendered without writing it:

```bash
idkmesh doctor --github examples/github-governance/governance-pass-v0.1.json \
  --codeowners-owner @example/security --json
```

The owner is always explicit. IDKMesh does not infer or hard-code a project
owner/team.

## Input trust boundary

The v0.1 input is a **normalized observation document**, not arbitrary issue or
pull-request text. An observation producer may be a trusted GitHub API adapter,
a repository owner, or a deterministic fixture. The current CLI deliberately
does not use a credential or mutate GitHub to collect it.

Top-level sections are:

- `repository_rules`;
- `workflow_source`;
- `environment_settings`;
- `codeowners`;
- `connector_configuration`;
- `conditions` controlling conditional policy guards;
- optional `unknown_reasons` keyed by canonical C12 guard code.

Observed values are `true`, `false`, or `null`/absent. Unknown fields, duplicate
JSON keys, unsupported versions, and non-boolean observation values fail
closed.

Free-form issue labels, comments, prompts, model output, or provider claims must
not be promoted into this trusted observation boundary.

## Status semantics

Each canonical C12 guard receives one of:

| Status | Meaning |
| --- | --- |
| `PASS` | the applicable guard is observed satisfied |
| `WARN` | a warning/optional guard is absent, or its evidence/applicability is unavailable |
| `FAIL` | a required applicable guard is observed absent |
| `UNKNOWN` | a required guard's evidence or applicability cannot be established |
| `NOT_APPLICABLE` | a trusted condition explicitly says the guard does not apply |

Overall priority is `FAIL` → `UNKNOWN` → `WARN` → `PASS`.

`operation_allowed` is true only for PASS/WARN. FAIL and UNKNOWN are emitted as
blocking states for required guards and block `require_governance()`. A missing
observation or applicability condition on a `warn`/`optional` guard degrades to
WARN instead, so additive hardening never becomes an implicit dependency. A
GitHub plan/API visibility limitation therefore cannot become a false PASS for a
required invariant.

Command exit codes are:

- `0` — PASS or WARN;
- `1` — FAIL or UNKNOWN;
- `2` — malformed/unreadable input or command misuse.

## Workflow-source linter

`lint_workflow_text()` is intentionally dependency-free and conservative. It
checks the security properties needed by C12 without trying to become a full
YAML interpreter:

- workflow-level `permissions: contents: read` default;
- every remote action/reusable workflow pinned to an immutable 40-hex Git SHA
  (Docker references require a digest; repository-local actions are allowed);
- every `actions/checkout` use sets `persist-credentials: false`;
- PR-triggered source does not combine untrusted PR execution with secret
  references or privileged `pull_request_target` head checkout;
- presence of a direct job-level environment binding in the generated workflow
  shape;
- presence of `id-token: write` inside workflow/job `permissions:` for an
  OIDC lane;
- mapped, scalar, and inline-list `pull_request`/`pull_request_target`
  trigger forms, including quoted `on` keys;
- secret-expression references including dot and bracket syntax.

The source checks intentionally reject ambiguous/non-standard shapes rather
than guessing them safe. For example, a key named `id-token` under `env:`
does not count as an Actions permission, and an `environment` variable does
not count as a protected GitHub Environment binding.

When several workflow files are supplied, their booleans are combined
conservatively: one unsafe/unknown workflow cannot be hidden by a safe one.
The linter never executes workflow code.

A conservative false positive is a review request, not permission to weaken the
rule. Complex workflows can instead be inspected by a trusted observation
producer and represented explicitly in the normalized document.

## Secret-bearing and untrusted-PR boundary

For `secret_bearing_dispatch`, `high_risk_dispatch`, and `cloud_dispatch`, the
canonical policy requires the environment/approval boundary before an operation
is allowed. The workflow linter separately checks the untrusted-PR secret
isolation rule.

This repository ships two non-executed reference shapes:

- `examples/github-governance/read-only-lane.yml` — contents-read only, no
  privileged secrets;
- `examples/github-governance/oidc-cloud-dispatch.yml` — explicit protected
  environment and `id-token: write`, with no long-lived cloud credential.

They are examples/fixtures, not evidence that a target repository has those
settings.

## CODEOWNERS recommendation

`render_codeowners_recommendation()` emits an owner-supplied starting point for:

- `.github/workflows/**`;
- `.idkmesh/**`;
- governance/security/evaluator code;
- schemas and security documentation;
- release/package configuration.

The function never writes `.github/CODEOWNERS`, never guesses an owner, and
cannot make GitHub enforce review. Enforcement is a separate repository-rules
observation.

## OIDC preflight

`oidc_preflight()` verifies only workflow shape: `id-token: write` must be
present and obvious long-lived cloud-secret references are rejected. It does
not exchange a token, authenticate to a provider, or prove the target cloud
trust policy is correct.

OIDC remains optional except when the project chooses the `cloud_dispatch`
profile that declares it. A repository without cloud execution must not be
forced to configure OIDC.

## GitHub plan and visibility limitations

C12-A records whether a guard is universal, repository/plan-dependent, or
provider-dependent. The preflight preserves that metadata in every row. If the
connected GitHub identity cannot observe a ruleset, environment setting, or
review feature, report UNKNOWN with the limitation; do not infer the control is
present or absent.

Examples of plan/repository-dependent capabilities include environment review,
CODEOWNERS enforcement, ruleset bypass metadata, and some branch/ruleset
surfaces. The exact availability changes with GitHub plan/repository settings;
this contract does not hard-code a commercial-plan claim.

## Authority ceilings

The report always publishes:

```json
{
  "automatic_admin_mutation": false,
  "ruleset_proves_independent_review": false
}
```

A PASS means only that the provided trusted observations satisfy the declared
preflight. It is not proof that a human reviewer was actually independent, that
a secret is safe, that a cloud identity is correctly configured, or that a
candidate should be accepted/merged.

## Relationship to other owners

- C12 consumes the C12-A policy object; it does not duplicate it.
- C8 bootstrap owns workflow generation and safe re-run behavior. C12 can lint
  those wrappers when they exist but does not generate or apply them here.
- C10/#598 owns GitHub human role/authority policy.
- E3/#670 owns enterprise ActorContext/authorization.
- API-8/#743 consumes these GitHub-first controls for network API security and
  must not create a second GitHub governance model.

## Verification

Focused tests cover good/missing/misconfigured repository observations,
conditional guards, UNKNOWN fail-closed semantics, secret-bearing approval,
untrusted PR + secret combinations, immutable action pins, checkout credential
persistence, read-only least privilege, explicit CODEOWNERS ownership, OIDC
shape, deterministic fixtures, and CLI exit/status rendering.
