---
title: "IDKMesh Capability Truth Matrix"
description: "The public claim boundary for IDKMesh: 20 engineering capabilities, each with status, evidence level 0-5, allowed public wording, and known limitation."
---

# IDKMesh Capability Truth Matrix

> Generated from `docs/capability-matrix-v1.json` by `scripts/check_capability_matrix.py`. Do not edit this table by hand.

**Canonical data:** [`capability-matrix-v1.json`](capability-matrix-v1.json)  
**Evidence ladder:** 0 planned · 1 implemented · 2 observed internal real run · 3 controlled benchmark · 4 external reproduction/pilot · 5 production-qualified  
**Baseline revision:** `110f0307ad36d4cca554c19465d7cdc0605d3f21`

This is the public claim boundary for IDKMesh. A higher evidence level is never inferred from a lower one: implemented code is not automatically benchmark evidence, external reproduction, or production qualification.

| ID | Engineering question | Status | Level | Allowed public wording | Known limitation |
| --- | --- | --- | ---: | --- | --- |
| CAP-001 | What exact task ran? | implemented | 1 | IDKMesh has a versioned WorkUnit contract for bounded task semantics. | A WorkUnit describes the bounded task; this does not prove the worker executed it correctly. |
| CAP-002 | What exact source/input revision was used? | implemented | 1 | IDKMesh validates provenance and revision bindings; atomic stale-input-safe execution is not yet claimed. | Binding contracts exist, but end-to-end atomic executor admission against changing inputs is still tracked by issue 921. |
| CAP-003 | Why was a worker/connector eligible? | experimental | 1 | IDKMesh implements inspectable connector eligibility/routing foundations. | Routing/admission foundations exist; the fully converged golden path is still under development. |
| CAP-004 | What authority did the worker have? | implemented | 1 | IDKMesh contracts separate worker execution claims from acceptance and integration authority. | Contracts bound authority, but deployment-specific enforcement still depends on the execution profile. |
| CAP-005 | Was local execution sandboxed? | planned | 0 | IDKMesh does not yet claim production-safe hostile local-code sandboxing. | A production hostile-code sandbox backend is not complete; issue 804 is the gate. |
| CAP-006 | What exact candidate was produced? | implemented | 1 | IDKMesh has a versioned ResultManifest contract for candidate outputs. | A ResultManifest records a candidate claim; it is not acceptance. |
| CAP-007 | Was candidate normalization/provenance verified? | implemented | 1 | IDKMesh implements candidate provenance and integrity validation. | Validation proves contract/integrity checks, not semantic correctness of the candidate. |
| CAP-008 | What independent verification occurred? | implemented | 2 | IDKMesh records verifier-owned VerificationResult evidence and has internal real-run evidence. | Observed repository runs are internal evidence, not external reproduction. |
| CAP-009 | How independent was the verifier panel? | implemented | 3 | IDKMesh measures effective votes and verifier error dependence on ground-truthed verdict data. | Measured dependence is corpus- and gate-specific; it is not intrinsic verifier independence. |
| CAP-010 | What evidence supports/rejects the candidate? | implemented | 1 | IDKMesh has a non-selecting Run Evidence Report and local inspection surface. | The evidence report is non-selecting and does not make the human decision. |
| CAP-011 | Who can record a human decision? | planned | 0 | Human-decision recording is planned; the current Control Tower cannot record it. | Transport schemas and a transport-neutral immutable decision core (idkmesh/human_decision_service.py) exist, but no endpoint or CLI calls it and it performs no policy authorization; the authenticated, authorized decision endpoint is still issue 740. |
| CAP-012 | Who can integrate/merge? | implemented | 1 | IDKMesh explicitly keeps integration authority separate from worker and verifier claims. | Repository protection and organization policy remain deployment-specific; worker/verifier evidence never grants merge authority. |
| CAP-013 | Can the run be replayed/audited? | experimental | 2 | IDKMesh has bounded internal replay and audit evidence. | Replay evidence exists for bounded internal fixtures/runs; this is not a universal deterministic replay guarantee. |
| CAP-014 | Are duplicate dispatches/idempotent retries safe? | experimental | 1 | IDKMesh implements idempotency controls on specific dispatch/state paths. | Idempotency exists on specific Product Spine/GitHub paths; it is not yet a universal exactly-once guarantee. |
| CAP-015 | Are stale inputs rejected? | experimental | 1 | IDKMesh implements scoped stale-input rejection in the local executor-admission boundary; this is not yet a claim about every live provider execution path. | The local executor-admission composition rejects changed upstream inputs before dispatch intent and candidate submission, but live provider/GitHub execution-path integration remains separate work. |
| CAP-016 | Can another repository adopt the workflow? | experimental | 1 | IDKMesh provides a deterministic GitHub-first bootstrap dry-run that renders project/config content and digests; apply/workflow-pack and external reproduction remain unfinished. | GitHub-first bootstrap planning and deterministic config rendering are implemented in dry-run mode; workflow wrappers, safe apply/re-run, and the external second-project pilot remain incomplete. |
| CAP-017 | Is the API localhost-only or network/multi-user qualified? | experimental | 1 | IDKMesh currently provides a loopback-only local Control Tower API, not a production multi-user service. | The implemented Control Tower API is loopback/local. Network multi-user production qualification remains in issue 713. |
| CAP-018 | Has a capability been externally reproduced? | planned | 0 | External reproduction is an explicit evidence gate, not a current project-wide claim. | The required second-repository/external pilot evidence level has not been reached. |
| CAP-019 | Has swarm value been benchmarked against simpler baselines? | planned | 0 | IDKMesh does not yet claim broad swarm superiority over strong simpler baselines. | Issues 1 and 5 / the strengthening plan require matched real-task baselines before broad superiority claims. |
| CAP-020 | Is a production claim supported by qualification evidence? | planned | 0 | IDKMesh is a research/engineering preview and does not claim project-wide production qualification. | No project-wide evidence-level-5 production qualification is declared; API/release qualification gates remain open. |

## Machine-checkable fields

Each canonical JSON row carries the stable question ID, status, evidence level, implementation paths, specification paths, supported CLI commands, deterministic test/evidence paths, known limitation, last verified source revision, allowed public wording, and an explicit qualification artifact slot. Evidence level 5 requires a dedicated, existing qualification artifact rather than merely a non-empty generic evidence list.

The same validator also checks the twenty required engineering questions, repository-local paths, actual top-level `idkmesh` subcommands, primary README command examples, the Unreleased changelog's capability-matrix/evidence-level linkage, and the generated Markdown/homepage projections.

Run the drift guard locally with:

```bash
python scripts/check_capability_matrix.py
```

After changing the canonical JSON, regenerate the two derived surfaces with:

```bash
python scripts/check_capability_matrix.py --write
```

## Promotion rule

Promoting a row is an evidence change, not a wording change. Update the canonical JSON only when the new implementation/evidence paths are committed and the public wording remains no stronger than the evidence level. Keep a limitation when it still applies even after implementation.
