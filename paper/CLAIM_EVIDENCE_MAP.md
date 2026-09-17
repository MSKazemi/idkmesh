# IDKMesh claim-to-evidence map

Status: paper-maintenance artifact, not a manuscript

Last repository audit: 2026-09-17 against
`main@1698e1fa535b940c20bf35f4ab0e12916a46b690`.

This map prevents paper-facing statements from becoming detached from the code,
experiments, and limitations that support them. Wording below is deliberately
narrow. It is a review constraint for a future canonical manuscript, not text to
paste into a paper without checking the manuscript context.

Evidence classes follow [`README.md`](README.md).

| ID | Narrow paper-facing statement | Evidence class | Primary repository evidence | Required limitation / interpretation |
| --- | --- | --- | --- | --- |
| `P-ARCH-001` | IDKMesh defines explicit work, evidence, and authority boundaries for its verified-swarm architecture. | `implemented` | [`../ARCHITECTURE.md`](../ARCHITECTURE.md), [`../PROJECT_RULES.md`](../PROJECT_RULES.md) | An architectural contract is not evidence of Internet-scale operation, independent governance, or production reliability. |
| `P-STATUS-001` | The repository separates implemented capability from staged or future work. | `implemented` | [`../ROADMAP.md`](../ROADMAP.md), [`../ARCHITECTURE.md`](../ARCHITECTURE.md) | Paper wording must follow the current status boundary; roadmap items are not completed capabilities. |
| `P-INTEROP-001` | IDKMesh has deterministic in-process A2A and MCP mapping/conformance paths against pinned optional SDKs. | `implemented` | [`../interop/README.md`](../interop/README.md), [`../requirements-interoperability.txt`](../requirements-interoperability.txt) | This is not a claim of deployed network integrations with arbitrary external agent systems. SDK conformance is protocol-boundary evidence only. |
| `P-INTEROP-002` | A2A and MCP optional SDK conformance admission is independent: an installed protocol SDK can be exercised without the unrelated SDK. | `implemented` | [`../interop/README.md`](../interop/README.md), [`../interop/tests/test_sdk_conformance.py`](../interop/tests/test_sdk_conformance.py) | Availability/skip logic does not prove that every SDK installation or platform succeeds; a skipped test is not conformance evidence. |
| `P-R1-001` | The R1 research track studies when diversity/replication helps or hurts under controlled conditions and includes a real-corpus readiness gate. | `synthetic` / `implemented` | [`../docs/research/R1_SWARM_DIVERSITY_EXPERIMENT.md`](../docs/research/R1_SWARM_DIVERSITY_EXPERIMENT.md), [`../docs/research/R1_CORPUS_READINESS.md`](../docs/research/R1_CORPUS_READINESS.md) | Synthetic R1 outcomes are not real coding-agent performance. A readiness contract is not a real-corpus outcome. |
| `P-E029-001` | E029 recorded 60 attempts from a pinned 0.5B open-weight producer on the frozen benchmark, with 0 accepted and 56/60 failing the diff protocol before repository content was consulted. | `observed-real-run` | [`../experiments/E029-first-real-model-attempts.md`](../experiments/E029-first-real-model-attempts.md), [`../docs/research/README.md`](../docs/research/README.md) | This is a bounded run on one pinned model/workload lineage, not a general statement about language models or production agent systems. Preserve the negative result. |
| `P-COLLAB-001` | Collaboration-observables analyzer v0.2 treats empty reviewer/owner HHI populations as undefined (`null`) rather than numeric zero. | `implemented` | [`../docs/research/COLLABORATION_OBSERVABLES_V0_1.md`](../docs/research/COLLABORATION_OBSERVABLES_V0_1.md), [`../scripts/collaboration_observables.py`](../scripts/collaboration_observables.py) | Historical v0.1 evidence remains immutable. Its empty-population `0.0` must not be reinterpreted as distributed participation; there were no eligible observations. |
| `P-GOV-001` | Project-operated or owner-controlled AI automation does not count as independent human/external review. | `implemented` | [`../PROJECT_RULES.md`](../PROJECT_RULES.md), [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | Do not use agent count, bot activity, or owner-controlled automated review as evidence of independent community validation. |
| `P-SCALE-001` | Internet-scale, multi-organization production behavior remains unresolved/staged rather than demonstrated by the repository evidence. | `unresolved` | [`../ROADMAP.md`](../ROADMAP.md), [`../docs/research/FIRST_RESEARCH_PROGRAM.md`](../docs/research/FIRST_RESEARCH_PROGRAM.md) | Present this as a limitation/future-work boundary, not as achieved scale. |
| `P-PAPER-001` | No canonical editable manuscript source is currently versioned in this repository. | `unresolved` | [`README.md`](README.md), [issue #478](https://github.com/MSKazemi/idkmesh/issues/478) | Until the real source is imported or an external canonical source is documented, a steward cannot truthfully claim an in-place manuscript review. |

## Quantitative-claim rule

Any manuscript number that is not a timeless protocol constant should carry enough
provenance to reproduce or audit it. At minimum record:

- the experiment/result identifier;
- exact repository revision or immutable release/tag/digest used;
- command or workflow that produced the number, when repository-generated;
- input fixture/corpus/model identity;
- whether the result is synthetic, observed real-run, or independently reviewed;
- exclusions, failed runs, negative outcomes, and known threats to validity.

If a number cannot meet that bar, downgrade it to a qualitative statement or mark
it unresolved until evidence is available.

## Change-impact checklist

Use this when code, documentation, or experiments move:

- **Architecture/interface change:** review `P-ARCH-*`, `P-STATUS-*`, and relevant
  interoperability claims.
- **Protocol/SDK change:** review `P-INTEROP-*`, including pins, protocol
  revisions, skip/conformance semantics, and the distinction between in-process
  validation and deployed integration.
- **Experiment rerun/new result:** add or revise a claim only after preserving the
  old artifact and classifying the new evidence. Negative or null results remain
  part of the record.
- **Metric contract change:** distinguish historical artifact semantics from the
  current analyzer contract, as `P-COLLAB-001` does for HHI v0.1/v0.2.
- **Community/agent automation change:** review independence/provenance language;
  automation volume is not independent validation.
- **Roadmap completion:** change `unresolved` only when the required evidence has
  actually landed, not when an issue or PR merely proposes it.

## Known gap

This map can be maintained and link-checked now, but it cannot be reconciled
section-by-section against manuscript prose until issue #478 supplies the
canonical manuscript source or an explicit external synchronization procedure.
