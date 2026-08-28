# IDKMesh interoperability and system evaluation

**Date:** 2026-08-28  
**Scope:** current `main` plus the `interop-runtime-integration` development branch

## Executive assessment

IDKMesh now has a credible **contract-first kernel**, but it is not yet a complete Verified Swarm Runner.

The strongest parts are:

- a distinctive verification-first thesis;
- explicit Work Unit and worker ResultManifest contracts;
- reproducible Phase 0 fixtures and CI;
- strong public research/governance/community records;
- a coherent long-term scaling model;
- a growing set of contributor-facing research and implementation issues.

The weakest parts are:

- no independent verifier/Evidence Report implementation on `main` yet;
- no fully exercised real local worker runtime on `main` yet;
- no production A2A/MCP adapter against a real SDK/server yet;
- no real multi-worker orchestration run yet;
- scalability remains primarily a research hypothesis rather than measured deployment evidence.

The most important architectural finding is that **IDKMesh does not need to invent another generic agent wire protocol**. Current A2A and MCP standards cover large portions of remote agent/tool interoperability. IDKMesh should own the semantics they do not guarantee: bounded work contracts, risk, verification policy, evidence, provenance, diversity/error-correlation-aware scheduling, and integration decisions.

---

## Maturity scale

This audit uses:

- **0 — idea:** proposed only;
- **1 — documented:** design/process exists;
- **2 — executable contract/prototype:** machine-readable schema, tests, or prototype exists;
- **3 — validated:** exercised in realistic/reproducible workflows with evidence;
- **4 — scaled:** repeatedly demonstrated across the intended scale/trust environment.

The number is a maturity indicator, not a quality score.

## System maturity matrix

| Area | Maturity | Assessment | Next evidence needed |
| --- | ---: | --- | --- |
| mission / differentiation | 3 | clear verification-first coordination thesis | external contributor/use-case validation |
| community/open-source foundation | 3 | governance, health files, contribution ladder, ACE experiments | recurring external contributors and reviewer delegation |
| Work Unit contract | 2 | canonical JSON Schema + fixtures + CI | use across local + external adapters and real tasks |
| worker ResultManifest | 2 | canonical schema separates self-report from acceptance | emitted by a real worker and consumed by verifier |
| experiment reproducibility | 2–3 | deterministic harness and schema CI exist | real agent runs with pinned environments/models |
| interoperability semantics | 2 after this branch | executable lossless A2A/MCP bindings + tests | validate against real A2A 1.0 and MCP 2026-07-28 SDKs |
| local execution runtime | 2 after this branch | canonical Docker binding + mocked tests | one real Docker acceptance run on immutable commit |
| independent verification | 1 | architecture/issues are strong; runtime missing | Evidence Report schema + verifier implementation |
| multi-worker orchestration | 1 | designed in #4/#16 | dispatch 2+ heterogeneous adapters through one coordinator path |
| security/isolation | 2 | least-privilege Docker policy implemented/tested structurally | real adversarial sandbox tests; stronger isolation evaluation |
| provenance | 2 | hashes and canonical provenance fields exist | signatures/attestations/transparency integration |
| agent diversity/correlation | 1 | strong research formulation | measured worker-family/error-correlation data |
| distributed networking | 1 | architecture/references documented | 3–10 real nodes after local kernel works |
| scalability | 1–2 | simulator/research direction strong | empirical scaling curves and control-plane measurements |
| self-evolution | 1–2 | IDKGraph/guarded evolution and ACE concepts exist | bounded shadow experiments with rollback evidence |
| product/UX | 1–2 | Verified Swarm Runner target is defined | installable CLI flow a newcomer can complete |

---

# Interoperability evaluation

## A2A

**Current released line:** A2A 1.0.  
Primary references: https://a2a-protocol.org/latest/specification and https://a2a-protocol.org/latest/whats-new-v1/

### Strong matches

- Agent Card discovery and capability/skill declaration;
- asynchronous, stateful Task lifecycle;
- Messages and structured Parts;
- Artifacts;
- task/context references;
- streaming/push patterns;
- protocol extensions.

### IDKMesh semantics not guaranteed by A2A

- allowed/forbidden repository scope;
- verification policy;
- independent evidence requirements;
- resource/attention budgets;
- project-specific risk policy;
- whether a completed task is trustworthy;
- whether an artifact may be merged/integrated;
- correlated-error/diversity logic.

### Decision

Use A2A as a **remote agent binding**. Carry the complete canonical Work Unit in a namespaced IDKMesh extension/data payload and verify its digest on round-trip.

Do not define a competing general-purpose remote-agent protocol.

## MCP

**Current protocol revision:** 2026-07-28.  
Primary references: https://blog.modelcontextprotocol.io/posts/2026-07-28/ and https://tasks.extensions.modelcontextprotocol.io/

### Strong matches

- tool discovery/calls;
- external context/tool access;
- stateless request routing;
- formal extensions;
- long-running execution through `io.modelcontextprotocol/tasks`;
- polling/cancellation/update lifecycle;
- modern authorization/routing conventions.

### Important current constraint

Tasks support is an extension and SDK support is uneven. The binding must not make MCP Tasks a mandatory requirement for the local kernel.

### IDKMesh semantics not guaranteed by MCP

The same acceptance/evidence/risk semantics listed for A2A remain IDKMesh responsibilities.

### Decision

Use MCP primarily as a **tool/context and optional task binding**. The local v0.1 runtime remains independent of MCP.

---

# Binding architecture implemented in this branch

