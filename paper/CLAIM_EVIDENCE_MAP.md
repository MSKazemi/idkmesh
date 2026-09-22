# IDKMesh claim-to-evidence map

Status: paper-maintenance artifact, not a manuscript

Last repository audit: 2026-09-19 against
`main@d03bf2f048f7280e8e908193bd4158418b87183f`.

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
| `P-INTEROP-003` | The A2A 1.0 decoder fails closed when IDKMesh-controlled semantic task surfaces disagree with the canonical Work Unit, including native objective text, Work Unit ID/digest metadata, extension declarations, and canonical payload digest. A2A `messageId` remains sender-owned transport correlation: it must be a non-empty string but need not equal IDKMesh's emitted deterministic value. | `implemented` | [`../interop/A2A_SEMANTIC_IDENTITY.md`](../interop/A2A_SEMANTIC_IDENTITY.md), [`../interop/tests/test_a2a_semantic_identity.py`](../interop/tests/test_a2a_semantic_identity.py), [`../interop/tests/test_a2a_message_identity.py`](../interop/tests/test_a2a_message_identity.py) | Internal semantic consistency and protocol-shape validation are not remote-agent authentication, correct execution, artifact validity, verifier independence, idempotency storage, or acceptance/merge authority. |
| `P-INTEROP-004` | The protocol-neutral Work Unit binding rejects `NaN` and positive/negative infinity before canonical digesting or A2A/MCP envelope construction, so those Python-only numeric extensions cannot enter the strict-JSON interoperability path. | `implemented` | [`../interop/README.md`](../interop/README.md), [`../interop/bindings.py`](../interop/bindings.py), [`../interop/tests/test_strict_json_bindings.py`](../interop/tests/test_strict_json_bindings.py) | This is a portability/fail-closed serialization invariant, not evidence of remote trust, complete schema validity, execution correctness, or a universal JSON canonicalization standard. Finite supported values and existing wire versions are unchanged. |
| `P-INTEROP-005` | The MCP `tools/call` decoder fails closed when namespaced `org.idkmesh/work-contract` Work Unit ID/digest metadata disagrees with the canonical payload. Its JSON-RPC request `id` remains caller-selected transport correlation rather than Work Unit semantic identity, but the decoder requires the MCP 2026-07-28 request shape: a present, non-null string or integer ID, with JSON booleans and other JSON types rejected. | `implemented` | [`../interop/README.md`](../interop/README.md), [`../interop/bindings.py`](../interop/bindings.py), [`../interop/tests/test_mcp_work_unit_identity.py`](../interop/tests/test_mcp_work_unit_identity.py), [`../interop/sdk_conformance.py`](../interop/sdk_conformance.py) | This proves bounded in-process semantic-identity and request-shape invariants, not network authentication, remote execution correctness, complete MCP deployment conformance, request-ID uniqueness across outstanding requests, verifier independence, or acceptance/merge authority. |
| `P-R1-001` | The R1 research track studies when diversity/replication helps or hurts under controlled conditions and includes a real-corpus readiness gate. | `synthetic` / `implemented` | [`../docs/research/R1_SWARM_DIVERSITY_EXPERIMENT.md`](../docs/research/R1_SWARM_DIVERSITY_EXPERIMENT.md), [`../docs/research/R1_CORPUS_READINESS.md`](../docs/research/R1_CORPUS_READINESS.md) | Synthetic R1 outcomes are not real coding-agent performance. A readiness contract is not a real-corpus outcome. |
| `P-R1-002` | The current R1 low-diversity threshold robustness audit (schema v2) preserves the paired mean-effect analysis and interval-only robustness label, then adds exact two-sided sign-direction corroboration with Holm-Bonferroni correction across the declared family of marginal and change-from-previous-marginal questions. Its stricter familywise directional label requires agreement of the normal and bootstrap intervals, the same sign-test direction, and Holm-adjusted `p <= 0.05`. | `synthetic` / `implemented` | [`../randomness_lab/R1_THRESHOLD_ROBUSTNESS.md`](../randomness_lab/R1_THRESHOLD_ROBUSTNESS.md), [`../randomness_lab/r1_threshold_robustness.py`](../randomness_lab/r1_threshold_robustness.py), [`../tests/test_r1_threshold_robustness.py`](../tests/test_r1_threshold_robustness.py) | This strengthens the internal robustness accounting of one synthetic analysis; it does not establish a real scaling law or external validity. The sign test targets directional/sign balance rather than the paired mean magnitude, exact-zero effects are omitted from its sign count, and familywise interpretation still depends on valid sign-test assumptions for the deterministic seed effects. |
| `P-AVE-001` | The repository contains an experimental Adaptive Verification Ecology (AVE) policy proposal and deterministic simulator combining correlation-aware verifier selection, known-bad probe memory, risk-adaptive verification, ecological anti-monoculture pressure, entropy exploration, and review-capacity shadow-price backpressure. | `synthetic` / `implemented` | [`../docs/algorithms/ADAPTIVE_VERIFICATION_ECOLOGY.md`](../docs/algorithms/ADAPTIVE_VERIFICATION_ECOLOGY.md), [`../sim/adaptive_verification_ecology_sim.py`](../sim/adaptive_verification_ecology_sim.py), [`../experiments/AVE-0-adaptive-verification-ecology.md`](../experiments/AVE-0-adaptive-verification-ecology.md), [`../experiments/results/AVE-0-reference-sweep.json`](../experiments/results/AVE-0-reference-sweep.json), [issue #621](https://github.com/MSKazemi/idkmesh/issues/621) | AVE is future-work/control-policy research, not evidence for this paper's measured panel results and not a production routing capability. Its current result is synthetic and exposes a safety/cost trade-off that requires ablation and real held-out WorkUnits before stronger claims. |
| `P-E029-001` | E029 recorded 60 attempts from a pinned 0.5B open-weight producer on the frozen benchmark, with 0 accepted and 56/60 failing the diff protocol before repository content was consulted. | `observed-real-run` | [`../experiments/E029-first-real-model-attempts.md`](../experiments/E029-first-real-model-attempts.md), [`../docs/research/README.md`](../docs/research/README.md) | This is a bounded run on one pinned model/workload lineage, not a general statement about language models or production agent systems. Preserve the negative result. |
| `P-COLLAB-001` | Current collaboration-observables analyzer v0.4 retains the v0.2 rule that empty reviewer/owner HHI populations are undefined (`null`) rather than numeric zero. | `implemented` | [`../docs/research/COLLABORATION_OBSERVABLES_V0_1.md`](../docs/research/COLLABORATION_OBSERVABLES_V0_1.md), [`../scripts/collaboration_observables.py`](../scripts/collaboration_observables.py) | Historical v0.1 evidence remains immutable. Its empty-population `0.0` must not be reinterpreted as distributed participation; there were no eligible observations. |
| `P-COLLAB-002` | Analyzer v0.4 separates observed bounded proportions from prior-only Beta-Binomial posterior values and uses a deterministic exact equal-tail 95% Beta-posterior credible interval as the primary uncertainty interval while retaining the historical normal approximation only as explicit compatibility output. With zero trials, `observed_sample_size` is `0`, `empirical_rate` is `null`, and the posterior is explicitly labeled `prior_only_no_observations`. | `implemented` | [`../docs/research/COLLABORATION_OBSERVABLES_V0_1.md`](../docs/research/COLLABORATION_OBSERVABLES_V0_1.md), [`../scripts/metric_uncertainty.py`](../scripts/metric_uncertainty.py), [`../scripts/collaboration_observables.py`](../scripts/collaboration_observables.py), [`../tests/test_metric_uncertainty.py`](../tests/test_metric_uncertainty.py) | A mathematically defined posterior mean or credible interval with zero observations is prior-derived, not an observed recurrence/pass rate. The equal-tail interval is Bayesian and conditional on the declared Beta prior and exchangeability model; it is not a frequentist confidence interval and does not establish independence, causal validity, or stronger external evidence. |
| `P-REPRO-001` | The benchmark publication path can publish the committed human- and machine-readable benchmark snapshots as an immutable release bound to the exact protected-main SHA after deterministic drift/tests pass. | `implemented` | [`../benchmarks/README.md`](../benchmarks/README.md), [`../.github/workflows/benchmark-publication.yml`](../.github/workflows/benchmark-publication.yml) | Publication is a provenance/distribution mechanism, not new experimental evidence: it does not execute candidates, choose outcomes, strengthen scores, or establish generalization. |
| `P-REPRO-002` | The Phase 0 experiment harness rejects duplicate `configurations[].id` values after JSON Schema validation and before Work Unit I/O, because configuration IDs participate in emitted run identity and deterministic smoke-score keys. | `implemented` | [`../experiments/harness.py`](../experiments/harness.py), [`../tests/test_experiment_manifest_configuration_ids.py`](../tests/test_experiment_manifest_configuration_ids.py), [`../schemas/README.md`](../schemas/README.md) | This is a semantic reproducibility/identity invariant, not evidence that an experiment design is scientifically valid, that execution was correct, or that any measured outcome generalizes. ExperimentManifest v0.1 remains structurally unchanged; executable semantics are narrowed by harness v0.4. |
| `P-GATE-001` | The packaged `idkmesh gate-audit` v0.1 path fails closed on malformed or ambiguous verdict matrices (including duplicate JSON keys, non-finite JSON constants, boolean/non-finite quorum values, incomplete matrices, and inconsistent probe labeling), emits strict JSON, prevents destructive output-path collisions, and renders comparison-table saturation in `effective_votes` as a censored lower bound instead of a resolved point estimate while preserving the v0.1 estimand. | `implemented` | [`../idkmesh/gate_audit.py`](../idkmesh/gate_audit.py), [`../idkmesh/cli.py`](../idkmesh/cli.py), [`../docs/specifications/GATE_AUDIT_V0_1.md`](../docs/specifications/GATE_AUDIT_V0_1.md), [`../tests/test_gate_audit.py`](../tests/test_gate_audit.py) | This is input/output and measurement-interpretation hardening for a supplied verdict matrix. It does not prove verifier independence, estimate population/sampling uncertainty, validate the ground truth, establish external generalization, or grant acceptance/integration authority. A censored lower bound such as `>=199` is a comparison-table resolution statement, not a confidence or credible interval. |
| `P-GOV-001` | Project-operated or owner-controlled AI automation does not count as independent human/external review. | `implemented` | [`../PROJECT_RULES.md`](../PROJECT_RULES.md), [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | Do not use agent count, bot activity, or owner-controlled automated review as evidence of independent community validation. |
| `P-SCALE-001` | Internet-scale, multi-organization production behavior remains unresolved/staged rather than demonstrated by the repository evidence. | `unresolved` | [`../ROADMAP.md`](../ROADMAP.md), [`../docs/research/FIRST_RESEARCH_PROGRAM.md`](../docs/research/FIRST_RESEARCH_PROGRAM.md) | Present this as a limitation/future-work boundary, not as achieved scale. |
| `P-PAPER-001` | A canonical editable manuscript source ([`main.tex`](main.tex), "Reviewer Count Is Not Evidence Count") is versioned in this repository at `paper/main.tex`, revised against a prior adversarial review whose findings were independently re-verified against the current text and underlying artifacts. | `implemented` | [`main.tex`](main.tex), [`README.md`](README.md), [`review_reviewer-count-is-not-evidence-count_2026-09-09.md`](review_reviewer-count-is-not-evidence-count_2026-09-09.md), [issue #478](https://github.com/MSKazemi/idkmesh/issues/478) | This resolves the manuscript-source gap issue #478 tracked; it does not by itself constitute independent venue peer review, which the manuscript's own AI/tool provenance paragraph states has not occurred. |

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
  revisions, skip/conformance semantics, strict-JSON serialization/digest
  boundaries, semantic-identity checks, and transport-level identifier shape.
  Keep protocol-owned correlation IDs such as A2A `messageId` and MCP JSON-RPC
  `id` distinct from IDKMesh Work Unit identity unless the upstream protocol and
  repository contract explicitly say otherwise. Transport ownership does not
  remove the need to validate the upstream protocol's identifier type/shape.
- **Experiment manifest/harness identity change:** review `P-REPRO-*` and record
  whether run/configuration identifiers can become ambiguous before execution.
  Treat identity hardening as reproducibility infrastructure, not outcome evidence.
- **Gate-audit/verification metric change:** review `P-GATE-*`; distinguish a raw
  estimand from presentation bounds, comparison-table censoring from inferential
  uncertainty, and parser/output hardening from evidence that the verifier panel is
  actually independent or representative.
- **Experiment rerun/new result:** add or revise a claim only after preserving the
  old artifact and classifying the new evidence. Negative or null results remain
  part of the record.
- **Statistical robustness/multiplicity change:** record which estimand each method
  targets, which family is corrected, which legacy fields remain compatible, and
  whether the evidence class is unchanged. A stricter synthetic uncertainty layer
  is not by itself real-task evidence.
- **Metric contract change:** distinguish historical artifact semantics from the
  current analyzer contract, including undefined empty-population statistics,
  prior-only Bayesian values with zero empirical observations, and whether a
  posterior interval is an exact model-conditional credible interval or a retained
  compatibility approximation.
- **Publication/release change:** distinguish stronger provenance/distribution
  guarantees from stronger scientific evidence; publishing an artifact does not
  improve its underlying evidence class.
- **Community/agent automation change:** review independence/provenance language;
  automation volume is not independent validation.
- **Open PR proposing a stronger method:** do not write its proposed semantics as
  current paper evidence until it is merged to `main` with its required checks.
- **Roadmap completion:** change `unresolved` only when the required evidence has
  actually landed, not when an issue or PR merely proposes it.

## Known gap

This map can be maintained and link-checked now, but it cannot be reconciled
section-by-section against manuscript prose until issue #478 supplies the
canonical manuscript source or an explicit external synchronization procedure.
