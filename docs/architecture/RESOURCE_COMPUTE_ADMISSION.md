# Resource → Compute Admission

**Status:** executable v0 integration contract  
**Date:** 2026-08-28  
**Scope:** Free Resource Mesh → Opportunistic Compute Fabric

## Executive decision

IDKMesh must not transform a public statement such as “this service has a free tier” into executable compute authority.

The admission layer is therefore **subtractive, not generative**.

```text
external provider evidence
        +
checked-in local authorization
        +
already-concrete live Compute Offer
        |
        v
Resource → Compute Admission
        |
        v
smaller admitted Compute Offer Pool
        |
        v
existing free_compute_router.py
```

The bridge can remove offers. It cannot create CPU, GPU, model, trust, correctness, repository-write, or merge authority.

## Why this layer exists

The Free Resource Mesh and Opportunistic Compute Fabric answer different questions:

- **Resource Mesh:** Is a resource/service class still real, current, zero-project-cost, and acceptable under privacy/security constraints?
- **Compute Offer Pool:** What concrete machine/runtime capacity exists right now?
- **Free Compute Router:** Which concrete eligible offer satisfies a Work Unit under the repository's hard `$0` policy?

Without an explicit bridge, a future implementation could accidentally bypass one of those layers.

This contract makes the boundary executable.

## The two-key temporal gate

A concrete offer is admitted only when **two independently maintained authorization records are current**.

Future-dated evidence is not “extra fresh.” It fails closed because it cannot yet have been observed or reviewed at the evaluator's `today` date.

### Key A — external resource evidence

The Free Resource Mesh registry must say that the resource class:

- exists and is not excluded;
- remains zero-project-cost;
- is a direct compute class (`compute` or `volunteer_compute`);
- has fresh, non-future source evidence;
- still exposes the broad resource capabilities the local binding says are required;
- has no repository-write authority;
- has no merge authority.

### Key B — local project authorization

`config/resource-compute-bindings.json` must contain a fresh, non-future, enabled binding that explicitly states:

- which Free Resource Mesh resource class is being authorized;
- which concrete provider identifier it may admit;
- which cost classes are permitted;
- which **resource/discovery capability names** must still be present in Key A;
- which **concrete runtime capability names** are permitted after materialization;
- whether current terms have been reviewed as eligible;
- the authorization scope;
- review date and expiration window.

A provider's marketing page cannot supply Key B. A checked-in binding cannot supply Key A indefinitely because its corresponding external evidence expires.

## Concrete offer remains mandatory

Even with both keys, there must already be a concrete offer in `compute-offer-pool-v0.1`.

That concrete offer carries runtime facts such as:

- current availability;
- CPU/RAM/disk/GPU capacity;
- trust classification;
- expected wait;
- observed success probability;
- independence group;
- concrete capability tags.

The bridge never invents these facts.

## Admission algorithm

For every concrete compute offer `o`, find a matching binding `b` and bound registry resource `r`.

The offer survives only when:

```text
match_provider(b, o)
AND cost_class(o) in allowed_cost_classes(b)
AND optional_offer_prefix_match(b, o)
AND enabled(b)
AND terms_eligible(b)
AND fresh_non_future(binding_review(b))
AND r exists
AND kind(r) in {compute, volunteer_compute}
AND status(r) in {available, conditional}
AND fresh_non_future(external_evidence(r))
AND required_resource_capabilities(b) subset_of capabilities(r)
AND project_cost(r) = 0
AND project_cost(o) = 0
AND available(o)
AND repo_write_authority(r) = false
AND merge_authority(r) = false
AND capabilities(o) subset_of allowed_capabilities(b)
```

The top-level registry observation date must also not be in the future.

If no binding matches, the offer is rejected.

If more than one binding matches, the offer is rejected as ambiguous.

This is deliberate fail-closed behavior.

## Capability materialization: two vocabularies, two gates

The Resource Mesh and the concrete Compute Offer Pool intentionally describe capabilities at different abstraction levels.

Example Resource Mesh capability evidence may say:

```text
git
python
ephemeral_vm
docker
```

while a concrete runtime offer may expose scheduler-facing capabilities such as:

```text
json-schema-validation
deterministic-local-execution
linux
python
```

These sets are **not expected to be string-equal**. Treating them as one vocabulary would either create false rejections or encourage invented equivalences.

