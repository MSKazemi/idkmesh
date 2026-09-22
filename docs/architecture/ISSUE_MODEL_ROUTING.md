# Issue-to-Model Routing Policy

**Status:** proposed deterministic routing control for GitHub issues  
**Model catalog checked:** 2026-09-22  
**Core rule:** choose the cheapest capable tier, but never use cost to bypass a risk or human-evidence gate.

## Purpose

IDKMesh should not send every issue to the largest model, and it should not send high-impact work to a small/free model merely because capacity exists. The router therefore makes two independent decisions:

1. **Capability tier** — how much model/reasoning capability is required?
2. **Authority** — may an owner-controlled AI satisfy the issue, or is human/external evidence required?

These axes are deliberately separate. A peak model may be technically capable of writing an audit, but it cannot satisfy an issue whose acceptance criterion is a genuinely independent human witness.

The router writes planning labels only. It does **not** dispatch a provider, approve code, choose a winning patch, push to `main`, or merge.

## Capability tiers

| Tier | Meaning | Typical work |
| --- | --- | --- |
| `T0` | deterministic | workflow-maintained state, scripted checks; no LLM required |
| `T1` | small | one-module tests, tiny bug fixes, mechanical docs |
| `T2` | standard | bounded multi-file tooling/features with explicit tests |
| `T3` | strong | cross-cutting implementation, architecture-aware work, broad synthesis |
| `T4` | peak | core orchestration/control plane, research methodology, statistical inference, release/security/governance |

The dated provider examples live in `config/llm-routing-policy.json`. They are examples, not architectural constants. Current catalog entries include small/standard/strong/peak mappings for OpenAI, Anthropic, and Google, plus a Jules lane.

Official references are recorded in that config:

- OpenAI models: https://developers.openai.com/api/docs/models
- Anthropic model lifecycle: https://docs.anthropic.com/en/docs/about-claude/model-deprecations
- Gemini models: https://ai.google.dev/gemini-api/docs/models
- Jules task dispatch: https://jules.google/docs/running-tasks/

## Jules is a lane, not a tier

Jules can consume GitHub issues through the literal `jules` label. The router intentionally never adds that dispatch label automatically.

For bounded `T1`/`T2` coding tasks it may add:

```text
agent:jules-eligible
```

A separate human or dispatcher may convert eligibility into the real `jules` label only after checking for duplicate work, an existing claimant/PR, current capacity, and repository policy.

This also avoids assuming that the model behind a managed coding agent is permanently fixed.

## Authority labels

| Label | Meaning |
| --- | --- |
| `authority:agent-candidate` | An AI may create a bounded candidate; normal verification/review still applies. |
| `authority:human-required` | Human/external evidence is part of acceptance; owner-controlled AI cannot satisfy it. |
| `authority:human-gate` | Agent work is useful only after/alongside a named human governance/evidence gate. |
| `authority:deterministic` | Prefer workflow/script maintenance; do not dispatch an LLM. |

Model labels are:

```text
model:t0-deterministic
model:t1-small
model:t2-standard
model:t3-strong
model:t4-peak
model:none
```

## Deterministic routing algorithm

The implementation is `scripts/issue_model_router.py`.

### 1. Apply reviewed current-issue routes

`config/issue-model-routing-overrides.json` contains the reviewed route for every open issue at the 2026-09-22 checkpoint. Overrides are auditable policy, not an LLM prediction, and should change when the issue changes materially.

### 2. Apply hard authority gates

Before complexity scoring:

```text
if acceptance requires independent human/external observation:
    authority = human_required
    model = none
elif issue is workflow/script-maintained state:
    authority = deterministic
    model = T0
else:
    authority = agent
```

This gate always wins over model capability.

### 3. Compute hard capability floors

Signals create minimum tiers that scoring cannot undercut:

- research design, scaling laws, statistical uncertainty -> `T4`;
- core orchestrator/control-plane/release/governance -> `T4`;
- architecture/schema/protocol/workflow/manuscript work -> typically at least `T3`;
- sensitive security/permissions/release surfaces -> at least `T3`, often `T4` by reviewed override.

Negative-scope phrases such as "no schema changes" or "do not change workflows" are ignored when detecting floors. A prohibition must not accidentally escalate a small task.

### 4. Score residual complexity

For new issues without an override:

| Signal | Points |
| --- | ---: |
| body >= 2,500 chars | +1 |
| body >= 7,000 chars | +2 total |
| 6+ checklist items | +1 |
| 16+ checklist items | +2 total |
| 3+ explicit repository paths | +1 |
| 8+ explicit repository paths | +2 total |
| 3+ issue/PR references | +1 |
| 8+ issue/PR references | +2 total |
| 4+ major sections | +1 |
| 8+ major sections | +2 total |
| reasoning-heavy/statistical/causal signals | +3 |
| sensitive/high-impact signals | +3 and at least `T3` |
| explicit `good first issue` without sensitive signals | -2 |

