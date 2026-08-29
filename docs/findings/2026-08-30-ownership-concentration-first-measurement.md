# Ownership Concentration: First Real Measurement, and What Structural Debt Refused to Say

**Date:** 2026-08-30
**Evidence level:** bounded observational snapshot; no causal claim, no policy authority.
**Artifacts:** `results/collaboration/snapshot-2026-08-29T22-03-24Z.json`,
`results/collaboration/observables-2026-08-29T22-03-24Z.json`

## Why this exists

[The first production collaboration-observables snapshot](2026-08-29-collaboration-observables-first-snapshot.md)
separated two kinds of zero. Three metrics read zero because a real measurement returned
nothing. Two read zero because the collector never looked: `scripts/collaboration_snapshot.py`
wrote `"changed_file_owners": []` and `"structural_debt_finding_ids": []` unconditionally and
declared both gaps in its own `limitations` list.

Collector `v0.2` closes both gaps. This report is the first run with them closed.

## Window

Fifty most recently created pull requests, `#288` through `#338`, all closed, cutoff
`2026-08-29T22:03:24Z`. Structural debt was inventoried by `tools/idkgraph_observatory.py`
at revision `f9ec91653834a6a318f50434b9e61b69fded0c6c`.

## Result 1 — ownership concentration is 1.0

| Quantity | Value |
| --- | --- |
| Changed-file observations | 281 |
| Attributed to a within-window owner | 66 |
| Unattributed (no prior merged touch in the window) | 215 |
| Distinct owners | 1 |
| Ownership HHI | **1.0** |

Ownership here is a declared model, `last_merged_toucher_within_window-v1`: a path is owned by
the author of the most recent *merged* pull request inside the window that changed it, and the
model is advanced only after a pull request merges, so no pull request is ever credited with
ownership it acquired by its own merge.

HHI of 1.0 is the maximum the index can take. Every file whose ownership could be established
from the observed window is owned by the same actor. The repository has asserted single-maintainer
concentration qualitatively in several places; this is the first time it is a number produced by
a collector rather than a sentence produced by a person.

The 215 unattributed observations are not a defect to be tuned away. They are the window boundary
made visible: those paths were touched once inside the window and never before it, so the window
carries no evidence about who owns them. A collector that guessed an owner for them would be
manufacturing the very concentration it is trying to measure.

## Result 2 — the deterministic debt is older than the window

Four deterministic findings were loaded, all severity `notice`, all of one category
(`document_referenced_only_by_non_markdown_artifact`):

| Finding | Path |
| --- | --- |
| `debt:01f073c92450dd93` | `docs/acceptance/PR91_CONTROLLED_DOCKER_GATE.md` |
| `debt:e43a860112808597` | `docs/algorithms/ACO_STIGMERGIC_TASK_ROUTING.md` |
| `debt:79ce72d82f955b84` | `docs/algorithms/HOMEOSTATIC_STIGMERGY_ROUTING.md` |
| `debt:8abf4cf4deb90d50` | `docs/protocols/CONSTITUTIONAL_EVOLUTIONARY_MESH.md` |

**Zero of the four were attributed.** No pull request in `#288`–`#338` touched any of those four
paths. Fifty consecutive pull requests of repository activity passed without one of them going
near the deterministic debt that exists.

## The trap this run walked into, and the guard that caught it

The observable still reports `structural_debt.observed_findings: 0` — byte-identical to the
value it reported when nothing was collected at all. The two zeros mean opposite things: the
first meant "not looked at", this one means "looked at, and none of it falls inside the window".

`inventory_complete` is what separates them, and it is now derived rather than hard-coded. The
collector sets it `true` only when a report was supplied **and** every finding in it reached a
pull request. Here one condition held and the other did not, so it stays `false` and
`structural_debt_findings_outside_the_window_are_unattributed` is added to the machine-readable
limitations. The snapshot additionally carries `collection.structural_debt.findings_loaded: 4`
and the full finding index, so the shortfall is recoverable rather than merely flagged.

A reader who takes `observed_findings` alone will undercount this repository's deterministic debt
by four. That is a real weakness in the observable's shape, not in the collection, and it is
recorded here rather than quietly fixed by inflating the count with findings that have no pull
request to attach to.

## Limitations

- The window is fifty pull requests, not repository history. Ownership before `#288` is invisible.
- Ownership is a last-toucher proxy. It is not `CODEOWNERS`, not review authority, and not
  blame-weighted by lines.
- Structural debt covers the deterministic observatory categories only. Coupling, duplication,
  test-gap, and dependency debt are not in this inventory.
- One actor and one category means neither number has a distribution behind it. Both are
  descriptive; neither supports inference about a population.
- A pull request touching 100 or more files saturates one bounded page. None did in this window
  (`saturated_file_lists: []`), but the flag exists per pull request and in the collection block.

## Decision

No policy changes on this evidence. The measurable next step is to widen the debt inventory
beyond the four deterministic notice categories, because a debt observable whose whole population
is four notices cannot discriminate between a healthy repository and an unexamined one.
