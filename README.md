# IDKMesh

> **I don't know. You don't know. Together, the mesh can discover, build, verify, and learn.**

IDKMesh is an open-source research and engineering project exploring how humans, AI agents, software tools, and heterogeneous compute can coordinate on uncertain goals and turn proposals into **verified useful work**.

The project is intentionally ambitious, but the repository is not claiming a finished planetary-scale system. Today it is a **GitHub-native research laboratory with an executable coordination/evidence foundation** and a reference-product target: the Git-native Verified Swarm Runner.

## See it work in sixty seconds

```bash
git clone https://github.com/MSKazemi/idkmesh && cd idkmesh
python -m pip install -r requirements-phase0.txt
python scripts/demo.py
```

The demo walks one bounded task through the acceptance contract using the real
schemas in [`schemas/`](schemas/) and the real fixtures in [`examples/`](examples/).
Four objects are rejected — one before any work starts, and three that each report
success anyway:

| The object | Why it is rejected |
| --- | --- |
| A task with no security contract | the bound is checked before dispatch, not after the work comes back |
| A worker that accepts its own output | worker completion is not acceptance |
| A "verifier" that is the worker under another name | correlated verification adds volume, not evidence |
| A verification whose provenance does not bind to what ran | evidence must reference the exact artifact it checked |

