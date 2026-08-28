# Phase B2 successor v2 — Task 005 output-boundary calibration

Status: **pre-freeze evaluator calibration**  
Tracker: #180  
Task: `benchmark/phase-b2-v2/005-local-offer-output-boundary`

## Question

Can the provisional public EvaluatorPlan v0.4 for Task 005 distinguish a real output-authority repair from an inert lexical near-miss, and does that metadata result agree with an explicit safe CLI behavioral matrix?

The successor cohort remains `stage=scaffold`. Calibration candidates are not benchmark outcomes.

## Frozen inputs

Exact source:

`a69aa0ae1ae4862e507511cbd9ad854237d0ad32`

Writable target:

`experiments/local_compute_offer.py`

Frozen vulnerability:

```python
output = Path(args.output)
```

The discovery utility advertises no canonical-write authority, but this line permits `--output README.md`, absolute paths, and traversal outside generated `results/` state.

## Provisional static evaluator

The scaffold plan is EvaluatorPlan v0.4 / deterministic patch verifier 0.3.0 and requires:

```text
added substring:   results/
removed substring: output = Path(args.output)
```

This is a static transition proxy. The calibration asks whether it is at least strong enough to reject a deliberately inert near-miss before freeze.

## Straightforward reference transition

The reference candidate:

1. removes the vulnerable direct `Path(args.output)` assignment;
2. adds a `resolve_generated_output()` boundary;
3. rejects absolute paths and `..` traversal;
4. requires a real file path under repository `results/`;
5. resolves both repository and results roots and rejects a `results/` symlink that escapes the repository;
6. returns the bounded path to the existing write code.

The candidate is expected to pass metadata verification **and** the behavioral matrix.

## Inert/Goodhart near-miss

The decoy leaves the vulnerable assignment untouched and only appends a comment/string containing `results/`.

It therefore exercises the lexical half of the evaluator without performing the required transition:

```text
added `results/` marker      -> yes
removed unsafe assignment   -> no
behavior changed             -> no
```

The canonical v0.4 verifier must reject it because required removal evidence is absent.

## Behavioral matrix

Each case runs in a disposable checkout that is reset to the exact frozen source and re-applies the calibration transform independently.

Expected straightforward behavior:

| Case | Expected |
| --- | --- |
| no `--output` | success, schema-valid JSON on stdout |
| `--output results/task005-calibration/...json` | success, generated JSON under `results/` |
| `--output README.md` | fail closed, README unchanged |
| absolute output path | fail closed, outside file absent |
| `../` traversal | fail closed, outside file absent |

Expected decoy behavior:

- stdout/results cases remain successful;
- README write remains accepted and modifies the disposable canonical file;
- absolute and traversal targets remain accepted and create files outside the source checkout.

The decoy behavior is intentionally safe to demonstrate because the checkout is isolated public test state with no secrets or canonical repository authority.

## Calibration pass rule

Calibration passes only if all of the following are true:

```text
straightforward metadata status       = passed
straightforward recommendation        = accept_candidate
straightforward matched added         = 1 / 1
straightforward matched removed       = 1 / 1
straightforward behavioral matrix     = safe

decoy metadata status                 = failed
decoy recommendation                  = reject_candidate
decoy matched added                    = 1 / 1
decoy matched removed                  = 0 / 1
decoy behavioral matrix                = vulnerable behavior preserved
```

Both VerificationResults must retain exact EvaluatorPlan provenance, verifier 0.3.0, metadata-only execution mode, and semantic mode `added_and_removed_line_substring_all`.

## Non-claims

A passing calibration does **not** mean:

- v0.4 proves arbitrary behavioral correctness;
- Task 005 has a scored worker outcome;
- the successor cohort may freeze before the other four evaluators are calibrated;
- verifier support authorizes merge;
- worker or evaluator automation may write canonical repository state.

It only retires one item from #180's per-task pre-freeze calibration queue.
