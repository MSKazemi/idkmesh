# Replaying the Node Evidence: One Digest Reproduces, Four Cannot

**Date:** 2026-08-30
**Evidence level:** direct reproduction on a second machine; no acceptance or integration authority.
**Artifacts:** `results/verification/node-e2e-replay-2026-08-30/`

## What was run

`tools/node_verifier_e2e_current.py` — one of the five executables that
[nothing in the repository demonstrated had ever run](2026-08-30-executables-nothing-ever-ran.md)
— was executed against the preserved canonical-node worker candidate.

The candidate is not in `main`. It was fetched from `refs/pull/91/head`, which still resolves to
`520ad2c9aa5825476de4957da4702d6823f4edb3`, and checked out into a detached work tree. The
harness generated a real patch with the containerized worker and then verified it with the
independent evaluator plan. Exit code 0.

```text
worker  local/idkmesh-node          status: succeeded
plan    verification/real-node-520ad2c-plan   backend: unified_diff
result  status: passed   recommendation: accept_candidate
        independent_from_worker: true
        human_integration_decision_required: true
```

The harness preserves the human gate in its own output. Worker success is not acceptance, and
this replay is not a review.

## Preservation, checked rather than assumed

Pull request #159 was closed during branch convergence with a comment stating the candidate was
preserved by tag and by pull-request ref. That claim was verified, not taken on trust:

| Claim | Result |
| --- | --- |
| `archive/integration/canonical-node-current-main-refresh` exists on origin | resolves to `61cafa86f7e0e86343d73182862e3cead1080ab9` |
| `refs/pull/159/head` fetchable | `61cafa86…` |
| `refs/pull/91/head` fetchable | `520ad2c9…` |
| `node/` tree intact at the candidate | 10 files present |

The pinned worker image was also re-pulled today. Its repository digest is
`python@sha256:d09d15e60962ca365d1cd544a48773bac9d33f2fb1b00f2aa0deec78ade7dc31`, identical to
the digest recorded in the #159 controlled-acceptance evidence two days earlier.

## The finding: four of five recorded digests cannot reproduce, by construction

Comparing this replay against the digests recorded on 2026-08-28 in
`docs/conversations/2026-08-28-real-node-verifier-e2e.md`:

| Recorded anchor | 2026-08-28 | 2026-08-30 replay | Reproduces |
| --- | --- | --- | --- |
| WorkUnit digest | `40993e89…` | `40993e89…` | **yes** |
| **Candidate patch digest** | `8383a0dd…` | `8383a0dd…` | **yes** |
| ResultManifest id | `attempt-1-5bead4f97b` | `attempt-1-3c3a50fd34` | no |
| ResultManifest digest | `b4542695…` | `c7c85c4c…` | no |
| VerificationResult id | `…5bead4f97b/patch-verification` | `…3c3a50fd34/patch-verification` | no |
| VerificationResult digest | `f52686e8…` | `e79ff7ce…` | no |
| Evaluator plan digest | `893e59d8…` | `a0e89da5…` | no |

The cause of the ResultManifest divergence is not environmental. It is a single line in the
worker:

```python
# node/src/idkmesh_node/runner.py:575
"id": f"{work.id}/attempt-1-{uuid.uuid4().hex[:10]}",
```

The attempt identifier is random per run. The manifest digest covers the identifier, so it
inherits the randomness; the VerificationResult identifier embeds the manifest identifier, so it
inherits it too. A second replay on this same machine minutes later produced a third distinct
identifier — `attempt-1-7c642cfd4d` — while the candidate patch digest stayed byte-identical.
These four values can only ever attest "this exact run happened". They can never attest "this
candidate produces this result".

**Exactly one recorded digest identifies the actual work product, and it reproduced exactly**:
`sha256:8383a0dd5217e9472e5f55eb658248620e539394cb96012dc61c24a3cc33f6cf`, matching three
committed conversation records and a pull-request comment, on a different machine two days later,
twice.

## What is not explained

The evaluator plan digest was stable across both replays on this machine (`a0e89da5…` twice) yet
differs from the 2026-08-28 record. It is therefore **not** a victim of the attempt-identifier
randomness, and the divergence has a real cause that this replay did not isolate. Two candidates,
neither confirmed: an evaluator-contract change on `main` since 2026-08-28, or a different
harness wrapper having produced the original record. Stating either as the answer would be a
guess, so neither is stated.

## Why this matters for the review that is blocked

Issue #138 asks for an independent human witness to the canonical-node evidence. A reviewer who
attempts the obvious check — replay the harness, compare against the recorded digests — will find
that five of seven values disagree, and could reasonably conclude the evidence is unsound.

It is not. The disagreement is the expected behaviour of a randomly seeded identifier plus one
unexplained plan-digest difference. The substantive anchor matches perfectly. This report exists
so that the reviewer knows which digest to check and which to ignore before drawing a conclusion.

## A side effect worth naming

Running these tools removes three entries from the unexercised-executable list, which is the
intended route off that list: run the tool and record the evidence, rather than delete the tool.
It also exposed a defect in the check that produced the list — the report naming the five
executables cleared all five, because `docs/` counted as recorded output. `docs/findings/` is now
excluded from that corpus, and the two executables that genuinely have never run stay flagged.

## Limitations

- This is a replay of an existing candidate, not a review of it. It confirms the artifact
  reproduces; it says nothing about whether the node should be integrated.
- The replay ran on one machine, on Linux, with Docker. Cross-platform reproduction of the patch
  digest is untested.
- The plan-digest divergence is unresolved, and no attempt was made to reconstruct the
  2026-08-28 evaluator contract.
- Nothing here reduces the requirement in #138 for a genuinely separate human witness.

## Decision

No integration, no acceptance, no change to the node candidate. The recommended repository change
is narrow and not made here: a ResultManifest identifier derived from the work product rather than
from `uuid.uuid4()` would make the manifest and verification digests reproducible, and would let a
reviewer check all of the anchors instead of one of them.
