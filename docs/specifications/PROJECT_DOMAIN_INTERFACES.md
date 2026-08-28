# ProjectManifest and DomainPack interfaces

**Status:** v0.1 contract proposal  
**Tracking:** issue #6

## Purpose

IDKMesh is a reusable collaboration framework, not one fixed application. The architectural boundary is:

```text
IDKMesh Core
    |
    v
DomainPack
    |
    v
ProjectManifest
    |
    v
bounded Work Units / evidence / integration decisions
```

Core owns generic coordination primitives. A DomainPack declares reusable domain policy. A ProjectManifest binds one actual project to one or more DomainPacks and narrows what that project permits.

The v0.1 contract is intentionally declarative and fail-closed. Loading a manifest validates configuration; it does not import arbitrary plugins, execute project commands, discover credentials, or grant repository authority.

## Layer 1 — Core

Core remains model-, vendor-, forge-, and project-independent. For this contract version, the exact supported boundary is:

```text
Core API:       0.1
WorkUnit schema: 0.2
```

The ProjectManifest/DomainPack validator treats these as exact compatibility identifiers, not semver ranges.

Core primitives include bounded Work Units, capability/resource matching, artifacts, verification evidence, provenance, scheduling, governance interfaces, and experiment/metric infrastructure.

## Layer 2 — DomainPack

A DomainPack defines reusable rules for a domain without naming one particular project.

`schemas/domain-pack.schema.json` includes:

- domain identity/version;
- exact Core/WorkUnit compatibility;
- domain-supported Work Unit kinds;
- default risk class per kind;
- required verification policy per kind;
- required capabilities/evidence;
- reusable verification policies;
- worker role/capability descriptions;
- risk classes;
- adapter interface definitions plus required/optional sets;
- default metrics;
- compatibility and breaking-change policy.

The first reference pack is:

`examples/domain-packs/software-engineering-v0.1.domain-pack.json`

It uses vendor-neutral capabilities such as `repository-edit`, `test-execution`, `repository-read`, and `deterministic-execution`. It does not prescribe GitHub, one model vendor, or one worker implementation.

## Layer 3 — ProjectManifest

A ProjectManifest declares an actual project while reusing Core and DomainPack contracts.

`schemas/project-manifest.schema.json` includes:

- project identity/version;
- Core/WorkUnit compatibility;
- repository/artifact/dataset/knowledge roots;
- Goal Graph/document entrypoints;
- exact DomainPack references by id/version/path;
- allowed Work Unit kinds;
- default verification requirements;
- risk policy and maximum autonomous risk;
- integration policy;
- governance roles/references;
- project metrics;
- worker capability constraints;
- storage/provenance roots;
- enabled adapter IDs.

The manifest may **narrow** a DomainPack. It may not silently weaken required verification or invent capabilities the DomainPack does not define.

## Reference projects

Two different manifests intentionally bind to the same Core and software-engineering DomainPack.

### IDKMesh improving IDKMesh

`examples/projects/idkmesh-self-improvement.project.json`

This project permits bounded coding/testing/review/benchmark/documentation/research/integration work. Its default code-change policy requires an independent verifier and protected human integration. Automatic merge is false.

### IDKMesh research replication

`examples/projects/idkmesh-research-replication.project.json`

This project uses the same Core and DomainPack but permits only benchmark/research/documentation/review work. The repository root is read-only, maximum autonomous risk is `none`, integration mode is proposal-only, and repository-write/merge authority is forbidden.

This demonstrates the intended property:

```text
same Core + same DomainPack
        |
        +-- Project A: bounded repository improvement
        +-- Project B: read-only research replication
```

No coordinator-core code changes are needed to define the second project.

## v0.1 compatibility rules

### 1. Exact Core matching

ProjectManifest and every referenced DomainPack must declare exactly the supported Core API and WorkUnit schema versions.

```text
project.core_compatibility == pack.core_compatibility
```

The v0.1 validator also requires:

```text
core_api_version == 0.1
work_unit_schema_version == 0.2
```

There is no `>=`, caret range, wildcard, or best-effort downgrade.

### 2. Exact DomainPack binding

A ProjectManifest references a DomainPack by all three:

```text
id
version
repository-relative path
```

The loaded document must match the declared id and version exactly. Pack paths must resolve inside the repository root.

### 3. Schema version is not object version

`schema_version` identifies the JSON contract shape. `version` identifies the semantic revision of a particular DomainPack or ProjectManifest.

A schema-compatible object can therefore advance its patch/minor semantic version without changing the schema, provided its stated compatibility remains truthful.

### 4. Breaking DomainPack semantics require explicit rebinding

A DomainPack must not silently redefine an existing verification policy, adapter interface, Work Unit meaning, or risk requirement under an incompatible semantic revision.

The software-engineering pack states the bootstrap rule:

