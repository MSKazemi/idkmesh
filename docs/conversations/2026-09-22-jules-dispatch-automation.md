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

A separate open PR (#562) proposed a direct Jules REST-API dispatcher with a second queue label and an additional provider secret. During convergence it was found to be both deeply diverged from current `main` and operationally overlapping. It was retired in favor of the native-App dispatcher so the repository has one queue and one execution path rather than duplicate session creation.

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


## Live handoff failure and REST-API migration

Later live observation exposed a provider-boundary assumption that the original
design had not tested: #586 and #587 received the `jules` label from
`github-actions[bot]`, but Google Jules did not acknowledge those label events.
When the owner removed and re-applied `jules`, Jules immediately accepted the
same issues and later created PRs #590 and #592. Earlier owner-applied label
pilots #563 and #564 had also succeeded.

That evidence invalidated the bot-applied label as the unattended transport.
The single automatic dispatcher therefore migrates from:

```text
agent-ready -> github-actions[bot] adds jules -> native Jules App
```

to:

```text
agent-ready
  -> repository capacity/veto checks
  -> resolve connected Jules source
  -> official Jules REST API session
  -> automationMode=AUTO_CREATE_PR
  -> agent:jules-dispatched status
  -> normal IDKMesh CI/review
```

The legacy `jules` label remains only as deliberate manual fallback and still
counts against repository-side capacity during migration, so old work cannot be
double-dispatched. Automatic dispatch requires the owner-managed Actions secret
`JULES_API_KEY`; missing credentials fail closed. The dispatcher also uses a
deterministic repo/issue marker in the Jules session title and checks recent
sessions before creation. Returned 4xx failures release the reservation for a
safe retry; ambiguous network/5xx failures retain the reservation to avoid
creating duplicate provider work.

The Jules REST API is alpha, so its contract is an explicitly monitored external
dependency rather than a protocol constant.
