# Getting Started: Using IDKMesh

IDKMesh is currently an **alpha research and engineering project**, not a finished
one-click multi-agent product. The most practical user-facing surface today is
the `idkmesh gate-audit` CLI. The repository also includes an executable
contract demo and a contribution/research environment.

This guide answers two questions:

1. **Who should use IDKMesh today?**
2. **What is the shortest path to use it successfully?**

## Who should use IDKMesh today?

### 1. Engineering teams that use multiple reviewers or AI judges

Use `idkmesh gate-audit` when a code-review, evaluation, moderation, or
acceptance gate collects multiple accept/reject verdicts and you can provide
ground truth for an audited candidate set.

Typical examples:

- a team using several LLM judges to review generated code;
- a CI or QA pipeline with multiple automated verifiers;
- a human-plus-AI review panel;
- a security or red-team process with seeded known-bad probes;
- an experiment that needs to measure whether reviewers make correlated errors.

The audit asks a specific question: **how much independent evidence is the
panel actually producing?**

### 2. Researchers working on multi-agent systems or collective intelligence

Use the repository when you want reproducible contracts, simulations,
experiments, provenance checks, or benchmark infrastructure for studying
coordination, verification, decomposition, reviewer dependence, governance, or
human/AI collaboration.

### 3. Open-source maintainers and platform engineers

Use the project as a reference for bounded task contracts, worker/verifier
separation, provenance, GitHub-native evidence, and explicit integration
authority.

### 4. Contributors who want to build the Verified Swarm Runner

The end-to-end Git-native Verified Swarm Runner is still being developed.
Contributors can work on the runner, adapters, schemas, experiments, CI,
documentation, security, community systems, or verification tooling.

## Who should *not* expect a finished product yet?

IDKMesh is not yet the right choice if you need:

- a polished one-click swarm that autonomously operates thousands of machines;
- a production service that automatically assigns arbitrary work to many live
  AI agents;
- a replacement for GitHub, CI, an agent framework, or a model provider;
- an automatic merge authority.

The current system deliberately keeps this authority boundary:

```text
worker success != acceptance
verification recommendation != merge authority
CI success != independent human review
```

## Path A: Try the contract demo

This is the fastest way to understand the core trust model.

### Step 1 — Install prerequisites

You need:

- Git;
- Python 3.11+ (the package currently lists Python 3.11, 3.12, and 3.13).

No model account or API key is required for the demo.

### Step 2 — Clone the repository

```bash
git clone https://github.com/MSKazemi/idkmesh
cd idkmesh
```

### Step 3 — Create a virtual environment

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-phase0.txt
.\.venv\Scripts\python.exe scripts\demo.py
```

### Step 4 — Install demo dependencies

Linux/macOS:

```bash
python -m pip install -r requirements-phase0.txt
```

### Step 5 — Run the demo

```bash
python scripts/demo.py
```

The demo validates committed synthetic fixtures. It intentionally checks both
valid and invalid contracts, including rejection of self-acceptance,
non-independent verification, missing security bounds, and mismatched
provenance.

Passing the demo means the contract validators behave as expected on those
fixtures. It does **not** prove real-world worker independence or approve any
change for merge.

## Path B: Audit a review or verifier panel

This is the most directly usable product surface today.

### Step 1 — Install the CLI

From the repository root:

```bash
pip install .
```

Confirm installation:

```bash
idkmesh --version
```

### Step 2 — Run the bundled example

```bash
idkmesh gate-audit examples/gate-audit/panel-votes.example.json --pretty
```

To save both machine-readable and human-readable output:

```bash
idkmesh gate-audit examples/gate-audit/panel-votes.example.json \
  --out gate-audit.json \
  --markdown gate-audit.md \
  --pretty
```

### Step 3 — Prepare your own verdict matrix

Create a JSON file with:

- a `gate_id`;
- `evidence_class`: `"synthetic"` or `"observed"`;
- candidates with known `ground_truth` of `"accept"` or `"reject"`;
- one or more verifiers;
- a verdict from every verifier for every candidate;
- optional seeded known-bad probes;
- optional `quorum` (default `0.5`, strict majority).

Minimal shape:

```json
{
  "gate_id": "my-review-gate",
  "evidence_class": "observed",
  "quorum": 0.5,
  "candidates": [
    {"id": "c01", "ground_truth": "accept"},
    {"id": "c02", "ground_truth": "reject"},
    {
      "id": "p01",
      "ground_truth": "reject",
      "probe": true,
      "probe_kind": "seeded-defect"
    }
  ],
  "verifiers": [
    {
      "id": "reviewer-a",
      "verdicts": {
        "c01": "accept",
        "c02": "reject",
        "p01": "reject"
      }
    }
  ]
}
```

For meaningful panel statistics, use more than the minimal toy example. The
contract requires at least two non-probe candidates and one verifier.

### Step 4 — Run the audit on your data

```bash
idkmesh gate-audit my-panel-votes.json \
  --out my-panel-report.json \
  --markdown my-panel-report.md \
  --pretty