> Breaking semantics require a new DomainPack major version or schema version and explicit ProjectManifest re-binding; silent downgrade is forbidden.

### 5. No implicit compatibility inheritance

Historical success with one DomainPack/project version is evidence about that exact contract, not automatic approval for a changed version.

This mirrors IDKMesh's broader exact-head/evidence-binding principle.

## Multi-DomainPack composition

A future project may reference multiple DomainPacks. v0.1 composes them conservatively.

The validator builds unions of supported Work Unit kinds, risk IDs, verification policies, and adapter definitions, with these fail-closed rules:

- repeated DomainPack IDs are rejected;
- policy IDs may coexist across packs only if their complete definitions are identical;
- adapter IDs may coexist across packs only if their complete definitions are identical;
- conflicting same-ID definitions are rejected;
- all DomainPack-required adapters remain required by the project;
- project-enabled Work Unit kinds must exist in at least one loaded pack;
- project risk classes must be supplied by the loaded packs.

This prevents load order from becoming hidden policy authority.

## Verification non-weakening rule

The ProjectManifest default verification policy must resolve to a policy supplied by a referenced DomainPack.

A project may strengthen a policy, for example by requiring more independent verifiers or requiring human integration where the DomainPack does not. It may not weaken the DomainPack minimum.

For the default policy:

```text
project.minimum_independent_verifiers
    >= domain_policy.minimum_independent_verifiers
```

If the DomainPack policy requires human integration, the project must keep both:

```text
verification.human_integration_required = true
integration_policy.human_decision_required = true
```

Workers remain evidence producers. Neither a ProjectManifest nor a DomainPack can make worker success equal acceptance.

## Adapter discovery rules

Adapters are declared by stable **IDs and interface contracts**, not executable module paths.

A DomainPack adapter definition contains:

```text
id
interface
discovery
trust_boundary
```

Example:

```text
id        = software.metadata-verifier
interface = idkmesh.adapter.verifier/v0.1
discovery = registry
```

Allowed discovery modes are:

- `builtin` — known to the trusted Core distribution;
- `registry` — resolved from a separately governed adapter registry;
- `project-manifest` — bound to a declared project resource/root;
- `external` — requires a separately implemented trust/consent boundary.

The ProjectManifest only enables adapter IDs already defined by its DomainPacks. Required adapter IDs cannot be omitted.

### Critical execution boundary

`experiments/project_contracts.py` does **not** dynamically import an adapter named in either manifest. It does not interpret adapter IDs as Python modules, shell commands, URLs, package names, or repository write permissions.

Future runtime adapter resolution must be a separate Core-owned mechanism with its own allowlist, capability, provenance, and security rules.

This means:

```text
configuration reference != executable authority
```

## Risk and integration boundaries

A ProjectManifest may restrict which DomainPack risk classes are available and may set a lower maximum autonomous risk.

For example, the research-replication project sets:

```text
maximum_autonomous_risk = none
integration mode        = proposal_only
automatic merge         = false
human decision          = true
```

The self-improvement project allows low/medium/high classification but caps autonomous risk at low and still requires protected human integration for its default code-change path.

A manifest that says both `automatic_merge_allowed=true` and `human_decision_required=true` is rejected as internally contradictory in v0.1.

Repository settings remain external authority. A manifest cannot create branch protection, bypass rulesets, mint credentials, or grant a GitHub token more permission.

## Deterministic validation

`experiments/project_contracts.py` validates schema and cross-object composition without executing project work.

The reference validation proves that two distinct projects load against one Core/WorkUnit contract and one software-engineering DomainPack.

Negative tests reject at least:

- unsupported project Work Unit kinds;
- omitted required adapters;
- weakened independent-verifier minimums;
- Core API mismatch;
- silent DomainPack version rebinding;
- DomainPack paths escaping the repository root.

`tests/test_project_contracts.py` makes these properties explicit, and `.github/workflows/project-domain-contracts-check.yml` runs them read-only on Python 3.11 and 3.13.

## What v0.1 deliberately does not do

- no dynamic plugin loading;
- no dependency solving across version ranges;
- no remote DomainPack fetching;
- no package manager;
- no secret/credential resolution;
- no model-provider selection;
- no forge-specific API calls;
- no Work Unit execution;
- no verification execution;
- no integration/merge action;
- no autonomous governance mutation.

Those capabilities should be added only behind separately reviewed interfaces when real use cases require them.

## Evolution rule

The boundary should evolve from evidence rather than abstraction pressure:

```text
new project need
 -> bounded contract extension
 -> deterministic compatibility tests
 -> explicit version change
 -> migration/rebinding evidence
 -> only then runtime adoption
```

The central invariant remains:

> Core should coordinate generic work; DomainPacks should express reusable domain rules; projects should choose and narrow those rules without becoming executable authority themselves.
