# IDKMesh interoperability and system maturity audit

**Date:** 2026-08-28  
**Scope:** current public repository plus active interoperability/runtime work

## Executive conclusion

IDKMesh has moved from an architecture notebook into an **executable contract-and-experiment project**.

The most important architectural conclusion is now clearer:

> IDKMesh should not become another generic agent protocol. It should be the verification-first coordination layer that turns heterogeneous human/agent/compute execution into bounded, comparable, independently verified candidate work.

Current external standards are sufficient to cover large parts of generic interoperability:

- A2A 1.0 for remote-agent discovery, task lifecycle, messages, and artifacts;
- MCP 2026-07-28 for tool/context integration and optional Tasks-style asynchronous execution.

IDKMesh should preserve the semantics those protocols do not guarantee:

- WorkUnit capability/resource requirements;
- security, permissions, and trust class;
- verification policy and required evidence;
- provenance;
- worker/result independence;
- diversity/error-correlation-aware coordination;
- integration/merge policy.

The critical invariant is:

```text
external execution completed != IDKMesh accepted
```

## Maturity scale

- **0 — idea:** proposed only
- **1 — documented:** design/process exists
- **2 — executable:** schema, deterministic code, tests, or bounded prototype exists
- **3 — validated:** exercised in realistic/reproducible workflows with evidence
- **4 — scaled:** repeatedly demonstrated across the intended scale/trust environment

This is a maturity indicator, not a quality score.

## Current maturity matrix