```

Exit code `0` means success. Input/usage failures return `2`.

### Step 5 — Read the important results

Focus on:

- **verifier accuracy** — how each verifier performed against ground truth;
- **mean pairwise error correlation** — whether verifiers tend to fail on the
  same candidates;
- **panel error / false accepts / false rejects** — measured gate behavior;
- **effective votes** — the approximate number of independent verifier votes
  that would match the measured panel performance;
- **effective-vote ceiling** — whether dependence limits how much value can be
  gained simply by adding more similar reviewers;
- **probe breaches** — seeded known-bad cases the panel still accepted.

A panel can have many nominal reviewers but much less independent evidence if
their errors are strongly correlated.

### Step 6 — Use the result as a diagnostic, not an authority decision

`gate-audit` does not run your reviewers, select candidates, accept work, or
merge code. It measures a verdict matrix that you already collected.

Use the result to ask better operational questions, for example:

- Are our reviewers too similar?
- Are they actually discriminating between good and bad candidates?
- Are known-bad probes getting through?
- Would adding more reviewers help, or do we need more diverse verification?
- Is our quorum rule producing an unacceptable false-accept rate?

## Path C: Add Gate Audit to GitHub Actions

A repository can run the audit in CI:

```yaml
- uses: MSKazemi/idkmesh/actions/gate-audit@main
  with:
    votes-file: path/to/panel-votes.json
```

Treat the output as diagnostic evidence unless your own repository policy
explicitly defines how that evidence is used.

## Path D: Use IDKMesh to develop another application

If you already have (or are creating) a separate software project, the practical
IDKMesh adoption path today is GitHub-native and verification-first:

1. create the application repository and a reproducible baseline test/CI path;
2. protect the canonical branch and keep merge authority separate from workers;
3. define project policy using the ProjectManifest/DomainPack model;
4. turn one small issue into a bounded Work Unit;
5. route it to a human or agent by required capability and risk;
6. require a candidate branch/PR plus exact test/provenance evidence;
7. verify the exact candidate revision independently;
8. integrate only through the protected human/governance path;
9. record the observed outcome and use it to shape the next Work Unit.

The full step-by-step workflow, role model, LLM/agent routing guidance, directory
layout, state machine, scenarios, and machine-friendly checklist are in
[Use IDKMesh to Build Another Software Project](PROJECT_ADOPTION_GUIDE.md).

This path does **not** claim that IDKMesh already provides a one-command external
repository bootstrap or a production dispatcher for every model provider. The
guide separates the parts that work today from the reference-product automation
that is still being built.

## Path E: Contribute to IDKMesh itself

### Step 1 — Read the public front door

Read:

1. `README.md`
2. `CONTRIBUTING.md`
3. `COMMUNITY.md`

You do not need to read the full research archive first.

### Step 2 — Choose a contribution path

Useful paths include:

- code and tests;
- research and experiment reproduction;
- pull-request review;
- security and threat modeling;
- documentation and onboarding;
- community tooling and governance;
- domain expertise;
- interoperability and adapters.

### Step 3 — Check current work before starting

Look at open issues, assignees, recent comments, and linked pull requests.
State the bounded change you intend to make so work is not duplicated.

### Step 4 — Make a focused branch and change

Prefer a small, reviewable change with explicit evidence or tests.

### Step 5 — Run repository checks

On POSIX environments:

```bash
make setup
make test
make integration
```

Portable Python fallback:

```bash
python -m pip install --disable-pip-version-check pytest
python -m pip install --disable-pip-version-check -r requirements-phase0.txt
python -m pytest -q
```

If you change Markdown, also run:

```bash
python scripts/check_links.py
```

### Step 6 — Open a pull request

Describe:

- the problem;
- your bounded change;
- tests or evidence;
- known limitations;
- community impact when relevant.

AI-assisted contributions are welcome, but material generated work should be
reviewed and its provenance noted when practical.

## Advanced use: WorkUnits, adapters, and the future runner

The repository already contains versioned WorkUnit, ResultManifest,
EvaluatorPlan, and VerificationResult contracts plus protocol-neutral adapters
and A2A/MCP mappings.

The target lifecycle is:

```text
bounded repository task
  -> WorkUnit
  -> replaceable worker adapter
  -> candidate artifacts + ResultManifest
  -> verifier-owned EvaluatorPlan
  -> independent VerificationResult
  -> evidence/reporting
  -> explicit human/governance integration decision
```

These pieces are suitable for contributors and researchers today, but they are
not yet packaged as a polished general-purpose swarm application.

## A simple rule for deciding where to start

- **I just want to understand IDKMesh:** run `python scripts/demo.py`.
- **I have reviewer/LLM-judge verdicts:** use `idkmesh gate-audit`.
- **I maintain a project and want continuous diagnostics:** integrate the
  Gate Audit GitHub Action.
- **I want to use IDKMesh while building a different application:** follow the
  [Project Adoption Guide](PROJECT_ADOPTION_GUIDE.md).
- **I want to study multi-agent verification or coordination:** use the schemas,
  simulations, experiments, and interop layers.
- **I want a finished autonomous swarm product:** follow or contribute to the
  Verified Swarm Runner work; that product is not complete yet.
- **I want to help build the project:** follow `CONTRIBUTING.md` and
  `COMMUNITY.md`.

## Where to ask questions

Use GitHub Discussions for broad questions and ideas. Use issues for defects or
bounded actionable work. Follow `SECURITY.md` rather than a public issue for
security vulnerabilities.
