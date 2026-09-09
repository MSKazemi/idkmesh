# Contributing to IDKMesh

Thank you for considering a contribution. IDKMesh is intentionally early, which means useful contributions include much more than production code.

The goal of this guide is to make a successful first contribution possible without requiring complete understanding of the project.

## Start here

Before contributing, read:

1. [`README.md`](README.md) — what IDKMesh is.
2. [`COMMUNITY.md`](COMMUNITY.md) — how the community works.
3. This file — how to make a contribution.

Read deeper architecture/research documents only when your contribution requires them.

**Looking for one concrete task or shared technical responsibility?** See the
[contributor pilot](docs/community/CONTRIBUTOR_PILOT_2026_09.md) and the public
[co-maintainer / bring-your-own-agent invitation](https://github.com/MSKazemi/idkmesh/issues/407).

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

You do not need to understand the research side of this repository to run the
tests. From the repository root:

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements-phase0.txt pytest
PYTHONPATH=. python -m pytest -q
```

Use Python 3.11 or 3.13 to match the stable PR gate. The example above is for
Linux/macOS shells. In Windows PowerShell, create the environment with
`python -m venv .venv`, then use `.\.venv\Scripts\python.exe` instead of `python`
for installation and tests, and set `$env:PYTHONPATH = "."` before running tests.
Activation or a machine-wide execution-policy change is not required.
These are setup instructions, not evidence that every operating system has
already been tested by a contributor.

These commands work without an unmerged Makefile or local testkit. If an older
issue refers to `make setup`, `make test`, or `make integration`, use the current
instructions here unless that tooling actually exists in your checkout.

That collects both suites — `tests/` and `interop/tests/` — in a single run. To
run one file while you work:

```bash
PYTHONPATH=. python -m pytest -q tests/test_r2.py
```

If your change touches Markdown, run the same local link gate as CI:

```bash
python scripts/check_links.py
```

The command checks Markdown files/anchors and repository-relative links to
tracked scripts, schemas, images, and directories, without network access.
Exit codes are `0` for no findings, `1` for findings, and `2` when inspection
cannot run. Add `--json` for a deterministic machine-readable report. It needs
Python and Git, not an API key or extra Python packages.

Sources under `tests/fixtures/` contain deliberately broken links and are
excluded; findings everywhere else must be zero. Links resolve against the
**tracked** file index, so `git add` a new file before checking. The command does
not stage files, repair links, or change the repository. Existing GitHub-route
exemptions and repository-absolute asset exclusions remain; this is not a
complete Markdown parser or a check of external website availability.

The lower-level `tools/idkgraph_link_check.py` remains the unchanged T2
Markdown/identity report, not the combined gate. See
[the stable PR gate](.github/workflows/pr-gate.yml) for the CI invocation.

**Do not verify your work with `python -m unittest discover`.** It silently
under-collects — `unittest` only finds `TestCase` subclasses, so the 162
module-level `test_*` functions in `tests/` are invisible to it. It runs 1476
tests and prints `OK`; `pytest` collects 1638. A tenth of the suite is skipped
with no indication anything was missed.

Two skips are expected and are not a problem with your setup:
`interop/tests/test_sdk_conformance.py` skips two tests unless the optional
interoperability SDKs are installed with
`python -m pip install -r requirements-interoperability.txt`.

If you cannot get the tests to run at all, that is a bug worth reporting — open
an issue with your OS, your Python version, and the failure.

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

### The automated reviewer

Pull requests may receive an automated review from CodeRabbit, configured in
[`.coderabbit.yaml`](.coderabbit.yaml).

**Its output is advisory and carries no authority.** It cannot approve, block, or
merge anything, and it is wrong often enough that you should argue with it. If it
raises a point you disagree with, say so in the thread and leave the disagreement
visible — that exchange is more useful to the next contributor than a silently
dismissed comment.

This is deliberate rather than incidental. The same separation runs through the
WorkUnit contracts: a worker's *claim*, a verifier's *evidence*, and *integration
authority* are three different things, and no reviewer — human, model, or
maintainer — collapses them by asserting a change is correct. A pull request is
merged on evidence, not on who vouched for it.

You are welcome to reply to it directly in the thread. You are equally welcome to
ignore it.

## Contribution workflow

1. Find or open an issue for non-trivial work.
2. State what you plan to change.
3. Fork/branch and make a focused change.
4. Add tests, evidence, or documentation.
5. Open a pull request using the template.
6. Respond to review in public where possible.
7. Update the change until the evidence and maintainability are sufficient.
8. If the change represents a major durable decision, add/update a decision record.

### Keep private files out of the commit

This repository is public, and coding agents and editors leave local files in the
working tree. `.gitignore` covers the usual ones — `CLAUDE.md`, `GEMINI.md`,
`.note*`, `.env*`, `*.local`, `.vscode/` and `.DS_Store` — but the rules only help
if you stage deliberately. Prefer naming paths over `git add -A`, and read
`git status` before you commit.

`AGENTS.md` is the exception and stays tracked: it is the public
[agents.md](https://agents.md) contributor standard, holds no private
configuration, and is the file coding agents read first.

`tests/test_private_file_ignore_rules.py` asks `git check-ignore` what `git add`
would actually do, so a regression in these rules fails the suite rather than
surfacing as a published secret.

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

When you check a squash subject by hand, pass the pull request's own number:

```bash
python tools/closing_keyword_guard.py --file "subject=subject.txt" --self 362
```

`gh pr merge --squash` appends `(#N)` to the subject, so a title that
legitimately contains a closing keyword otherwise reports a violation against
the pull request being merged. `--self` suppresses that one number and reports
it under `suppressed_self_references`; a reference to any other number in the
same subject is still a violation.

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