That is the part of IDKMesh that exists and runs today. If you disagree with
where those lines are drawn, that disagreement is the most useful thing you can
bring to this project — argue it in
[Discussions](https://github.com/MSKazemi/idkmesh/discussions/categories/q-a).

Questions and "why is it done this way" belong in
[Discussions](https://github.com/MSKazemi/idkmesh/discussions); the issue tracker
is for defects and bounded pieces of work.

## The central question

> **Can a large open community of humans and AI agents discover goals, decompose work, execute bounded tasks, verify results independently, and maintain complex systems better than isolated developers or agents can?**

IDKMesh treats that as an empirical question. More agents, more activity, more commits, or more votes are not automatically better.

## Current status

**Executable research foundation; reference runner still incomplete.**

What is already present on `main`:

- versioned WorkUnit contracts, with `work-unit-v0.2.schema.json` as the current semantic task contract;
- ResultManifest, EvaluatorPlan, and VerificationResult contracts that separate worker claims, verifier evidence, and integration authority;
- cross-object provenance and integrity validation;
- a five-arm WorkUnit decomposition benchmark contract and strict synthetic-vs-observed evidence boundary;
- protocol-neutral worker-adapter code plus A2A/MCP bindings and SDK/conformance helpers under [`interop/`](interop/);
- simulation and experiment code under [`sim/`](sim/) and [`experiments/`](experiments/);
- zero-project-spend compute admission and routing experiments;
- IDKGraph repository modeling, observability, link-integrity, and warning/review machinery;
- GitHub-native ACE community-growth experiments and repository-evolution control tooling;
- a first installable product surface: `pip install .` provides the `idkmesh`
  CLI, whose `gate-audit` command packages the measured verifier-panel results
  (E015/E016/E017) as a review-gate diagnostic;
- protected `main` with the stable PR gate required on Python 3.11 and 3.13.

What is **not** yet a finished capability:

- there is no claim that IDKMesh can safely coordinate thousands or millions of real machines;
- the reference Verified Swarm Runner is not yet a polished install-and-run product with multiple production worker adapters;
- canonical real-node integration remains subject to its independent-review/evidence gates rather than being inferred from historical prototypes;
- A2A/MCP support is an interoperability layer, not a claim that every external agent framework is production-integrated;
- autonomous repository/community actuation remains policy- and authority-gated;
- benchmark infrastructure is not scientific proof until controlled observed runs exist.

This distinction is important: **implemented infrastructure is evidence of capability to run experiments, not evidence that the research hypotheses are true.**

## Try it in five minutes: audit a review gate

The first installable tool cut from this research is `idkmesh gate-audit`. It
measures what a panel of reviewers/verifiers is actually worth: effective
independent votes (not nominal head-count), error-correlation structure, and
the breach rate of seeded known-bad probe candidates.

```bash
git clone https://github.com/MSKazemi/idkmesh
cd idkmesh
pip install .
idkmesh gate-audit examples/gate-audit/panel-votes.example.json --pretty
```

The bundled example reports that a five-verifier panel is worth about **1.69
effective independent votes**, and that the popular `N/(1+(N-1)ρ)` heuristic
overstates it — the phenomenon measured on a real 25-verifier panel in
[E017](experiments/E017-item-difficulty-and-quorum.md) and falsified as a
sizing rule in [E015](experiments/E015-verification-phase-diagram.md). The
contract is specified in
[`docs/specifications/GATE_AUDIT_V0_1.md`](docs/specifications/GATE_AUDIT_V0_1.md).
The audit is diagnostic only: it consumes verdicts you collected and grants no
acceptance or merge authority.

## Start here

You do not need to understand the entire repository before contributing.

1. Read this README.
2. Read [`CONTRIBUTING.md`](CONTRIBUTING.md).
3. Choose a contribution path in [`COMMUNITY.md`](COMMUNITY.md).
4. Browse the live [`good first issue`](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22good+first+issue%22) and [`help wanted`](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22help+wanted%22) views.
5. Before starting, check assignees, recent comments, and linked pull requests, then state the bounded change you intend to make.

Two live examples at the time of this audit:

- [#167 — independently review IDKGraph orphan cohort 1](https://github.com/MSKazemi/idkmesh/issues/167), a bounded newcomer-friendly evidence/review task;
- [#151 — independently audit the mathematical evolution control plane](https://github.com/MSKazemi/idkmesh/issues/151), a higher-skill security/control-systems review task.

The [ACE Bootstrap Cohort Observatory](https://github.com/MSKazemi/idkmesh/issues/109) is the live evidence source for the original growth-seed cohort. It intentionally distinguishes activity from verified external participation.

If something is confusing, stale, contradictory, or difficult to discover, reporting or fixing that is useful project work.

## IDKMesh in 60 seconds

- **IDK** means *I Don't Know*: uncertainty, disagreement, assumptions, and competing hypotheses are first-class states.
- **Mesh** means a network of people, agents, tools, evidence, tasks, and compute rather than one monolithic agent.
- Workers should receive bounded **Work Units**, not unlimited project authority.
- Worker completion is not acceptance; verifier recommendation is not merge authority.
- Verification, provenance, reproducibility, and security must scale with generation volume.
- Diversity matters only when it adds sufficiently independent useful evidence.
- Git/GitHub are the current collaboration and canonical-history substrate.
- A2A and MCP are integration surfaces; IDKMesh should not invent commodity transport protocols unnecessarily.
- The public repository is also project memory: durable decisions, findings, evidence, and important collaboration history should remain inspectable.

## The reference product

The first reference application is a **Git-native Verified Swarm Runner**.

The target lifecycle is:

```text
bounded repository task
        |
        v
   WorkUnit v0.2
        |
        v
 replaceable worker adapters
        |
        v
 candidate artifacts + ResultManifest
        |
        v
 verifier-owned EvaluatorPlan
        |
        v
 independent VerificationResult
        |
        v
 non-selecting evidence/reporting
        |
        v
 explicit human/governance integration decision
```

The key authority rule is:

```text
worker success != acceptance
verification recommendation != merge authority
CI success != independent human review
```

The current codebase already implements substantial pieces of this trust path, but the end-to-end newcomer product is still being converged and experimentally validated. See [`EVOLUTION.md`](EVOLUTION.md), [`ROADMAP.md`](ROADMAP.md), and the open project issues for the live gates.

## Run the repository checks

For the repository's Python research/control code:

```bash
python -m pip install --disable-pip-version-check pytest
python -m pip install --disable-pip-version-check -r requirements-phase0.txt
PYTHONPATH=. python -m pytest -q
```

Validate the core Phase 0 contracts directly with:

```bash
python experiments/harness.py validate
```

Pull requests to protected `main` run the stable PR gate on Python 3.11 and 3.13 plus deterministic Markdown-link integrity. Individual subsystems also have narrower workflows.

## Core architecture

IDKMesh is best understood as one layered system:

```text
human constitution / governance
           |
           v
 goals + questions + evidence
           |
           v
       Work Units
           |
           v
 capability/resource matching
           |
           v
 isolated humans / agents / tools / compute
           |
           v
 candidate artifacts + provenance
           |
           v
 independent verification / criticism
           |
           v
 explicit integration decision
           |
           v
 canonical state + outcome evidence
           |
           +------> next goals / policy learning
```

The canonical lifecycle vocabulary—event, action, candidate, iteration, generation, learning, and improvement—is defined in [`ITERATION_MODEL.md`](ITERATION_MODEL.md).

For implementation-level boundaries, see [`ARCHITECTURE.md`](ARCHITECTURE.md) and the curated [`docs/architecture/`](docs/architecture/README.md) index.

## What IDKMesh builds vs reuses

IDKMesh should spend its complexity budget on the parts that express its research thesis:

- goals, uncertainty, and evidence;
- bounded Work Units and authority;
- decomposition and dependency structure;
- capability/resource matching;
- independent verification and evidence aggregation;
- provenance and reproducibility;
- experiment/benchmark machinery;
- community and governance feedback loops;
- measured self-improvement under external authority constraints.

Commodity infrastructure should normally be integrated rather than reinvented. Current examples include Git/GitHub, OCI-style isolation patterns, A2A, MCP, and established provenance/supply-chain approaches.

## Research discipline

The repository distinguishes at least four states:

1. **implemented mechanism** — code/schema/workflow exists;
2. **synthetic validation** — deterministic fixtures/simulations test mechanics;
3. **observed evidence** — controlled runs measured real behavior;
4. **accepted conclusion** — evidence is strong enough for the scoped decision.

Do not collapse these states. A simulator can validate an algorithm's implementation without proving that the algorithm improves real collaboration.

One flagship research family compares, under matched budgets:

```text
one strong worker
vs one small worker
vs replicated workers
vs heterogeneous workers
vs specialized roles
vs task/evidence DAG teams
```

Important outcomes include correctness, hidden-test success, regressions, error correlation, reviewer time, compute/resource use, latency, integration conflict, provenance quality, and verified useful work per unit of scarce attention/cost.

See [`RESEARCH_QUESTIONS.md`](RESEARCH_QUESTIONS.md), [`docs/research/`](docs/research/README.md), and [`experiments/`](experiments/).

## Project principles

**Community first.** Contributor experience, review capacity, and leadership scalability are engineering constraints.

**Proposal is not proof.** Human or AI confidence does not replace evidence.

**Popularity is not correctness.** Votes, stars, reputation, or correlated model agreement cannot override failed checks.

**More agents are not automatically better.** Diversity, independence, decomposition quality, and verification capacity matter more than raw count.

**Uncertainty is data.** Competing goals and unresolved hypotheses should remain explicit when evidence is insufficient.

**Generation must not outrun verification.** Output volume is harmful if the project cannot review, reproduce, and maintain it.

**Integrate before reinventing.** Reuse open standards for commodity capabilities and keep IDKMesh-specific semantics at the coordination/evidence layer.

**Scale must be earned.** Simulated or small-scale results must not be advertised as Internet-scale guarantees.

**Cryptographic provenance comes before blockchain.** Add heavier trust infrastructure only when a demonstrated threat model requires it.

**Canonical authority remains external to generators and verifiers.** Protected integration is a separate decision boundary.

## Repository guide

### New contributor

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — contribution workflow and checks.
- [`COMMUNITY.md`](COMMUNITY.md) — participation paths and contributor ladder.
- [`SUPPORT.md`](SUPPORT.md) — how to ask for help.
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — community expectations.
- [`SECURITY.md`](SECURITY.md) — vulnerability reporting.

### Understand the system

- [`docs/WHAT_IS_IDKMESH.md`](docs/WHAT_IS_IDKMESH.md) — framework, research, community, reference application, and self-hosting layers.
- [`ITERATION_MODEL.md`](ITERATION_MODEL.md) — canonical evolution vocabulary and authority flow.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — current architecture map.
- [`EVOLUTION.md`](EVOLUTION.md) — strategy, implemented foundation, and next gates.
- [`ROADMAP.md`](ROADMAP.md) — evidence-gated progression from the current state.
- [`docs/README.md`](docs/README.md) — curated documentation navigation.

### Contracts and interoperability

- [`schemas/README.md`](schemas/README.md) — current machine-readable contracts and versioning rules.
- [`docs/specifications/`](docs/specifications/README.md) — protocol/specification index.
- [`interop/`](interop/) — protocol-neutral adapter boundary, A2A/MCP mappings, identity binding, and conformance helpers.
- [`IDKIPS.md`](IDKIPS.md) — major improvement-proposal process.

### Research and evidence

- [`docs/research/`](docs/research/README.md) — research programs and evidence.
- [`sim/`](sim/) — deterministic simulations/analysis code.
- [`experiments/`](experiments/) — experiment definitions, harnesses, and results tooling.
- [`docs/audits/`](docs/audits/) — bounded audits and repository-health evidence.
- [`docs/findings/`](docs/findings/) — research and engineering findings.

### Community, governance, and project memory

- [`GOVERNANCE.md`](GOVERNANCE.md) and [`CONSTITUTION.md`](CONSTITUTION.md) — authority and protected principles.
- [`COMMUNITY_GROWTH_ENGINE.md`](COMMUNITY_GROWTH_ENGINE.md) — ACE community-growth experiment and safeguards.
- [`PROJECT_RULES.md`](PROJECT_RULES.md) — repository-wide operating rules.
- [`docs/conversations/`](docs/conversations/README.md) — append-only structured collaboration history.

## Public project record

The repository is the durable project record. Important conclusions from project work should be promoted into current architecture, specifications, decisions, findings, research evidence, governance, or implementation—not left only in chats or buried in historical notes.

Historical records remain valuable, but they should not silently override current canonical documents. See [`PROJECT_RULES.md`](PROJECT_RULES.md) and [`docs/README.md`](docs/README.md) for the documentation hierarchy.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).

## Invitation

IDKMesh starts from a simple admission: **we do not yet know the best way to coordinate intelligence at this scale.**

If you can improve a question, falsify an assumption, reproduce an experiment, write a test, find a security problem, make a contract clearer, reduce reviewer burden, improve onboarding, or build one verified component, you can contribute.

> **From uncertainty to collective intelligence—through evidence.**