```text
Canonical Work Unit v0.1
       |
       +------------------------------+
       |               |              |
       v               v              v
 local Docker       A2A 1.0      MCP 2026-07-28
 execution          binding          binding
       |               |              |
       +---------------+--------------+
                       |
                       v
              worker execution state
                       |
                       v
             ResultManifest v0.1
                       |
                       v
          independent verifier (next)
                       |
                       v
                Evidence Report
                       |
                       v
              human/policy decision
```

## Core invariant

```text
external execution completed != IDKMesh accepted
```

A2A `TASK_STATE_COMPLETED` and MCP task `completed` normalize only to:

```text
execution_status = succeeded
acceptance_status = pending_verification
```

## Integrity invariant

The A2A/MCP bindings carry the full canonical Work Unit plus a canonical SHA-256 digest. Round-trip extraction rejects modified contracts.

This deliberately favors semantic preservation over pretending every IDKMesh field has a protocol-native equivalent.

---

# Local runtime integration

The previous local-worker prototype in PR #21 had useful isolation controls but defined a second incompatible object also named Work Unit v0.1 and a custom result protocol.

This branch ports the useful runtime direction onto canonical contracts.

## Canonical input

The worker consumes `schemas/work-unit-v0.1.schema.json`.

Runtime-specific Docker details are carried only in:

```text
extensions.org.idkmesh.execution.docker
```

Source code is represented as a canonical `git_ref` input with an immutable commit digest:

```text
git:<40-character-sha>
```

## Safety policy

The local worker currently requires:

- HTTPS public GitHub source;
- immutable revision;
- `permissions.network = none`;
- no secrets;
- explicit process execution permission;
- allowed container image;
- CPU/RAM/PID/time limits;
- read-only root filesystem;
- capabilities dropped;
- no-new-privileges;
- no Docker socket or home/credential mounts;
- post-execution allowed/forbidden path enforcement.

A successful process that modifies an out-of-scope path becomes a failed worker result.

## Canonical output

The worker writes:

- `result-manifest.json` conforming to worker ResultManifest v0.1;
- `changes.patch`;
- `stdout.txt`;
- `stderr.txt`.

The ResultManifest requests independent validators and explicitly describes the patch as an unverified candidate.

---

# Evaluation by project dimension

## Architecture

**Good:** clean separation is forming between contract, adapter, execution, verification, and integration.

**Risk:** architecture documents still describe many future layers. Contributors may confuse future federation/IDKGraph/market ideas with v0.1 requirements.

**Action:** keep v0.1 dependency graph small and executable.

## Security

**Good:** the project consistently treats workers and prompts as untrusted and avoids giving workers merge authority.

**Risk:** Docker alone is not sufficient for arbitrary hostile public jobs; post-execution path checks detect but do not prevent all bad behavior inside the mounted workspace.

**Action:** run real acceptance/adversarial tests, then compare rootless Docker, gVisor, Firecracker/microVM, and WASI-style backends by risk class.

## Verification

**Good:** the most important conceptual distinction—worker self-report versus acceptance—is already in the schema.

**Critical gap:** there is no canonical independent Evidence Report/verifier runtime yet.

**Action:** this should be the next core implementation after this branch passes CI.

## Scientific rigor

**Good:** hypotheses, negative results, scaling questions, and common metrics are treated seriously.

**Risk:** many algorithm ideas exist without empirical ranking.

**Action:** freeze new mechanism catalogs temporarily and turn selected mechanisms into controlled experiments.

## Community

**Good:** community-first rule, contributor ladder, templates, ACE growth experiments, and public reasoning history are unusually strong for this stage.

**Risk:** generated issues/automation could create activity without durable contributor reproduction.

**Action:** measure second-contribution conversion, reviewer growth, and verified descendants rather than issue count/stars.

## Developer experience

**Good:** schemas, examples, CI, and the local runtime are converging toward a runnable path.

**Gap:** no single top-level install/run demo yet.

**Action:** after verifier exists, make one command run the full local flow and show an Evidence Report.

## Scalability

**Good:** the project correctly avoids claiming that a one-machine prototype proves million-node scale.

**Gap:** no measured network/control-plane curve yet.

**Action:** do not start networking until local work/verification semantics stabilize.

---

# Priority development sequence

## P0 — complete the trusted local loop

1. Merge this interoperability/runtime integration after CI passes.
2. Perform one real Docker acceptance run using the checked-in immutable Work Unit.
3. Implement canonical Evidence Report schema and independent verifier.
4. Connect local worker ResultManifest -> verifier -> human decision.
5. Run the same coordinator path with two worker adapters.

## P1 — real interoperability

6. Validate A2A binding against official A2A 1.0 SDK/types.
7. Validate MCP binding against a 2026-07-28 SDK; keep Tasks optional until runtime support is mature.
8. Add one mock/real remote adapter behind the same worker interface.
9. Convert remote artifacts/results to canonical ResultManifest.
10. Add Agent Card / MCP capability discovery as scheduler input.

## P2 — flagship evidence

11. Execute the single-versus-many experiment with fixed budgets.
12. Measure error correlation, verification cost, human review minutes, and accepted regression-free output.
13. Publish raw reproducible results, including failures.

## P3 — distributed mesh

14. Only then move to 3–10 real nodes.
15. Introduce signed Work Units/results and stronger provenance.
16. Test churn, partitions, malicious/slow workers, retries, and backpressure.

---

# Immediate merge gates for this branch

- interoperability unit tests pass;
- Phase 0 contract validation still passes;
- node unit tests pass without Docker;
- checked-in canonical local Work Unit validates;
- GitHub Actions reports success;
- no external protocol completion can set an acceptance state;
- no duplicate Work Unit or worker-result protocol is introduced.

A real Docker execution is deliberately a post-merge/local acceptance gate if Docker is unavailable in CI; it must be recorded before calling the runtime validated maturity level 3.
