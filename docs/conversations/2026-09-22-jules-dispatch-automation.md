# Jules issue dispatch automation and development-speed hardening — 2026-09-22

## Owner requirements

The project owner asked to connect Google Jules to the IDKMesh GitHub repository,
use labels to send suitable simple coding issues to Jules, understand who
triggers jobs and at what frequency, and then make the system more solid while
preserving good development speed and clear documentation.

## Observed pilot

The repository already had a `jules` label and a root `AGENTS.md`. A bounded
pilot was run on issue #540. The Google Labs Jules GitHub App acknowledged the
issue and created PR #561, which later merged. Two additional bounded starter
tasks (#563 and #564) were created with the `jules` label and were acknowledged
by Jules; they subsequently produced PRs #566 and #565 respectively.

This demonstrated that the provider's issue-label integration works, but the
selection/dispatch decision was still manual.

## Durable design decision

Separate **eligibility** from **execution**:

```text
trusted triage -> agent-ready -> repository dispatcher -> jules -> Jules task
```

`agent-ready` is the reviewed repository approval boundary. `jules` is an
execution signal and should normally be added by automation.

The dispatcher must not infer safety by reading arbitrary issue prose. It uses
explicit labels, fail-closed veto labels, bounded concurrency, and normal
protected-branch CI/review.

## Throughput policy

The initial repository-side concurrency cap is four open dispatched issues.
Newly approved issues are dispatched event-first when capacity exists. Closing
a dispatched issue immediately refills freed capacity from the queue. A
30-minute best-effort scheduled sweep repairs missed/waiting dispatches and can
fill up to two slots per sweep.

This is intentionally optimized for a queue of small, reviewable tasks rather
than maximum generated PR volume.

## Human-only boundaries

The automatic path excludes issues requiring genuine human observation,
independent research/evidence, security approval, governance decisions, or
broad decomposition. Those tasks retain separate evidence/authority semantics.

## Implementation artifacts

- `config/jules-dispatch.json`
- `tools/jules_dispatcher.py`
- `tests/test_jules_dispatcher.py`
- `.github/workflows/jules-dispatch.yml`
- `docs/operations/JULES_AUTOMATION.md`

The detailed operational documentation names the actors, labels, triggers,
frequency, failure recovery, speed controls, and no-auto-merge boundary.
