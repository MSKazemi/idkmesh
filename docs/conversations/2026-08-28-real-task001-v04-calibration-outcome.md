# Conversation outcome — real Task 001 v0.4 calibration

Date: 2026-08-28

This outcome record supplements `docs/conversations/2026-08-28-real-task001-v04-calibration.md` with the final integration evidence.

## Convergence

- PR #170 was closed without merge after PR #171 independently landed the canonical EvaluatorPlan v0.4 / verifier 0.3.0 implementation.
- Draft PR #176 was also closed without merge because its real calibration retained a superseded experimental finding-text assertion and failed its dedicated canonical calibration run.
- PR #177 became the sole clean integration path for the unique real frozen-source calibration layer.

## PR #177

Title: `Calibrate canonical v0.4 on real frozen Task 001`

Final head:

`c4e4810c618a0ab840e22727724937a6dcb40513`

Merged as:

`4639687d76f4c3eace5ec6c4bf8e7584a04ed6e1`

It adds only:

- a Task 001 bound post-burn EvaluatorPlan v0.4 calibration fixture;
- a real frozen-source straightforward-vs-decoy calibration harness;
- a dedicated read-only GitHub Actions workflow;
- a research note documenting the static/behavioral evidence boundary;
- the project conversation record.

No duplicate schema/verifier/runner was added.

## Exact-head workflow evidence

Dedicated workflow:

`Task 001 real v0.4 transition calibration`

Run:

`33194631359`

Job:

`98928508539`

Conclusion: success.

The workflow separately checked out:

- the current evaluator control plane; and
- exact frozen Task 001 source `9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2`.

The burned first-five cohort remained burned with original definition digest:

`sha256:4fdec8a2768e32dc223b218ed70aec3a67aefcd87c64b72c5675c9921a4eab5c`

## Calibration result

EvaluatorPlan:

- id: `verification/task001-real-transition-calibration-v0.4`
- digest: `sha256:d85821027c920637ece1405519ac1788baf2212baaf2ec1c1e88230fedf9b607`
- verifier adapter version: `0.3.0`

### Straightforward repair

- VerificationResult: `passed`
- recommendation: `accept_candidate`
- required removed-substring matches: `1/1`
- all four absolute/traversal outside-repository cohort probes: rejected as unsafe
- ResultManifest digest: `sha256:b4d0727eea0683456b60b9f30f088549b82415119a0913b2a0247724a2df630e`
- VerificationResult digest: `sha256:9e62896a53896811bf8b3a893f29b16bc93e8088185664fed26e64ea01d11f6c`

### Inert Goodhart decoy

- VerificationResult: `failed`
- recommendation: `reject_candidate`
- required removed-substring matches: `0/1`
- all four vulnerable absolute/traversal outside-repository cohort probes: still accepted
- ResultManifest digest: `sha256:029ea19c516496da41ea4d5d53af8d27dbcf9faad4e15c7f3bb4a14adf8e3e80`
- VerificationResult digest: `sha256:fc88f7436351a171951662f4addf4259082b1feaf51a66915d23fe39a6a43f1c`

Both results preserve semantic mode:

`added_and_removed_line_substring_all`

and exact plan-digest provenance.

## Retained artifact

Artifact name:

`task001-real-v04-calibration`

Artifact ID:

`9695205986`

Files: 13

ZIP SHA-256:

`3860fc10a0370c7fe41f23fb95e5d9691c5094e407ce23e9672ea86b4bf39356`

Retention: 30 days.

## Other exact-head gates

On PR #177's final head:

- Phase 0 schema check — success;
- IDKMesh Evolution Loop — success;
- IDKGraph observatory — success.

## Subsequent convergence

Before PR #177 merged, PR #175 independently landed Benchmark Cohort v0.1 routing for public EvaluatorPlan v0.4:

`b6bd6fa9e5edeb87a2147cb42b9e1c8cbd1bdf55`

Therefore the semantic-version P0 tracked by #157 had all expanded acceptance criteria satisfied and was closed completed after #177 merged.

## Next gate

The project can now define and freeze a **new successor Phase B2 cohort** against a new source snapshot using calibrated versioned evaluator semantics.

Task 001 must not be represented as untouched held-out evidence because its solution is known.

The burned v1 cohort remains diagnostic history, not real benchmark outcome evidence.

No worker/verifier gained push, approval, merge, canonical-write, spending, or automatic candidate-selection authority.
