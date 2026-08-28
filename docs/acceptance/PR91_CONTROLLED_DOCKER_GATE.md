# PR #91 controlled Docker acceptance gate

**Tracker:** issue #37  
**Candidate:** PR #91  
**Frozen head:** `d638a2f78e4a89353b98e91052233e365f56f90a`  
**Node CI:** `33183974768`  
**Phase 0 schema check:** `33183974817`

## Purpose

Issue #37 is a real-runtime safety gate. Static CI, synthetic fixtures, or a metadata-only verifier are not substitutes for a controlled Docker execution of the exact frozen PR #91 candidate.

`scripts/pr91_acceptance.py` reduces manual error around that gate while preserving the gate's independence and fail-closed rules. The helper lives on `main`, not on PR #91, so improving the helper does **not** move the frozen candidate head and invalidate its exact-head evidence.

The helper does not grant merge authority and does not convert a successful worker run into acceptance.

## Trust separation

Use two checkouts:

```text
main checkout
  -> scripts/pr91_acceptance.py

separate PR #91 checkout
  -> exact commit d638a2f78e4a89353b98e91052233e365f56f90a
  -> node implementation under test
```

The harness refuses a candidate checkout whose `git rev-parse HEAD` differs from the frozen SHA.

## Controlled host preconditions

Use a machine intentionally selected for this MVP. It must have:

- Python 3.11+;
- Git;
- Docker;
- no production credentials or sensitive local files exposed to the test;
- no Docker socket, host home directory, or secrets mounted into the task container.

Preload the allowlisted image manually:

```bash
docker pull python:3.12-alpine
docker image inspect python:3.12-alpine
```

The node and harness require both:

- an immutable local `sha256:...` image ID;
- a matching `python@sha256:...` repository digest.

The harness does not pull the image implicitly.

## Prepare the exact candidate checkout

For example, from a clean parent directory:

```bash
git clone https://github.com/MSKazemi/idkmesh.git idkmesh-pr91-acceptance
cd idkmesh-pr91-acceptance
git fetch origin pull/91/head
git checkout --detach d638a2f78e4a89353b98e91052233e365f56f90a
```

Confirm:

```bash
git rev-parse HEAD
```

must print exactly:

```text
d638a2f78e4a89353b98e91052233e365f56f90a
```

If PR #91's head moves, stop. Do not reuse acceptance from the old tree.

## Run preflight from a current-main checkout

From a checkout that contains `scripts/pr91_acceptance.py`:

```bash
python scripts/pr91_acceptance.py preflight \
  --repo /absolute/path/to/idkmesh-pr91-acceptance \
  --report /tmp/idkmesh-pr91-preflight.json
```

Preflight checks:

- exact frozen PR #91 SHA;
- Python version;
- Git and Docker availability;
- Docker version;
- local presence of `python:3.12-alpine`;
- immutable image ID;
- matching immutable repository digest.

## Run the positive path

```bash
python scripts/pr91_acceptance.py run-positive \
  --repo /absolute/path/to/idkmesh-pr91-acceptance \
  --output /tmp/idkmesh-node-acceptance \
  --report /tmp/idkmesh-pr91-positive-report.json
```

The helper runs the equivalent of:

```bash
python -m pip install -e node
python -m unittest discover -s node/tests -v
python -m idkmesh_node validate node/examples/work-unit.canonical-smoke.json
python -m idkmesh_node run node/examples/work-unit.canonical-smoke.json \
  --output /tmp/idkmesh-node-acceptance
```

It then independently inspects the bundle rather than trusting the worker's summary fields.

## Positive evidence checked by the harness

The helper requires:

- `result-manifest.json`, `changes.patch`, `stdout.txt`, and `stderr.txt`;
- ResultManifest v0.1 with `status: succeeded`;
- exact WorkUnit id/version binding;
- exact immutable source revision alignment;
- independently recomputed SHA-256 for the patch and both logs;
- independently parsed unified-diff paths;
- WorkUnit allowed/forbidden/filesystem-write scope enforcement;
- zero untracked files;
- no patch truncation;
- zero policy violations;
- empty path/unpackaged/protected-metadata/output/runtime violation arrays;
- worker-reported `changed_paths` consistent with independently parsed patch paths;
- configured image, immutable local image ID, and immutable repository digest matching preflight;
- provenance container image equal to the immutable repository digest;
- verification-request validator IDs exactly equal to the WorkUnit's required validator IDs;
- `candidate-patch` requested for independent verification;
- no top-level worker claim of acceptance or independent verification.

The report contains observed hashes and identities suitable for attaching to issue #37 after human review.

## Required negative runtime matrix remains mandatory

The helper currently automates the positive path only. Issue #37 still requires controlled-host evidence for all five negative cases:

| ID | Negative case | Required behavior |
|---|---|---|
| A | tracked out-of-scope path | path-policy violation; fail closed |
| B | ignored untracked artifact | artifact still observed; fail closed |
| C | task-visible `.git` pointer tampering | real metadata remains protected; tampering recorded; fail closed |
| D | oversized candidate patch | `patch_truncated == 1`; output-policy violation; fail closed |
| E | absent/local-retagged image without matching RepoDigest | refuse execution; no implicit pull |

Do not commit destructive negative fixtures. Use temporary local copies as specified in issue #37.

A future revision may safely automate these negatives, but it must not reduce them to mocked unit tests and call that runtime acceptance.

## What CI proves and does not prove

`.github/workflows/pr91-acceptance-harness-check.yml` only runs:

```bash
python -m py_compile scripts/pr91_acceptance.py
python scripts/pr91_acceptance.py self-test
```

That self-test verifies parsing, hash comparison, exact-path rules, a synthetic positive bundle, and tamper detection without Docker.

It **does not** count as issue #37 evidence.

## Evidence to attach to issue #37

After a real controlled-host run, retain at minimum:

- host OS and Docker version;
- exact tested PR #91 SHA;
- exact CI run IDs above;
- configured image tag;
- immutable Docker image ID and matching repository digest;
- sanitized positive ResultManifest;
- independent patch/stdout/stderr hashes;
- positive sandbox-policy confirmation;
- concise evidence for negatives A–E;
- confirmation that PR #91 still points to the tested SHA when acceptance is recorded.

## After the gate

Only after issue #37 has real positive and negative evidence should IDKMesh proceed with the full Phase B1 chain:

```text
real node bundle
 -> EvaluatorPlan v0.2
 -> unified-diff verifier backend
 -> VerificationResult v0.1
 -> Evidence Report / replay
 -> human integration decision
```

Then build the first 5–10 replayable repository-level benchmark tasks for issue #5.
