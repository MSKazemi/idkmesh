# Node -> verifier E2E replay, 2026-08-30

Produced by `tools/node_verifier_e2e_current.py`, which wraps
`tools/node_verifier_e2e.py` and imports `tools/node_runtime_acceptance.py`.

The worker candidate is not in `main`. Reproduce with:

```bash
git fetch origin 'refs/pull/91/head:refs/tmp/pr91'
git worktree add --detach /tmp/idkmesh-node-candidate 520ad2c9aa5825476de4957da4702d6823f4edb3
docker pull python:3.12-alpine
PYTHONPATH=tools python tools/node_verifier_e2e_current.py --candidate /tmp/idkmesh-node-candidate
```

The harness writes to `results/verification/real-node-cbd40c4/`; this directory is a
dated copy of one such run.

Only `candidate_patch_digest` and the WorkUnit digest reproduce across runs. The
ResultManifest and VerificationResult identifiers are seeded by `uuid.uuid4()` in the
worker and differ on every run. See
`docs/findings/2026-08-30-node-evidence-replay-and-digest-reproducibility.md`.

This is a replay, not a review. It carries no acceptance or integration authority.
