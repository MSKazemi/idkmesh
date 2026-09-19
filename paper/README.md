# IDKMesh paper stewardship

This directory is the public synchronization point between IDKMesh research claims
and the repository evidence that can support them.

## Current manuscript status

The canonical manuscript source is [`main.tex`](main.tex) ("Reviewer Count Is
Not Evidence Count: Measured Error Dependence in an Executable Verification
Panel"), built with [`Makefile`](Makefile) against [`refs.bib`](refs.bib) and
the figures [`make_figures.py`](make_figures.py) regenerates from committed
experiment artifacts under `experiments/results/`. The built PDF is committed
alongside it for reader convenience; LaTeX build byproducts (`.aux`/`.bbl`/
`.blg`/`.log`/`.out`) and the regenerated `figures/` directory are derived, not
source, and are gitignored.

This addresses issue [#478](https://github.com/MSKazemi/idkmesh/issues/478)'s
request for a discoverable canonical manuscript source. The manuscript was
revised against a prior adversarial review,
[`review_reviewer-count-is-not-evidence-count_2026-09-09.md`](review_reviewer-count-is-not-evidence-count_2026-09-09.md)
(Weak Reject, 14 findings), which is kept alongside the source as a
transparency record: every Critical/Major finding in it (the `n_eff` clamp
misrepresented as a measurement, missing confidence intervals, the missing
best-member comparison, the unconditional heuristic claim, the uncited
concurrent work, and the two-factor correlation/blind-spot confound) was
independently re-verified against the current text and the underlying
artifacts before this manuscript status was updated — not merely re-read.
The manuscript's own "AI/tool provenance" paragraph discloses assistance and
states plainly that it has not undergone venue peer review.

Reviewers of *this repository* (as opposed to the manuscript) should still
verify the manuscript matches current evidence before relying on it: research
code and experiment records change faster than this file does. If a change to
`sim/`, `experiments/`, or `docs/research/` affects a claim in `main.tex`,
update the manuscript and [`CLAIM_EVIDENCE_MAP.md`](CLAIM_EVIDENCE_MAP.md) in
the same bounded change, per the rules below.

## What belongs here

- [`CLAIM_EVIDENCE_MAP.md`](CLAIM_EVIDENCE_MAP.md) records paper-relevant claims,
  their evidence class, repository sources, and the limitation that must travel
  with each claim.
- [`main.tex`](main.tex) is that canonical manuscript, at this stable path. If a
  second manuscript is ever added, give it its own named path rather than
  overloading `main.tex`; if the canonical source ever moves external to this
  repository, this file must document the synchronization procedure before that
  happens, not after.
- Reproduction instructions for figures/tables should name the exact command,
  input artifact, output artifact, and source revision used. Do not add a command
  merely because it appears plausible from nearby code.

Publisher-generated binaries are optional. Editable source and reproducible
provenance are the important artifacts.

## Evidence classes

Use these labels consistently in the manuscript and claim map:

| Class | Meaning |
| --- | --- |
| `implemented` | The repository contains an executable or schema-level contract. This alone is not empirical effectiveness evidence. |
| `synthetic` | The result comes from a simulation, generated environment, or controlled synthetic benchmark. Do not present it as field performance. |
| `observed-real-run` | A pinned real execution produced the recorded observation. State the exact workload/model/revision and do not generalize beyond it. |
| `accepted-conclusion` | A bounded conclusion is supported by the repository's declared evidence procedure. It is still scoped to that procedure and data. |
| `unresolved` | The repository does not yet contain evidence sufficient for the stronger statement. Present it as a question, hypothesis, limitation, or future work. |

A claim can cite more than one class, for example an `implemented` mechanism with
`synthetic` evaluation. Do not collapse those into a stronger evidence category.

## Rules for humans and autonomous agents

When a change can affect a paper claim:

1. Start from current `main` and inspect open issues/PRs to avoid parallel claim
   rewrites.
2. Locate the claim in [`CLAIM_EVIDENCE_MAP.md`](CLAIM_EVIDENCE_MAP.md). If it is
   material and absent, add it with the narrowest defensible wording.
3. Separate implementation existence from experiment outcome, and separate
   synthetic evidence from real executions.
4. Preserve negative, null, and counterexample results. A new implementation or
   favorable run does not erase an earlier falsification or limitation.
5. Pin quantitative statements to the exact committed evidence/revision that
   produced them. A current code path is not automatically the producer of a
   historical result.
6. Treat protocol hardening as a scoped implementation claim. Identity checks,
   strict serialization, SDK conformance, and immutable publication strengthen
   specific boundaries; they do not by themselves establish remote trust,
   execution correctness, scientific validity, or independent review. Keep
   transport/correlation identifiers separate from Work Unit semantic identity
   when the upstream protocol owns those identifiers, while still validating the
   protocol-mandated identifier shape (for example A2A's non-empty string
   `messageId` and MCP's non-null string-or-integer JSON-RPC request `id`).
7. Treat experiment-manifest and harness identity checks as reproducibility
   invariants. Rejecting ambiguous configuration IDs protects run labeling and
   deterministic reproduction, but it does not turn a synthetic experiment into
   observed evidence or establish that an experimental conclusion is correct.
8. Treat statistical robustness layers as bounded evidence transformations, not as
   automatic evidence-class upgrades. For example, the R1 threshold audit's
   bootstrap/sign/Holm familywise layer can make a synthetic directional claim more
   conservative without turning deterministic simulator seeds into a real task
   population or making the sign estimand identical to the paired mean estimand.
9. Treat collaboration-observables posterior intervals as model-conditional evidence. An exact equal-tail Beta-posterior credible interval is preferable to a clipped normal approximation for that declared model, but it does not convert prior-only values into observations, prove independence/exchangeability, or create causal or frequentist guarantees.
10. Treat `gate-audit` parser/output hardening and censored effective-vote rendering
   as measurement-integrity infrastructure. A strict input contract, valid JSON,
   and an explicit lower-bound display prevent avoidable misinterpretation; they do
   not supply sampling uncertainty, prove verifier independence, or turn a supplied
   verdict matrix into broader scientific evidence.
11. Update the canonical manuscript in the same bounded PR **only after** its
    source is available. Otherwise record the paper-impact note here or on #478.
12. Run the repository Markdown/link gate and any experiment-specific
    reproduction checks that actually apply. Report only commands that really ran
    and their actual result.
13. Disclose AI/tool assistance. Owner-controlled automation is not independent
    human or external scientific review.

## Paper review checklist

A paper-facing review should explicitly check:

- architecture names and interfaces against [`../ARCHITECTURE.md`](../ARCHITECTURE.md);
- implemented versus planned capability against [`../ROADMAP.md`](../ROADMAP.md);
- protocol mappings, semantic-identity rules, transport/correlation identity and
  identifier shape, strict-JSON/digest boundaries, and optional SDK conformance
  against [`../interop/README.md`](../interop/README.md);
- experiment status, manifest/run identity, and evidence boundaries through
  [`../docs/research/README.md`](../docs/research/README.md),
  [`../experiments/README.md`](../experiments/README.md), and
  [`../schemas/README.md`](../schemas/README.md);
- gate-audit claims against [`../docs/specifications/GATE_AUDIT_V0_1.md`](../docs/specifications/GATE_AUDIT_V0_1.md),
  including the declared evidence class, strict-JSON/input contract, the distinction
  between a resolved effective-vote estimate and a comparison-table lower bound,
  and the fact that a point estimate is not a sampling-uncertainty interval;
- collaboration-observables uncertainty claims against
  [`../docs/research/COLLABORATION_OBSERVABLES_V0_1.md`](../docs/research/COLLABORATION_OBSERVABLES_V0_1.md), including empirical-vs-prior-only status, analyzer/method version, exact credible-interval semantics, retained approximation fields, and the exchangeability/independence limitation;
- R1 threshold language, when used, against
  [`../randomness_lab/R1_THRESHOLD_ROBUSTNESS.md`](../randomness_lab/R1_THRESHOLD_ROBUSTNESS.md),
  including the distinction between the paired mean intervals, sign-direction
  corroboration, multiplicity correction, and real-world external validity;
- negative/inconclusive evidence relevant to the narrative;
- real-run provenance, model/workload identity, and exact source revision for
  quantitative claims;
- limitations and threats to validity, including missing independent review and
  missing production-scale/multi-organization evidence where applicable;
- reproducibility paths for every repository-generated table or figure.

The Markdown links in this directory are intentionally repository-relative so the
existing link-integrity gate can detect broken evidence references.
