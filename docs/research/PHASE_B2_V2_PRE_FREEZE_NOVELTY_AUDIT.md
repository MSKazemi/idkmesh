# Phase B2 successor-v2 pre-freeze novelty audit

## Decision

Do not freeze `benchmarks/phase-b2-successor-v2/` as a scored held-out cohort.
At canonical revision `ed23a3995961cca784f7f049ee74732ea44a5fc7`, all five
task solutions are public in the repository's calibration scripts and reports.
The calibration evidence remains valid, but the tasks are no longer novel.

## Method and result

The audit compared every fixed WorkUnit objective with public changes after
source revision `a69aa0ae1ae4862e507511cbd9ad854237d0ad32`. Four production
paths are byte-identical to that source. `tools/benchmark_cohort.py` has only
unrelated cohort-loader and definition-projection changes; its symlink-order
repair is also absent. Thus none of the five production defects has been fixed.

Production-path novelty is not the gate, however. For each task, the merged
calibration PR contains an explicit straightforward transformation, behavioral
success matrix, and inert near-miss:

| Task | Public PR | Merge commit | Result |
| --- | ---: | --- | --- |
| symlink reference | #235 | `b6505bd` | solution public |
| non-finite router values | #207 | `1f6eafe` | solution public |
| unobserved branch head | #198 | `0b0887b` | solution public |
| non-finite RWVB inputs | #233 | `621e648` | solution public |
| local-offer output boundary | #189 | `ad00a1c` | solution public |

The committed programs do not merely describe the defects. They reconstruct
the exact candidate patches from the frozen source, and the public receipts
identify those patches as passing. Calling them calibration candidates rather
than scored outcomes preserves accounting integrity, but it cannot restore
solution novelty.

The machine-readable audit is
[`../evidence/phase-b2-successor-v2-novelty-audit.json`](../evidence/phase-b2-successor-v2-novelty-audit.json).

## Interpretation

This is not a calibration failure and does not erase the completed calibration
receipts. It is a held-out-validity failure: a worker or model may have learned
the exact reference changes from public history. Restricting runtime network
access does not remove pretraining, cache, or prior-context contamination.

Keep this scaffold outcome-empty and unfrozen. The next scored cohort must use
new task identities and a new pre-outcome digest. Calibrate evaluator mechanics
on separate analogous fixtures without publishing exact held-out solutions
before scoring, or explicitly label the resulting corpus as public
replay/training data rather than held-out evidence.

No audit result grants write, push, approval, merge, spending, or automatic
candidate-selection authority.
