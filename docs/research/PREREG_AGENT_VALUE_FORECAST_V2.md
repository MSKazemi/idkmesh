# Preregistration v2 — temporal holdout for the agent-value forecast

**Experiment:** E048 · **Extends:** [`PREREG_AGENT_VALUE_FORECAST_V1`](PREREG_AGENT_VALUE_FORECAST_V1.md) ·
**Program items:** H1–H3 of the [Scientific Program](SCIENTIFIC_PROGRAM.md) · **Epic:** #969
**Status:** registered on 2026-10-09. **No data exists to run it yet.** At registration, `SWE-bench/experiments` has zero commits after `40f164d5` (checked 2026-10-09).

## 1. Why a second registration

E046 was confirmatory but rests on one feasible split (Lite), and Lite overlaps Verified on 93 of 300 tasks. E047 then showed that the leaderboard has far fewer distinct models than rows. All five splits have now been seen. The only way to get a new confirmatory result from this source is data that does not exist yet: **submissions added upstream after `40f164d5`.**

## 2. Frozen artefacts

| artefact | value |
|---|---|
| analysis | the E046 code, imported unchanged: `experiments/agent_value_forecast.py`, SHA-256 `67aa3068b52cf67baa6c3862f03fee8ae93a6ad0568de3d26f7b5a1848f28f7d` |
| population builder | `experiments/submission_provenance.py` (E047), unchanged |
| runner | `experiments/temporal_holdout.py` (selects submissions only; adds no statistics) |
| baseline commit | `40f164d5b8f1d249bf95a6df8b74b577fd8e519d` |

## 3. Population

- **Instrument:** a split's submissions present at the new upstream commit but absent from the baseline commit, matched by directory name. The new commit is named when the run is triggered. It is the upstream HEAD at that time and must be recorded.
- **Trigger rule:** run only when at least one split has ≥ 20 competent new submissions and ≥ 100 tasks (E046's feasibility rule). Otherwise report "not yet feasible" and do nothing else. This avoids peeking at partial data.
- **Primary population:** all competent new submissions (E046's definition). **Co-primary:** the same analysis on one submission per model (E047's rule). Both are reported, and neither is chosen after seeing the results.
- Pilots are drawn only from the new submissions. The baseline submissions are not used here.

## 4. Hypotheses and decision rules

These are E046's, unchanged:

- **H1**, **H2** and **H3** use the E046 tests and verdicts (§5 of v1) and the cross-split rules (§6 of v1), on the feasible splits.
- **Replication standard.** A hypothesis counts as **replicated** only if it is *supported* in both the all-submissions and the one-per-model populations. Supported in one only is **unresolved**.
- **Overlap.** Tasks shared with a baseline-era split are reported separately as a sensitivity analysis. They do not change the verdict.

## 5. What would change the program

- H1 failing here, in both populations, would end the worker-side claim that per-item difficulty forecasts team coverage better than correlation models.
- H2 and H3 are promoted from *fragile* to *established* only by being replicated here.
- Every outcome, including "not yet feasible", is published in an E048 results record.

## 6. Execution

```bash
python experiments/temporal_holdout.py list  --commit <new upstream commit>
python experiments/temporal_holdout.py fetch --commit <new upstream commit> --cache .cache/e048
python experiments/temporal_holdout.py analyze .cache/e048/<split> [...] --out experiments/results/E048-temporal-holdout.json
```

`frozen_e046_sha256` in the output must equal the digest in §2.