Score mapping:

```text
0..2 -> T1
3..5 -> T2
6..8 -> T3
9+   -> T4

required_tier = max(hard_floor, score_tier)
```

So a cheap model cannot win a low score when a hard research/safety floor requires a stronger tier.

## Provider selection happens after tiering

Capability routing and provider/resource selection remain separate:

```text
required tier
 -> filter provider/model offers by tier + tools + context + data policy
 -> reject stale/unavailable/unauthorized offers
 -> prefer lowest-cost eligible offer
 -> run one bounded attempt
 -> independent verification
 -> escalate only for reasoning/capability failure
```

This composes with the existing Free Resource Mesh: the resource layer answers availability/cost/trust questions; this router answers capability/authority questions. Neither grants merge authority.

For `T4`, the default should be a peak candidate plus a different strong/peak family for criticism/review where practical, followed by deterministic repository checks and any required human gate.

## Escalation state machine

Do not escalate just because an attempt failed. Classify the failure first:

| Failure class | Response |
| --- | --- |
| environment/tool outage | fix/retry at the same tier |
| issue too broad | split the issue; do not buy capability to compensate for bad scope |
| unclear criteria | clarify/specify; if ambiguity is intrinsic, escalate one tier |
| reasoning/implementation error on a clear task | escalate one tier after one bounded failed attempt |
| repeated correlated mistakes | switch provider/model family before adding more identical attempts |
| security/governance/human-evidence boundary | stop at the gate; a larger model does not replace authority |
| `T4` still uncertain | add diverse independent strong/peak review, then preserve uncertainty for human decision |

Recommended transition:

```text
T1 -> T2 -> T3 -> T4 -> T4 + diverse independent reviewer -> human decision
```

Every escalation should record its reason.

## Current open-issue routing snapshot

The complete authoritative map is `config/issue-model-routing-overrides.json`. Important examples:

| Issue | Capability | Authority | Lane |
| --- | --- | --- | --- |
| #1/#2 benchmark research | `T4` | agent candidate | peak + independent reviewer |
| #4 orchestrator MVP | `T4` | human gate | gate, then peak |
| #9 recurring contributors | none | human required | human/community |
| #12 hosted-agent activation | `T4` | human gate | gate, then peak |
| #23/#109 workflow-maintained observatories | `T0` | deterministic | CI/workflow |
| #138/#151/#167 independent reviews | none | human required | human reviewer |
| #401 external clean install | none | human required | external human machine |
| #520 finite-sample uncertainty | `T4` | agent candidate | peak statistical reasoning + independent review |
| #540 argparse smoke test | `T1` | agent candidate | Jules or equivalent small model |
| #541 manual benchmark re-derivation | none | human required | human/manual |
| #542 newcomer-path observation | none | human required | human newcomer |
| #563 focused oracle tests | `T1` | agent candidate | Jules or equivalent small model |
| #564 benchmark family coverage | `T2` | agent candidate | Jules or equivalent standard model |

## GitHub Actions behavior

`.github/workflows/issue-model-router.yml` runs when an issue is opened, edited, or reopened. It:

1. checks out trusted repository code;
2. runs focused router tests;
3. creates/updates only the managed routing labels;
4. classifies the issue;
5. removes stale managed routing labels;
6. applies capability/authority labels;
7. writes the decision and reason to the workflow summary.

Manual `workflow_dispatch` backfills all open issues after a policy change.

The workflow intentionally does not listen to `labeled`/`unlabeled`, avoiding label-update recursion.

## Dispatch contract

A future dispatcher should interpret the labels conservatively:

```text
model:t1-small + agent:jules-eligible
    -> Jules/free small lane is eligible

model:t2-standard + agent:jules-eligible
    -> Jules or standard provider lane is eligible

model:t3-strong
    -> strong provider lane; no automatic Jules dispatch

model:t4-peak
    -> peak provider lane + independent reviewer

authority:human-required
    -> never auto-dispatch as if the agent could close the issue

authority:human-gate
    -> dispatch only when the named gate/dependency permits it
```

Before adding the real `jules` dispatch label, check that no active claimant/PR already targets the same bounded outcome.

## Verification and merge safety

Routing is planning metadata, not correctness evidence. Every candidate still follows `AGENTS.md`, repository test gates, provenance requirements, protected-branch rules, independent verification where applicable, and explicit human/governance decisions where required.

**No model tier is merge authority.**
