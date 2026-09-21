# Conversation record: IDKMesh readiness assessment

**Date:** 2026-09-21  
**Base revision inspected:** `2df1d454ff454e266c1cd4f46caa1fec0a36d232`

## Project-owner question

The project owner asked for an assessment of an external Claude Code summary of
IDKMesh readiness. The supplied summary characterized IDKMesh as a research
foundation rather than a production tool, identified `idkmesh gate-audit` as
the usable product surface, said the Verified Swarm Runner was not ready, and
stated that no live workers or live verifiers had been executed.

## Repository checks

The assessment was checked against current `main`, especially:

- `README.md`
- `ROADMAP.md`
- `EVOLUTION.md`
- `pyproject.toml`
- `idkmesh/cli.py`
- `interop/README.md`
- `experiments/E015-verification-phase-diagram.md`
- `experiments/E016-live-verifier-correlation.md`
- `experiments/E017-item-difficulty-and-quorum.md`
- `experiments/E029-first-real-model-attempts.md`
- issue 16, the local Git-native Verified Swarm Runner v0.1 gate
- issue 374, the reproducible Verified Swarm Runner release gate

## Findings

### 1. The production-readiness conclusion is directionally correct

Current `README.md`, `ROADMAP.md`, and `EVOLUTION.md` all distinguish the
implemented research/coordination foundation from a finished reference runner.
The roadmap still requires a coherent local product loop, heterogeneous worker
interchangeability, a reproducible release, and later small multi-machine
experiments.

IDKMesh should therefore not currently be presented as a production-ready
multi-agent coordination platform.

### 2. `gate-audit` is the clearest usable product surface on current main

`pyproject.toml` exposes the `idkmesh` console script and labels the package
Alpha. `idkmesh/cli.py` explicitly says there is one subcommand for now:
`gate-audit`.

That makes the external assessment substantially correct that `gate-audit` is
the clearest installable, user-facing product surface available today. It is a
diagnostic tool: it consumes collected verdicts and does not itself execute a
review gate or grant acceptance authority.

### 3. The statement "no live workers, no live verifiers executed" is outdated

Current repository evidence contradicts that statement:

- E016 ran 20 live open-weight LLM verifiers across 72 candidates. It was a
  negative result because no verifier discriminated above chance, but it was
  live verifier execution.
- E017 ran 25 programmatic partial-test verifiers over the same corpus and
  measured observed missed-defect correlations. This is real verification
  behavior, although the verifier diversity structure was constructed.
- E029 ran 60 real sandboxed language-model coding attempts against frozen
  WorkUnits. All failed before independent verification, mostly on strict
  unified-diff protocol compliance, but they were real worker/model attempts.
- issue 16 records experimental real-node multi-attempt orchestration,
  independent verification, non-selecting evidence reporting, and exact replay
  evidence. The issue remains open because the coherent newcomer-facing v0.1
  path and its remaining evidence/review gates are incomplete.

The correct distinction is therefore not "only schemas/simulations versus no
real execution." The distinction is "real experimental execution exists, but a
coherent, reviewed, packaged production runner is not yet complete."

### 4. E015-E017 should not be grouped together as uniformly "real experiments"

E015 is a large synthetic/simulation study. E016 is a live LLM-verifier
experiment with a negative result. E017 is observed programmatic-verifier
evidence. The repository itself is careful about these evidence classes, so
readiness summaries should preserve that distinction.

### 5. A more precise readiness label

A useful current description is:

> **IDKMesh is an advanced research prototype with a usable review-panel
> diagnostic product, substantial executable coordination/verification
> infrastructure, and real experimental worker/verifier evidence. The
> Git-native Verified Swarm Runner is not yet a coherent production release.**

That description is stronger than "only a research foundation" but still avoids
claiming production readiness.

## Practical readiness by surface

| Surface | Current assessment |
| --- | --- |
| `idkmesh gate-audit` | Usable now as an Alpha diagnostic on already-collected verdicts |
| Contract demo, schemas, validators, simulations | Usable now for research/development |
| WorkUnit, ResultManifest, EvaluatorPlan, VerificationResult machinery | Substantial executable foundation |
| A2A/MCP interoperability | Tested semantic/conformance layer, not a production remote-agent network |
| Real model/verifier experiments | Present, including negative results |
| Local Verified Swarm Runner | Experimental/incomplete product path |
| Reproducible newcomer release | Not yet shipped; issue 374 remains open |
| Multi-machine / Internet-scale production mesh | Not ready and not claimed |

## Recommended project focus

The highest-leverage next milestone is convergence, not another architectural
layer:

1. finish the remaining acceptance gates in issue 16;
2. make the complete local path installable and understandable by a newcomer;
3. satisfy issue 374 with one reproducible release that can run, verify, inspect,
   and replay a bounded example;
4. only then expand heterogeneous adapters and multi-machine experiments.

This would turn the repository's existing research and experimental evidence
into the product surface that external evaluators are currently looking for.

## Community impact

A precise readiness statement helps newcomers distinguish what they can use
today from what they can help build. It also prevents two opposite forms of
confusion: overselling IDKMesh as production-ready, or understating the real
execution/evidence already present in the repository.

## AI/tool provenance

Assessment produced with ChatGPT (GPT-5.6 Sol) using direct inspection of the
current GitHub repository through the connected GitHub tooling. No hidden chain
of thought is preserved. The conclusions above are a public-safe summary of the
repository evidence inspected in this conversation.