| Dimension | Maturity | Evidence | Highest-priority gap |
| --- | ---: | --- | --- |
| mission/differentiation | 3 | verification-first collective engineering thesis is coherent and public | external use-case/contributor validation |
| open-source/community foundation | 3 | governance, community-health files, ACE experiment, starter tasks | recurring external contributors and distributed review ownership |
| canonical WorkUnit | 3 | WorkUnit v0.2, fixtures, harness, CI, issue #3 complete | use through multiple real adapters |
| worker ResultManifest | 2–3 | v0.1 contract + relationship checks | canonical runtime output from validated real worker runs |
| independent VerificationResult | 2–3 | v0.1 contract and trust-boundary checks merged in PR #47 | real hidden/test/security verifier execution |
| A2A/MCP interoperability | 2 | v0.2 field mapping + digest-protected semantic round-trip tests in this branch | official SDK conformance + real remote adapter |
| local execution runtime | 2 | canonical node backend in PR #34 with policy/unit CI | controlled Docker acceptance issue #37 and merge |
| multi-worker orchestration | 1–2 | product/issue design is clear | one coordinator path dispatching 2+ heterogeneous adapters |
| experiment/research harness | 3 | deterministic Phase 0, randomness lab, R1 diversity/replication experiment | connect synthetic results to real repository-agent tasks |
| security/isolation | 2–3 | explicit risk/trust/permissions, bounded Docker design, independent verification | protect `main`; real adversarial isolation tests; stronger sandbox tiers |
| provenance | 2 | hashes/digests, source revisions, worker/verifier provenance | signatures/attestations and transparency evidence where justified |
| zero-cost compute policy | 2–3 | zero-project-spend schemas/router/policy work | real local capability discovery (#52) |
| distributed networking | 1 | architecture and references are strong | defer until trusted local loop is complete |
| scalability | 2 | simulators/randomness/scheduling research is executable | real multi-node control-plane curves |
| guarded self-evolution | 2 | ACE, deterministic evolution scoring, repository observatory work | protected integration boundary + outcome-based calibration |
| product/developer UX | 1–2 | Verified Swarm Runner target is clear | one install/run path producing worker + independent verifier evidence |
| integration/review capacity | 2 | governance/process exists | actual repository activity is already outrunning easy integration |

## Interoperability architecture

The preferred boundary is now:

```text
                      +--> local node / sandbox
                      |
WorkUnit v0.2 --------+--> A2A remote agent
                      |
                      +--> MCP tool/task
                      |
                      +--> future mini-SWE/OpenHands/human adapters
                                |
                                v
                       ResultManifest v0.1
                                |
                                v
                    VerificationResult v0.1
                                |
                                v
                    human/policy integration
```

### A2A

A2A is a strong remote-agent binding because it already has Agent Cards, task state, messages/parts, artifacts, and extensions.

IDKMesh-specific security/verification/evidence semantics remain in the canonical WorkUnit and a namespaced extension payload.

### MCP

MCP is a strong tool/context binding. The 2026-07-28 protocol extension model and `io.modelcontextprotocol/tasks` can support long-running tool operations where useful.

MCP Tasks must remain optional because local execution and some SDK paths should not depend on it.

### Lossless mapping rule

Protocol-native fields are hints/transport conveniences. The full canonical WorkUnit plus digest travels through the binding so that risk, permissions, budgets, verification rules, or provenance cannot silently disappear.

## Trust-boundary correction

The repository now has the right three-stage separation:

1. **WorkUnit v0.2** — what may be done, under what capability/security/verification contract.
2. **ResultManifest v0.1** — worker self-report and candidate artifacts.
3. **VerificationResult v0.1** — independent verifier evidence/recommendation.

Neither ResultManifest nor VerificationResult is the final merge/integration authority.

This is more defensible than the earlier wording in IDKIP-0001 that called ResultManifest itself the Evidence Report.

## Architecture strengths

- Core contracts are model/vendor/forge neutral.
- WorkUnit v0.2 makes resources, trust, sandboxing, and independent verification explicit.
- Versioned historical schemas preserve reproducibility rather than rewriting history.
- External protocols can evolve independently of core WorkUnit semantics.
- Worker and verifier roles are structurally separated.
- Zero project-spend policy is encoded rather than left as prose.
- Scientific experiments preserve negative-result and uncertainty framing.

## Architecture risks

### 1. Integration is already the scarce resource

During this audit/development turn, `main` and the canonical-node branch advanced repeatedly while integration work was being prepared. Several attempted fast-forward updates were correctly rejected because concurrent work had changed the branch.

This is useful evidence, not merely inconvenience:

> **Generation is already scaling faster than effortless integration.**

The project should instrument/reduce this cost rather than respond by generating more parallel artifacts.

### 2. `main` is still unprotected

Public branch metadata currently reports `main` as unprotected. Issue #35 correctly treats this as a P0 gate before stronger autonomous repository writes.

No agent/community-growth/self-evolution system should gain bypass authority until GitHub branch/ruleset protections are actually enabled and independently checked.

### 3. Docker is not the final hostile-workload boundary

The local-node MVP has sensible least-privilege controls, but a writable repository mount plus ordinary Docker is not sufficient containment for arbitrary hostile public workloads.

Use controlled low-risk public tasks first, then benchmark stronger risk-tiered isolation such as rootless containers, gVisor, microVMs/Firecracker, or WASI-style execution.

### 4. Verification execution lags verification contracts

The independent VerificationResult contract now exists, but issue #5 remains open for the actual hidden evaluator, unauthorized-change/dependency checks, and benchmark task set.

That should take priority over adding another layer of orchestration theory.

## Community evaluation

Community engineering is unusually mature relative to code maturity:

- community-first project rule;
- explicit contributor ladder;
- issue/PR templates;
- starter Growth Seeds;
- ACE reproduction/capacity experiment;
- conversation/decision preservation.

However, ACE's own ledger is currently in **CONSOLIDATE** mode with a high review-load proxy and a very small capacity multiplier. That is a strong signal to prefer review, integration, reproducibility, and second-contribution conversion over spawning more issues or generated proposals.

Recommended community KPI for the next stage:

```text
verified useful descendants
---------------------------
reviewer + maintainer time
```

not raw issue/PR/star volume.

## Scientific/research evaluation

The project now has executable research rather than only cross-disciplinary analogies:

- deterministic Phase 0 harness;
- randomness-lab policies and repeated seeded trials;
- R1 diversity-vs-replication experiment;
- emergence/criticality/scheduling/evolution tracks.

The next research discipline should be **connection to real system artifacts**:

- real WorkUnits;
- real worker adapters;
- real VerificationResults;
- measured human review time;
- correlated failure across actual agent families.

Avoid expanding the algorithm catalog faster than experiments can falsify it.

## Priority development gates

### P0 — trusted local loop

1. Complete/review PR #34 against current WorkUnit v0.2 and satisfy controlled Docker acceptance issue #37.
2. Finish issue #5's actual verifier execution: hidden tests/checks, scope/dependency checks, evidence artifacts.
3. Build the common worker-adapter interface and dispatch one WorkUnit through at least two heterogeneous adapters.
4. Connect ResultManifest -> independent VerificationResult -> explicit human/policy decision.
5. Provide one newcomer-runnable command for that full local path.

### P0 — repository safety

6. Complete issue #35 by enabling actual GitHub protection/ruleset for `main` through repository administration.
7. Keep autonomous write actuators fail-closed until that external guard is verified.

### P1 — interoperability evidence

8. Merge the semantic A2A/MCP binding tests from this branch after review/CI.
9. Add official A2A 1.0 SDK conformance.
10. Add MCP 2026-07-28 implementation conformance while keeping Tasks optional.
11. Normalize a real remote-agent output into ResultManifest v0.1 and pass it through the same independent verifier as local workers.

### P1 — flagship product evidence

12. Run the same bounded repository task with one strong baseline, replication, and heterogeneous workers.
13. Record hidden/independent verification, human review minutes, compute, wall time, error correlation, and negative results.

### P2 — distributed mesh

14. Only after the local trust loop works, move to 3–10 real nodes.
15. Add signatures/attestations and stronger provenance where threat models justify them.
16. Test churn, partitions, malicious/slow workers, verifier backpressure, and recovery.

## Current go/no-go rules

**Go now:** contracts, verification execution, adapter interface, interoperability conformance, local acceptance, branch protection, contributor review capacity.

**Defer:** custom agent wire protocol, global scheduler, token economy, public hostile volunteer jobs, million-node claims, autonomous merging.

## Overall assessment

IDKMesh is now technically interesting because its distinct layer is becoming executable:

```text
bounded work + heterogeneous execution + independent evidence + guarded integration
```

The next success is not another architecture document. It is one fully reproducible local run in which two different workers produce candidates, an independent verifier produces VerificationResult evidence, and a human can inspect why a candidate should or should not be integrated.
