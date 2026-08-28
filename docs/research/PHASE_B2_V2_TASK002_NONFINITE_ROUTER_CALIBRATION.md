# Phase B2 v2 Task 002 — non-finite free-router calibration

## Purpose

Calibrate the provisional public EvaluatorPlan for:

`benchmark/phase-b2-v2/002-router-nonfinite-numbers`

before the successor-v2 benchmark is frozen or any scored candidate outcome is collected.

The task protects the free-compute routing boundary. Python's standard `json.loads` accepts `NaN`, `Infinity`, and `-Infinity` even though those tokens are not standard JSON. Numeric JSON Schema comparisons also do not reliably reject every non-finite float. A value that reaches the router can therefore participate in cost-limit comparisons or ranking with surprising semantics.

## Frozen definition

Source revision:

`a69aa0ae1ae4862e507511cbd9ad854237d0ad32`

WorkUnit digest:

`sha256:1c3398ec000719eee21396b6214bc56bb410a4aa449cb7b4f9206811daf7a27d`

EvaluatorPlan digest:

`sha256:21d6ef9b1386adc2aeac8cb2c1d409b2ff32ff07686378d260b8a56399226a43`

The metadata-only v0.4 transition proxy requires:

```text
added:   isfinite
removed: return json.loads(path.read_text(encoding="utf-8"))
```

That transition is intentionally not trusted by itself.

## Calibration candidates

### Straightforward

The reference transition changes `read_json` so parsed structures are walked recursively and every floating-point value is checked with `math.isfinite` before schema validation, eligibility, spend-limit comparison, or ranking.

This is evaluator-owned calibration code against the immutable source snapshot. It is not merged into the production router by this calibration PR.

### Inert decoy

The near-miss only adds the lexical marker `isfinite`. It deliberately leaves the vulnerable direct `json.loads` return intact.

The v0.4 verifier must reject the decoy because the required vulnerable line is not removed.

## Behavioral matrix

Each candidate is exercised through the actual frozen-source `free_compute_router.py select` CLI in a disposable checkout. The offer pool is reduced to the known finite zero-cost control offer `github-public-ci` so ranking outcomes are easy to interpret.

Cases:

| Case | Purpose |
| --- | --- |
| finite baseline | prove ordinary zero-spend routing still selects the control offer and emits strict JSON |
| WorkUnit budget = NaN | non-finite WorkUnit budget |
| WorkUnit budget = +Infinity | unbounded WorkUnit budget |
| WorkUnit budget = -Infinity | negative non-finite WorkUnit budget |
| policy spend ceiling = NaN | non-finite repository ceiling |
| policy spend ceiling = +Infinity | infinite repository ceiling |
| offer project cost = NaN | cost comparison bypass + non-standard output risk |
| offer project cost = +Infinity | infinite offer cost |
| offer project cost = -Infinity | negative infinite offer cost |
| offer success probability = NaN | non-finite ranking input |
| offer success probability = +Infinity | out-of-domain non-finite ranking input |
| offer expected wait = +Infinity | non-finite ranking tiebreak input |

The straightforward candidate must preserve the finite baseline and return the router's fail-closed error code for every non-finite case.

The inert decoy must retain the known vulnerability. In particular, NaN project cost can remain eligible because comparisons with NaN are false; the selected report can then contain a literal `NaN`, which strict JSON rejects. NaN success probability and infinite wait can also reach routing/ranking when the pool contains an otherwise eligible single free offer.

## Acceptance conditions

Calibration passes only when all of these hold:

1. exact WorkUnit/source/EvaluatorPlan digests are unchanged;
2. the canonical v0.4 verifier accepts the straightforward transition;
3. the canonical v0.4 verifier rejects the inert lexical decoy;
4. the straightforward behavioral matrix passes all finite/non-finite cases;
5. the decoy behavioral matrix demonstrates that non-finite values still reach routing;
6. ResultManifest and VerificationResult provenance is retained;
7. no benchmark outcome, definition digest, candidate selection, repository write authority, or merge authority is created.

## Scientific boundary

This exercise calibrates an evaluator before freeze. The generated straightforward patch is not a scored benchmark result and is not a production fix. Task 002 remains outcome-pending until the full five-task successor is calibrated, novelty-audited, frozen, and then evaluated according to the benchmark protocol.

A fresh novelty audit is required immediately before freeze because public repository activity can make a previously novel task known.

## Authority boundary

The GitHub Actions workflow uses `contents: read`, persists no checkout credentials, consumes no repository secrets, and writes only to disposable source/result paths. It cannot push, approve, merge, change settings, spend project funds, or automatically select a candidate.

Related: #180, #186, #198, #201.
