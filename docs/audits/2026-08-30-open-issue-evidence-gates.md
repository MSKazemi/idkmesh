# Open-issue evidence gates — 2026-08-30

**Baseline revision:** `e16a8d0`.
**Tool:** [`tools/issue_evidence_gate.py`](../../tools/issue_evidence_gate.py).

Read this as a snapshot. The numbers below were measured at that revision and
are re-derived on every run of the tool; the tool, not this page, is the current
authority.

## What was inspected, and why

Twenty-one issues were open when this audit was written; issue 152 has since
been closed, leaving twenty. Several of them cannot be closed by writing code,
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
| `examples/community/ace-activation-gate-current.example.json` | the ACE activation gate's verified-descendant count, as a committed snapshot |

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
| distinct actors for a worker fleet | `1` | `>= 10` | no |
| verified descendant evidence | `0` | `>= 1` | no |

The corpus number is the one most likely to be misread. Four cohorts exist —
`phase-b2-first-five`, `phase-b2-first-five-v2`, `phase-b2-successor-five`,
`phase-b2-successor-v2` — and each carries five tasks, so the tree is not empty.
The attempts are concentrated rather than spread: `phase-b2-successor-five` holds
all five recorded attempts and the other three cohorts hold none. The frozen
audit still returns `status: blocked` and `eligible_work_units: 0` for all four,
because the recorded attempts are untrusted model patches with no independent
verification result beside them. Attempts are not evidence.

These counts are no longer written by hand. `tools/benchmark_publication.py`
derives them from the cohort files and `--check` fails when the committed
`benchmarks/publication.json` drifts from the tree; an earlier revision of this
paragraph claimed six attempts spread across all four cohorts, which the
generated count contradicts.

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
| 1 | distinct actors `>= 10` | its minimum experiment's step 4 is to connect 10-20 heterogeneous worker nodes |
| 4, 16 | independent review exists | every remaining box in both begins with PR 159's required separate human review |
| 57 | verified descendant evidence | Phase A shipped; the one unchecked activation-gate box needs a cohort with real descendants |

### The four external dependencies

Re-reading all twenty-one open issues on 2026-08-30 against `53ca25a` found that
every externally blocked one reduces to exactly one of four things:

1. **A genuinely separate human reviewer** — 4, 11, 16, 138, 151, 167, and 152 by
   a criterion its owner added after the body was written. Repository-wide: `0`
   independent reviews across `50` pull requests. Issue 152 was closed on
   2026-08-30 without that reviewer appearing, so it now sits in the evidence
   gate's `resolved_registrations` rather than its live registry; the
   independent-review count is unchanged.
2. **Real external contributors** — 9, 10, 57. `distinct_actors: 1`, HHI `1.0`.
3. **A real held-out corpus, or compute for a larger producer** — 1, 30, 70, 96.
4. **Owner-held credentials or the repository admin UI** — 12, and the
   social-preview half of 10. No repository evidence can observe these, so 12
   stays unclassified rather than being recorded on a guess.

Issues 23 and 109 are outside that taxonomy because they are not tasks at all:
they are the ACE workflows' storage. `ace-cohort-observer.yml` locates its ledger
by scanning *open* issues for the `ace:cohort-observer` label and creates a new
one when it finds none, so closing either forks a duplicate ledger at a new
number on the next scheduled run.

Issue 86's entry is marked `partial_gate`, because the issue is a programme
rather than a single deliverable and only one of its items is gated this way.

## Issues deliberately left unclassified

`2`, `12`, `13`, `22`.

No mechanical precondition was read off their text, so none is recorded. **That
is not evidence that they are blocked**, and a test asserts they stay out of the
registry so a future guess cannot be laundered into a machine-checked status.

`12` is blocked, but on owner-held credentials and a third-party hosted service,
which no evidence surface in this repository can observe. Recording it would mean
asserting a blocker the tool cannot check, which is the thing this registry
exists to avoid.

The other three are actively being worked rather than waiting:

- **22** — E030 and E031 landed against it, and E031's decision section states
  plainly that it closes none of the issue by itself.
- **13** — hypothesis 1 ("increasing `N` with low diversity produces diminishing
  or negative returns after a measurable threshold") is testable in the existing
  simulator and had been sitting in a plan file, unconnected to the issue. That
  connection was the one real error this audit corrected. E032 acts on it.
- **2** — the benchmark task set, runner, isolation, result schema, independent
  validator and public negative results all exist; what is missing is the
  strong-model baseline arm, which is work, not a blocker.

A partial gate is recorded for `4`, `16`, `57` and `86`, because each has shipped
deliverables and recording them as wholly blocked would misreport the repository's
own state.

## When the evidence cannot be read

The readiness audit validates cohorts against the Phase 0 schemas, so it needs
the `requirements-phase0.txt` dependencies. Some workflows deliberately run
without them.

In that case the tool reports `available: false`, `observed: null` and
`met: false` for the corpus precondition — **"cannot tell", never "measured
zero"**. The two are indistinguishable in a bare number and mean opposite things:
one is an empty corpus, the other is an audit that never ran. A partially
audited set is treated the same way, because one unreadable cohort could hide a
ready one behind it. Two tests pin this, one of them by running the audit
through an interpreter that genuinely cannot import the validator.

## What this audit does not establish

- It does not show any issue *should* stay open. It shows what each issue's own
  stated precondition currently measures.
- The registry is hand-written. Each entry carries a note recording where the
  precondition was read from, and a test requires that note to be substantive,
  but the mapping from issue text to precondition is a human reading.
- Passing preconditions would make an issue workable, not finished.
