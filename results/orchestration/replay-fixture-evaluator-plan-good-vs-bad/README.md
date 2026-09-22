# Two-attempt orchestration replay fixture

Produced by `experiments/replay_run.py capture`, which wraps
`experiments/two_attempt_orchestrator.py` and `experiments/run_evidence_report.py`
(the same code already used by their own `self-test` commands), plus a raw,
unprojected `VerificationResult` per attempt from `experiments/local_verifier.py`
via `experiments/evaluator_plan_runner.py`.

Reproduce the capture:

```bash
python experiments/replay_run.py capture \
  --config examples/orchestration/two-attempt-evaluator-plan-good-vs-bad.json \
  --output-dir results/orchestration/replay-fixture-evaluator-plan-good-vs-bad
```

Confirm it replays:

```bash
python experiments/replay_run.py replay \
  --bundle results/orchestration/replay-fixture-evaluator-plan-good-vs-bad/replay-source.json
```

This is a real bounded task -> WorkUnit -> two isolated attempts -> independent
verification -> evidence report run (ROADMAP.md S4), not a simulation: the
source WorkUnit is `verification/patch-smoke` (`examples/work-units/patch-verifier-smoke.work-unit.json`),
`attempt-001` is a real unified-diff candidate patch
(`examples/verifier/patch/good/changes.patch`) that independent verification
accepts, and `attempt-002` is a real unified-diff candidate patch
(`examples/verifier/patch/wrong-semantic/changes.patch`) that independent
verification rejects for a semantic mismatch. The evidence report preserves
that accept/reject disagreement rather than selecting a winner (see
`evidence-report.md`); it carries no acceptance or integration authority.

## Reproducibility

`run-record.json` and `evidence-report.json` are expected to be
**byte-identical** on every replay, on every machine, on every supported
Python version. That is a design property of the producer code, not a hope:
`two_attempt_orchestrator._verification_record` / `_result_manifest_record`
and `local_verifier.semantic_signature` project every stored field down to
content that never depends on wall-clock time or the host environment before
it is written to the run record, and `run_evidence_report.build_report`
derives the evidence report purely from that record. See the "Field
classification" section of `experiments/replay_run.py`'s module docstring for
the field-by-field justification.

`verification-result-attempt-001.json` and `verification-result-attempt-002.json`
are the raw, *unprojected* `VerificationResult` documents the orchestrator
computes internally but does not persist in full (only their
content-projected summary reaches the run record above). These are **not**
expected to be byte-identical on replay: `started_at`, `finished_at`,
`resources.wall_seconds`, and `provenance.environment.{platform,python}` are
real wall-clock timestamps, elapsed compute time, and interpreter/platform
strings, and differ run to run and machine to machine. Every other field --
`status`, `decision_support`, `checks`, `evidence`, `findings`, `metrics`, the
rest of `provenance` -- is derived from the static WorkUnit/ResultManifest/plan
inputs and is expected to match exactly. `experiments/replay_run.py replay`
enforces exactly this split; it does not do a blind byte-for-byte diff.

This differs from `results/verification/node-e2e-replay-2026-08-30/`, where
the ResultManifest and VerificationResult *identifiers* themselves are
`uuid.uuid4()`-seeded by a real worker process and only the candidate patch
digest and WorkUnit digest reproduce (see
`docs/findings/2026-08-30-node-evidence-replay-and-digest-reproducibility.md`).
The fixtures this bundle replays are static files under `examples/verifier/patch/`,
so no identifier here is randomly seeded; the volatility is limited to the
timing/environment leaves listed above.
