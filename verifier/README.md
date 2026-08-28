# Deterministic Independent Verifier

This directory contains the first executable verification substrate for IDKMesh issue #5.

The verifier is intentionally small and conservative. It does **not** execute candidate code, run arbitrary commands from a Work Unit, call a model, use the network, or merge anything. It independently recomputes evidence from a candidate bundle and emits a canonical `VerificationResult v0.1`.

## What v0.1 verifies

Built-in validator IDs:

- `result-manifest-schema` — validate the worker's ResultManifest contract;
- `work-unit-digest` — recompute the canonical Work Unit SHA-256 and compare worker provenance;
- `artifact-digests` — recompute SHA-256 for produced artifacts and digested logs;
- `path-policy` — parse patch target paths and compare them with `allowed_paths` / `forbidden_paths`.

If a Work Unit requires another validator, this verifier reports that check as **inconclusive**. It never silently converts an unsupported validator into a pass.

## Trust boundary

```text
worker ResultManifest + candidate files
                 |
                 v
      deterministic verifier
       (separate identity)
                 |
     schema + digest + scope checks
                 |
                 v
       VerificationResult v0.1
                 |
                 v
       decision support only
```

A `passed` VerificationResult can recommend `accept_candidate`, but it is **not merge authority**.

## Fixture run

From the repository root:

```bash
python -m pip install -r requirements-phase0.txt
python -m verifier.deterministic \
  --work-unit examples/work-units/deterministic-verifier.work-unit.json \
  --result-manifest examples/verifier-bundle/result-manifest.json \
  --artifact-root . \
  --output /tmp/idkmesh-verification.json
```

The fixture should return exit code `0`, emit a schema-valid `VerificationResult`, and report four required checks as passed.

## Failure behavior

The verifier fails closed when:

- the Work Unit or ResultManifest violates its canonical JSON Schema;
- Work Unit ID/version references disagree;
- verifier identity equals worker identity;
- a declared artifact locator escapes the trusted artifact root;
- a declared artifact/log digest is wrong or its file is missing;
- a patch touches a forbidden path or a path not covered by `allowed_paths`;
- a required validator is unsupported.

Deterministic check failures produce `reject_candidate`. Unsupported required evidence produces `insufficient_evidence`.

## Security limits

This is **not** yet the hidden-test/sandbox execution layer described by the full #5 milestone. It is the safe substrate beneath that layer.

Future verifier plugins can add hidden tests, linting, static analysis, fuzzing, or sandboxed reproduction. Those plugins must remain independently controlled from the worker and must not turn Work Unit text into unbounded host command execution.

## Zero-spend rule

The verifier uses local/public-project execution only and records zero project-paid compute. It has no paid-provider fallback and no network requirement.
