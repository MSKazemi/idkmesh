# Contributing to IDKMesh

Thank you for considering a contribution. IDKMesh is intentionally early, which means useful contributions include much more than production code.

The goal of this guide is to make a successful first contribution possible without requiring complete understanding of the project.

## Start here

Before contributing, read:

1. [`README.md`](README.md) — what IDKMesh is.
2. [`COMMUNITY.md`](COMMUNITY.md) — how the community works.
3. This file — how to make a contribution.

Read deeper architecture/research documents only when your contribution requires them.

## Choose a contribution type

Good contributions include:

- code and tests;
- bug reports and reproductions;
- documentation and diagrams;
- architecture critiques;
- research references and literature reviews;
- benchmark and experiment design;
- reproducing experiments;
- security and threat-model work;
- UX and developer-experience improvements;
- community and governance improvements;
- issue triage and pull-request review;
- translations and accessibility improvements;
- domain expertise;
- negative results that prevent repeated dead ends.

## Small contributions

For typo fixes, documentation clarity, small tests, or other narrow reversible changes, a pull request is enough.

Keep the change focused. Explain:

- what changed;
- why it helps;
- how it was checked.

## Larger contributions

Before investing heavily in a large feature, architecture change, new protocol, governance change, or expensive experiment, open an issue or RFC first.

Describe:

- the problem;
- the proposed approach;
- alternatives considered;
- how success will be evaluated;
- major risks;
- **Community Impact** — whether this makes participation, documentation, maintenance, review, or governance easier or harder.

The purpose is not to ask permission for every idea. It is to avoid duplicated work and surface disagreements while changes are still cheap.

## Pull-request principles

Prefer pull requests that are:

- small enough to review;
- linked to a clear problem or hypothesis;
- accompanied by tests/evidence appropriate to the change;
- documented for the next contributor, not just the current reviewer;
- explicit about known limitations;
- reversible when the design is experimental.

A pull request should not be merged simply because an AI model, experienced contributor, or maintainer says it is correct.

## AI-assisted contributions

AI-assisted contributions are welcome and expected in IDKMesh.

For materially AI-generated code, research, tests, or documentation, include a short provenance note when practical:

- model/tool used (if known);
- what the human contributor verified;
- whether tests or claims were independently checked;
- any uncertainty that remains.

Do not submit large volumes of unreviewed generated material. Generation must not grow faster than the community's ability to verify and maintain it.

## Running the tests

You do not need to read the architecture to run the gate. Two commands:

```bash
make setup    # once: creates .venv and installs the test dependencies
make test     # the pre-commit gate: the full unit suite
```

`make help` lists every tier. The ones you will use:

| Command | What it runs | When |
|---|---|---|
| `make smoke` | only the tests affected by your uncommitted changes | after each edit |
| `make test` | the full unit suite | before each commit |
| `make integration` | the unit suite plus the schema and link gates | before each push |
| `make gate` | whichever tier your current changes actually require | when unsure |

`make integration` is the closest local equivalent of the `PR Gate` check, so
running it before you push is the cheapest way to avoid a red pull request.
[`docs/TESTING.md`](docs/TESTING.md) explains why the tiers are drawn where they
are and what to do when one complains.

Two things that surprise newcomers, neither of which means you broke anything:

- Each tier has a **CPU-time budget** as well as a pass/fail result, so a green
  suite that runs too slowly still fails the tier. If the budget trips, first
  re-run it on an otherwise idle machine — heavy load from unrelated processes
  inflates measured CPU time substantially.
- Results are cached per tree state, so an unchanged tree reports
  `cached pass` instead of re-running. `make clean-cache` forces a full re-run.

If you cannot get the gate to run at all, that is a bug worth reporting — open
an issue describing your OS, Python version, and the failure.

## Code quality

Every code contribution should aim to provide:

- a reproducible way to run or test the change;
- tests for behavior that can be tested;
- no unnecessary dependencies;
- clear failure behavior;
- documentation for public interfaces;
- security consideration when code handles untrusted workers, artifacts, credentials, or execution.

## Research quality

Research contributions should distinguish:

- established external evidence;
- project observation;
- working hypothesis;
- speculative analogy;
- implementation decision.

For proposed experiments, define before execution when possible:

- hypothesis;
- baseline;
- independent variable(s);
- evaluation metrics;
- workload/dataset;
- resource budget;
- stopping rule;
- threats to validity.

Negative results are welcome.

## Review

A useful review can check more than correctness. Consider:

- Does this solve the stated problem?
- Is the evidence strong enough?
- Could a smaller change work?
- Does it create hidden coupling?
- Are security/trust assumptions clear?
- Can another contributor reproduce it?
- Is the documentation understandable?
- Does it increase future maintainer burden?
- What is the community impact?

## Contribution workflow

1. Find or open an issue for non-trivial work.
2. State what you plan to change.
3. Fork/branch and make a focused change.
4. Add tests, evidence, or documentation.
5. Open a pull request using the template.
6. Respond to review in public where possible.
7. Update the change until the evidence and maintainability are sufficient.
8. If the change represents a major durable decision, add/update a decision record.

### Linking issues without closing them

Reference an issue on the template's `Refs:` line. Use `Closes on merge:` only
when merging should actually resolve it.

This distinction is enforced, because GitHub closes an issue whenever a closing
keyword (`close`, `fix`, `resolve`, and their inflections) sits near an issue
reference, in a pull request title or body **and in any commit message** — and a
parenthetical such as "(does not close)" does not prevent it. Evidence pull
requests here routinely land while an independent-human review gate stays open,
so an accidental closure would post a false "resolved" status and dissolve that
gate.

The `PR Gate` check runs `tools/closing_keyword_guard.py` over the title, the
body, and every commit message in the pull request. If it fails, either move the
reference to `Closes on merge:` when closure is intended, or write the number
without `#` in prose, for example "issue 152".

## Newcomers are allowed to be uncertain

You may open an issue that says:

- what you currently understand;
- what is confusing;
- what you tried;
- what kind of contribution you want to make.

Confusion is useful project data. If several contributors misunderstand the same thing, the documentation or architecture needs improvement.

## Path to greater responsibility

IDKMesh uses a contributor ladder described in [`COMMUNITY.md`](COMMUNITY.md) and [`GOVERNANCE.md`](GOVERNANCE.md).

Review, documentation, research, security, and community contributions count toward trust and leadership just as code contributions do.

## Conduct and security

Please follow [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

For security vulnerabilities, do not open a public issue; follow [`SECURITY.md`](SECURITY.md).

## Questions

See [`SUPPORT.md`](SUPPORT.md) for the current help channels.
