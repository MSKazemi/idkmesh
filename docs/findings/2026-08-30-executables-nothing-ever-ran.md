# Five Committed Executables That Nothing Demonstrates Ever Ran

**Date:** 2026-08-30
**Evidence level:** deterministic repository condition; review candidates, not proven defects.
**Producer:** `tools/idkgraph_health_checks.py`, severity `notice`, category
`executable_without_exercise_or_recorded_output`.

## The question

[The ownership-concentration report](2026-08-30-ownership-concentration-first-measurement.md)
closed with a complaint about its own evidence: a structural-debt observable whose entire
population is four `notice` findings in one category cannot discriminate between a healthy
repository and an unexamined one. This adds a second category, chosen because the repository
had just been caught by exactly the condition it detects.

`tools/open_model_benchmark_probe.py` is a complete, pinned, sandboxed harness for running an
open-weight model as a benchmark candidate producer. A repository-wide search found it named by
no workflow, no test, and no committed result. Nothing recorded that it had ever run. Nothing
in the repository's automated health surface noticed, because no check asked.

## The rule, and why it is conjunctive

A committed Python entry point below `tools/` or `scripts/` is flagged when **both** hold:

1. no file under `.github/workflows/` or `tests/` names it, and
2. its name appears in no file under `results/`, `experiments/results/`, `docs/`, or
   `benchmarks/`.

The second condition is what makes the check usable. Fourteen executables satisfy the first
condition alone — but nine of those are one-shot calibration and evidence tools such as
`tools/task004_rwvb_nonfinite_calibration.py`, which ran once, wrote committed evidence, and
were never meant to be wired into CI. Flagging them would be wrong. They did their job, and the
proof is in the tree.

Requiring both conditions takes the population from fourteen to five, and every one of the five
survives manual inspection.

## The five

| Executable | Why nothing runs it |
| --- | --- |
| `tools/node_runtime_acceptance.py` | Needs `node/`, absent from `main` |
| `tools/node_verifier_e2e.py` | Needs `node/`, absent from `main` |
| `tools/node_verifier_e2e_current.py` | Needs `node/`, absent from `main` |
| `tools/open_model_benchmark_probe.py` | Never wired to a run |
| `tools/open_model_text_generator.py` | Supports the probe above |

The partition is the interesting part. The check was written without reference to either
situation, and it independently recovered both of the repository's known structural gaps: the
`node/` directory that two rejected pull requests failed to introduce, and the open-model
benchmark path that has never been exercised. Five findings, five true positives, out of
sixty-two executables scanned.

## A matcher bug worth recording

The first implementation compared bare filename stems as substrings and reported four, not five.
`tools/node_verifier_e2e.py` was cleared because `tools/real_node_verifier_e2e.py` — a different,
genuinely wired tool — contains its stem. Substring matching silently absolves any executable
whose name is a suffix of a referenced one. The stem match is now anchored on identifier
boundaries, and `test_stem_matching_respects_identifier_boundaries` pins the case.

A reference check that is too permissive fails silently and in the safe-looking direction: it
reports a clean repository. That is the failure mode to design against.

## Severity, and what this must not become

`notice`, not `warning`. An executable can be legitimately dormant — three of these five are
waiting on a dependency that two rejected pull requests failed to land, and a fourth is staged
ahead of the run that will use it. This module cannot tell dormant from abandoned, and it does
not try.

The finding names three responses and ranks none: wire it into automation, run it once and
record the evidence, or remove it. **Driving this count to zero by deleting tools would be the
worst available outcome** and would make the repository less capable while the number improved.
The count is a review prompt. It is not a target, and nothing in CI enforces it.

## Limitations

- Reference detection is textual. A tool invoked through indirection — a variable holding its
  path, a dynamic import — reads as unreferenced.
- `docs/` counts as recorded output, so merely *mentioning* a tool in prose clears it. That is
  deliberate (a documented tool has a human explaining it) but it is a weaker signal than a
  committed artifact.
- The check cannot see whether an exercised tool's automation actually runs, only that it is
  named. A workflow that is permanently skipped still counts as exercise.
- Scope is `tools/` and `scripts/` Python entry points. Shell scripts, `sim/`, `experiments/`,
  and `randomness_lab/` are out of scope for this rule.

## Decision

No removals, no CI enforcement, no threshold. The five are recorded as review candidates. Two of
them — the open-model pair — are the subject of active work; if that work produces a recorded
result, they leave this list by the intended route, which is running rather than deleting.