The checked-in binding therefore carries two independent controls:

```text
required_resource_capabilities
    = broad capabilities that must remain present in external/discovery evidence

allowed_capabilities
    = concrete runtime capabilities the project is willing to admit
```

Admission requires both gates. The binding is the reviewed materialization relationship between them; the bridge does not infer new capabilities merely because names look similar.

This means two different forms of drift fail closed:

1. **external evidence contraction** — a resource stops claiming a broad capability required by the binding;
2. **runtime capability expansion** — a concrete offer exposes a capability not explicitly allowed by the binding.

A change to either side requires reviewed evidence or binding changes.

## Current binding

v0 authorizes exactly one resource-class → concrete-provider path:

```text
Free Resource Mesh:
  github-actions-public-standard

required Resource Mesh capability evidence:
  git
  python
  ephemeral_vm

binding:
  github-public-ci-v0

concrete provider:
  github-actions

allowed concrete runtime capabilities:
  json-schema-validation
  deterministic-local-execution
  linux
  python

allowed cost class:
  public_project_ci

scope:
  legitimate CI, verification, reproducibility, testing,
  and bounded repository experiments for this public project
```

The existing example offer `github-public-ci` can therefore survive admission when all freshness, evidence, and policy checks pass.

The following existing example offers do **not** survive this bridge by default:

- generic paid cloud — no binding and non-zero project cost;
- volunteer-node example — no resource-class binding yet;
- illustrative unavailable grant GPU — no binding and unavailable.

That is intentional.

## Volunteer resources

A volunteer binding should not be added merely because `volunteer-ollama-local` exists in the Resource Mesh registry.

The binding should be added only after the runtime path can prove:

1. explicit donor opt-in;
2. capped concrete resources;
3. canonical node/adapter boundary;
4. no broad GitHub token in the task sandbox;
5. safe cleanup/stop semantics;
6. current concrete capabilities;
7. independent result verification.

This keeps PR #91's human integration gate meaningful rather than routing around it.

## Hosted agents are not direct compute

Hosted/manual agents such as Gemini or Jules are intentionally rejected by this bridge because their Resource Mesh kind is not a direct compute class.

They belong to the separate hosted-agent adapter lane:

```text
bounded public task
 -> explicit provider/account/secret consent
 -> advisory/candidate output
 -> canonical evidence
 -> independent verification
 -> human decision
```

They must not be disguised as CPU/GPU offers merely to reuse the compute router.

## Machine-readable surfaces

- `scripts/resource_compute_admission.py` — deterministic subtractive bridge;
- `tests/test_resource_compute_admission.py` — fail-closed policy tests;
- `schemas/resource-compute-bindings-v0.1.schema.json` — binding schema;
- `config/resource-compute-bindings.json` — current project authorization;
- `.github/workflows/free-resource-plan.yml` — end-to-end proof against the existing router.

The workflow demonstrates:

```text
Free Resource Mesh registry
 -> binding admission
 -> filtered Compute Offer Pool
 -> existing free_compute_router.py
 -> zero-project-cost GitHub public CI selection
```

No workload is dispatched by the bridge itself.

## Authority boundary

The following implications are invalid:

```text
free resource        => trusted resource          [false]
admitted resource    => correct worker            [false]
selected compute     => correct result            [false]
worker success       => accepted candidate        [false]
agent confidence     => evidence                  [false]
```

The correct chain remains:

```text
admission
 -> selection
 -> bounded execution
 -> ResultManifest
 -> independent VerificationResult / Evidence Report
 -> explicit human/governance integration decision
```

## Operational policy

The binding file is intentionally treated like infrastructure policy, not ordinary descriptive documentation.

Changes should be reviewed for:

- provider terms/eligibility;
- monetary implications;
- external resource-evidence requirements;
- concrete capability expansion;
- security boundary changes;
- privacy/external-processing implications;
- donor consent semantics;
- relationship to branch protection and repository governance.

A binding should expire rather than remain trusted indefinitely, and evidence from the future must never satisfy freshness.

## Success criterion

This bridge is successful when IDKMesh can add and remove free/donated compute backends without changing Work Units or the core router, while preserving these invariants:

> **No eligible zero-project-cost, explicitly admitted concrete offer → no execution selection.**

and

> **Admission never grants correctness or integration authority.**
