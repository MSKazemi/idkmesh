# IDKMesh paper stewardship

This directory is the public synchronization point between IDKMesh research claims
and the repository evidence that can support them.

## Current manuscript status

As of the stewardship audit against `main@1698e1fa535b940c20bf35f4ab0e12916a46b690`
on 2026-09-17, this repository does **not** contain a discoverable canonical
editable manuscript source (`.tex`, Markdown manuscript, or equivalent) or a
committed paper PDF. Issue [#478](https://github.com/MSKazemi/idkmesh/issues/478)
tracks that missing source-of-truth.

That absence is a maintenance limitation, not permission to reconstruct a paper
from README or architecture prose. Until the actual manuscript is imported or an
external canonical source is documented, repository stewards should improve the
evidence map and paper-facing constraints here, but should not claim that the
paper text itself was reviewed or updated.

## What belongs here

- [`CLAIM_EVIDENCE_MAP.md`](CLAIM_EVIDENCE_MAP.md) records paper-relevant claims,
  their evidence class, repository sources, and the limitation that must travel
  with each claim.
- A future canonical manuscript should live under a stable path such as
  `paper/manuscript/`, **or** this file should point to the intentionally external
  canonical source and describe how a repository revision is synchronized to it.
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
6. Update the canonical manuscript in the same bounded PR **only after** its
   source is available. Otherwise record the paper-impact note here or on #478.
7. Run the repository Markdown/link gate and any experiment-specific
   reproduction checks that actually apply. Report only commands that really ran
   and their actual result.
8. Disclose AI/tool assistance. Owner-controlled automation is not independent
   human or external scientific review.

## Paper review checklist

A paper-facing review should explicitly check:

- architecture names and interfaces against [`../ARCHITECTURE.md`](../ARCHITECTURE.md);
- implemented versus planned capability against [`../ROADMAP.md`](../ROADMAP.md);
- experiment status and evidence boundaries through
  [`../docs/research/README.md`](../docs/research/README.md) and
  [`../experiments/README.md`](../experiments/README.md);
- negative/inconclusive evidence relevant to the narrative;
- real-run provenance, model/workload identity, and exact source revision for
  quantitative claims;
- limitations and threats to validity, including missing independent review and
  missing production-scale/multi-organization evidence where applicable;
- reproducibility paths for every repository-generated table or figure.

The Markdown links in this directory are intentionally repository-relative so the
existing link-integrity gate can detect broken evidence references.
