# Open-issue evidence gates — 2026-08-30

**Baseline revision:** `e16a8d0`.
**Tool:** [`tools/issue_evidence_gate.py`](../../tools/issue_evidence_gate.py).

Read this as a snapshot. The numbers below were measured at that revision and
are re-derived on every run of the tool; the tool, not this page, is the current
authority.

## What was inspected, and why

Twenty-one issues are open. Several of them cannot be closed by writing code,
because their own acceptance text names a precondition that is a **measured
property of the repository** rather than a task: a held-out corpus that has to
be collected, an independent reviewer who has to appear, a contributor who has
to come back.

That distinction had been carried in triage prose. Prose rots: it cannot tell
you when a blocker clears, and it cannot be checked by anyone who does not
already trust the person who wrote it. This audit replaces the prose with a
tool that reads evidence surfaces the repository already publishes.

The tool is deliberately narrow about its own authority:

> **It never decides that an issue is blocked.** It evaluates preconditions that
> were each read off an issue's own text, and it fails when a registered
> precondition has become *met* — that is, when the registry has gone stale and
> the issue can be worked again.

An unmet precondition is the expected steady state and is not an error.

## Evidence surfaces

All three are produced by existing tooling; none is new to this audit.

| surface | what it supplies |
|---|---|
| `randomness_lab.r1_readiness` over `benchmarks/*/cohort.json` | the preregistered fail-closed audit for a real R1 replay corpus |
| newest `results/collaboration/observables-*.json` | independent-review latency, contributor recurrence, ownership concentration, evidence-derived priors |
| `.github/workflows/*.yml` | workflows that store state inside an open issue body |

## Measured state at `e16a8d0`

| precondition | observed | required | met |
|---|---|---|---|
| eligible held-out work units | `0` | `>= 20` | no |
| independent reviews exist | `0` (of 50 pull requests, `50` closed without review) | `>= 1` | no |
| recurring-contributor trials | `0` | `>= 1` | no |
| distinct actors | `1` (HHI `1.0`) | `>= 2` | no |
| evidence-derived strategy priors | `0` | `>= 1` | no |
| canonical `node/` directory | absent | present | no |
| no workflow stores state in an issue | `ace-cohort-observer.yml`, `ace-community-growth.yml` | none | no |

The corpus number is the one most likely to be misread. Four cohorts exist —
`phase-b2-first-five`, `phase-b2-first-five-v2`, `phase-b2-successor-five`,
`phase-b2-successor-v2` — and each has five tasks with six recorded attempts, so
the tree is not empty. The frozen audit still returns `status: blocked` and
`eligible_work_units: 0` for all four, because the recorded attempts are
untrusted model patches with no independent verification result beside them.
Attempts are not evidence.

## Issues with a machine-checked precondition

| issue | precondition | why that precondition |
|---|---|---|
| 9 | recurring contributors | the title asks for the first ten recurring contributors |
| 10 | distinct actors | a repository-driven community engine needs a community |
| 11 | `node/` directory | activation targets a canonical node that is not in the tree |
| 23, 109 | not a workflow state store | their bodies are rewritten in place by ACE workflows |
| 30, 70, 96 | eligible held-out work units | each names a real held-out coding corpus |
| 138, 151, 167 | independent review exists | each asks for an independent inspection |
| 152 | independent review exists | gated on issue 167 |
| 86 | evidence-derived priors | P0 item 4 only; items 2 and 5 are already met |

Issue 86's entry is marked `partial_gate`, because the issue is a programme
rather than a single deliverable and only one of its items is gated this way.

## Issues deliberately left unclassified

`1`, `2`, `4`, `12`, `13`, `16`, `22`, `57`.

No mechanical precondition was read off their text, so none is recorded. **That
is not evidence that they are blocked**, and a test asserts they stay out of the
registry so a future guess cannot be laundered into a machine-checked status.

Two of them are actively being worked rather than waiting:

- **22** — E030 and E031 landed against it, and E031's decision section states
  plainly that it closes none of the issue by itself.
- **13** — hypothesis 1 ("increasing `N` with low diversity produces diminishing
  or negative returns after a measurable threshold") is testable in the existing
  simulator and had been sitting in a plan file, unconnected to the issue. That
  connection was the one real error this audit corrected.

## What this audit does not establish

- It does not show any issue *should* stay open. It shows what each issue's own
  stated precondition currently measures.
- The registry is hand-written. Each entry carries a note recording where the
  precondition was read from, and a test requires that note to be substantive,
  but the mapping from issue text to precondition is a human reading.
- Passing preconditions would make an issue workable, not finished.
