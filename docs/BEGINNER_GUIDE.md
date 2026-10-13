---
description: "A plain-English explanation of what IDKMesh does today, what is still being built, and a first working audit you can run without an AI account."
---
# IDKMesh for Absolute Beginners

**New to AI agents, GitHub, or programming? Start here.** You do not need to understand the research papers or the architecture to understand what this project is for.

## IDKMesh in one sentence

**IDKMesh helps people assess AI-assisted work by separating what a worker *claims* from what an independent check *shows*.** It is developing a broader framework for coordinating people, AI agents, and tools around that principle.

Imagine five AI reviewers all say **"approve."** Did five different checks really happen, or did they all miss the same error? IDKMesh has a tool that analyzes recorded reviewer decisions against known correct answers to help you investigate this question.

**Important:** IDKMesh is an **alpha research and engineering project**. The review-auditing tool works today; an automatic, general-purpose AI swarm that takes a request, runs arbitrary agents, verifies everything, and merges the result is **not yet a finished product**.

## What problem is it trying to solve?

When AI produces code, an answer, or a proposed change, three questions matter:

1. **What was requested?** The job needs clear boundaries.
2. **What evidence says the result is good?** A worker saying "done" is not proof.
3. **Who is allowed to accept it?** The worker and checker should not silently approve their own work.

Several reviewers can also make *the same* mistake. Simply counting reviewers does not tell you how much independent confidence they add.

This project combines **research on that problem** with **working software components** that record, validate, inspect, and analyze evidence.

## An example without jargon

Suppose a team uses five AI models to review a proposed software change.

| What happens | What it means |
| --- | --- |
| A change is submitted | This is the **candidate** to be reviewed. |
| Five reviewers vote approve/reject | These are **verdicts**, not automatically the correct answer. |
| The team has test cases with known correct outcomes | This is **ground truth**: which candidates really should be accepted or rejected. |
| IDKMesh compares the verdicts with those known outcomes | The `gate-audit` tool measures mistakes, shared mistakes, and how useful the whole panel was. |
| A responsible person reads the report | **The person or project's governance still makes the decision**; the report does not accept or merge code. |

The bundled example contains **synthetic (made-up) votes**, not real AI reviewers. In that example, five nominal reviewers correspond to roughly **1.69 effective independent votes** under the measured gate-performance metric. This is an illustration, **not** a claim that every five-reviewer panel has that value.

## How does IDKMesh work?

There are **two related but different paths**. Do not confuse them.

**Path 1 — a working tool you can try now:**

```text
Your saved reviewer votes + known correct answers
                  |
                  v
         idkmesh gate-audit
                  |
                  v
   JSON report / readable Markdown report
                  |
                  v
       You interpret the evidence
```

`gate-audit` does **not** call an AI model, run the reviewers, discover the correct answers, or make a merge decision.

**Path 2 — the wider framework's intended work cycle:**

```text
Goal --> small, bounded task --> human / AI worker
                                  |
                                  v
                         candidate + history
                                  |
                                  v
                       separate verification
                                  |
                                  v
                         evidence for review
                                  |
                                  v
                       human / policy decision
```

IDKMesh calls the bounded task a **WorkUnit**. It has schemas and validators for these stages, a local evidence viewer, and experimental coordination components. **This diagram is a framework model, not a promise that a single command runs the whole cycle for any GitHub repository today.**

The most important rule is:

> A worker saying "finished" is not verification. Verification is not permission to merge.

## What can I actually use today?

| If you want to... | Current status | Start with |
| --- | --- | --- |
| Understand the rule that workers cannot approve themselves | **Working synthetic fixture demo** | `python scripts/demo.py` |
| Analyze a panel of reviewers when you already have verdicts and known correct outcomes | **Working CLI + local browser UI** | `idkmesh gate-audit` or `idkmesh gate-audit-ui` |
| Look at recorded work attempts, verification results, and evidence | **Working read-only local viewer** | `idkmesh control-tower` |
| Create/read/cancel a local run record | **Working local record management**; does not start or terminate a remote worker | [Run lifecycle tutorial](RUN_LIFECYCLE_TUTORIAL.md) |
| Adopt bounded tasks and review/evidence rules in another repository | **Manual operating model + components; automation incomplete** | [Project Adoption Guide](PROJECT_ADOPTION_GUIDE.md) |
| Automatically run arbitrary AI agents across machines and approve their code | **Not a finished capability** | [Capability Truth Matrix](CAPABILITY_MATRIX.md) |

These are different levels of maturity. **A program existing is not proof it is safe or production-ready.** For the exact evidence and limitations behind each claim, see the [Capability Truth Matrix](CAPABILITY_MATRIX.md).

### For the complete list of commands

The CLI also exposes tools for inspecting connector metadata, explaining route eligibility, and reading local run/project/event records. They are **not** a general live-agent deployment wizard. To explore without modifying anything, run:

```bash
idkmesh --help
idkmesh connections --help
idkmesh run --help
idkmesh control-tower --help
```

For the **complete, code-backed CLI, local API, and module inventory**, see [Executable Capability Reference](EXECUTABLE_CAPABILITIES.md). It marks limits including offline-only connector probes, loopback-only HTTP, and missing automatic decision/merge authority.

## Your first 10 minutes: run an actual audit

This is the most useful first hands-on experience. You will analyze **sample reviewer data stored on your own computer**. You do **not** need ChatGPT, Claude, an API key, a GPU, cloud resources, or a paid service.

### Step 1 — what you need

- A computer with **Python 3.11 or newer** and **Git** installed.
- A **terminal** (a window where you type commands).
- An internet connection only to obtain the repository and install the package.

The next commands are for **Linux or macOS**. Windows users can follow the [PowerShell instructions in Getting Started](GETTING_STARTED.md#path-a-try-the-contract-demo) and use the same `idkmesh` commands after installation.

### Step 2 — get the software

Copy and run these commands, one line at a time:

```bash
git clone https://github.com/MSKazemi/idkmesh.git
cd idkmesh
python -m venv .venv
source .venv/bin/activate
python -m pip install .
idkmesh --version
```

What the commands mean:

- `git clone` downloads a local copy of the repository.
- `cd idkmesh` moves into its directory.
- `venv` creates an isolated Python environment so you do not change your other Python projects.
- `pip install .` installs the small IDKMesh command-line package.
- `idkmesh --version` confirms that the command is available.

### Step 3 — analyze the included example

```bash
idkmesh gate-audit examples/gate-audit/panel-votes.example.json \
  --out first-gate-audit.json \
  --markdown first-gate-audit.md \
  --pretty
```

**What to expect:** if the command succeeds, it creates two files in your current directory:

- `first-gate-audit.json` — a machine-readable report.
- `first-gate-audit.md` — a readable report that you can open in a text editor.

On Linux/macOS, you can also read the Markdown file with:

```bash
cat first-gate-audit.md
```

Look for the panel error measurements, shared reviewer mistakes, **effective votes**, and **probe breaches** (known-bad test cases wrongly accepted). The input is labelled `"evidence_class": "synthetic"`. **Do not present the generated numbers as measurements of your real team.**

**Prefer clicking instead of reading terminal output?** Use the included local browser interface with the same example:

```bash
idkmesh gate-audit-ui examples/gate-audit/panel-votes.example.json
```

The browser connects to a process on your own computer (`127.0.0.1`). Stop that process in the terminal with `Ctrl+C`.

### Step 4 — understand the input

Open [`panel-votes.example.json`](https://github.com/MSKazemi/idkmesh/blob/main/examples/gate-audit/panel-votes.example.json). A **JSON** file is structured text; the braces and quotes help software read it.

Notice these fields:

| Field | In everyday language |
| --- | --- |
| `candidates` | The things being checked |
| `ground_truth` | The known correct accept/reject outcome for each candidate |
| `verifiers` | The reviewers in the panel |
| `verdicts` | What each reviewer said about each candidate |
| `probe` | A deliberately included known-bad test case |
| `evidence_class` | Whether the input is an illustration (`synthetic`) or a record of something observed (`observed`) |

For example, in the included file, candidate `c10` should be **rejected**, but `reviewer-a` voted **accept**. That is an error the analysis can count. A verifier's opinion is not the ground truth.

To use **your own data**, you must gather the verdicts and establish the correct outcomes first. Changing `evidence_class` to `observed` does **not** turn invented results into real evidence. See the [complete data format and examples](GETTING_STARTED.md#path-b-audit-a-review-or-verifier-panel).

### Step 5 — decide what you learned

Ask three questions:

1. Do the reviewers tend to make the **same errors**?
2. Did the panel accept any **known-bad** candidates?
3. Does adding more similar reviewers seem helpful, or is a different kind of check needed?

The report informs those questions; it does **not** answer whether a new code change is safe in all circumstances.

## Try two other learning paths

### See why the project separates workers from checkers

This demo validates **prepared examples** against the project's task, result, and verification rules:

```bash
python -m pip install -r requirements-phase0.txt
python scripts/demo.py
```

You should see valid examples and **intentional rejections**, such as a worker trying to accept its own result or a task missing security limits. A rejection is a *successful contract check*. **No live AI worker or external verifier runs in this demo.**

### Inspect what a completed two-attempt run looks like

```bash
idkmesh control-tower
```

This opens a **local read-only evidence viewer** using a committed example when no path is supplied. You can inspect the separate worker-claim, verification-evidence, and human-authority layers. **The viewer cannot run agents, record a human decision, push code, or merge a pull request.** For a more detailed local walkthrough, see the [Run Lifecycle Tutorial](RUN_LIFECYCLE_TUTORIAL.md).

## Propose a task without writing JSON

Select **IDKMesh WorkUnit request** from the GitHub new-issue chooser and describe a small task using labelled fields. The [no-JSON WorkUnit walkthrough](help/GITHUB_WORKUNIT_FORM.md) includes a reproducible offline preview with valid, malformed, and out-of-policy examples. The form is **untrusted planning input**: it cannot dispatch an agent, grant secrets, remove independent verification, or approve a merge.

## How can I use IDKMesh with my own project?

Today, a maintainer can **apply the operating model**: write small tasks with clear permissions, have people or external AI tools propose changes, check changes separately, and use GitHub's own review/branch protections before merging. IDKMesh provides contracts, validators, and related tooling, but **you must still connect and operate many of those pieces yourself**.

If you want a step-by-step adoption plan, read the [Project Adoption Guide](PROJECT_ADOPTION_GUIDE.md). The **one-command external-project runner and automatic integration are unfinished**; the GitHub-first bootstrap command is currently **dry-run planning only**, not a live install wizard.

## Common beginner questions

**Is IDKMesh an AI model or a chatbot?** No. It does not train a model and is not a conversational assistant.

**Will it write code or fix an issue by itself?** Not as a general-purpose, install-and-run product today. The repository includes experimental agent/coordination components, but the end-to-end reference runner is unfinished.

**Does `gate-audit` review my GitHub pull request?** No. You first provide recorded accept/reject verdicts and known correct answers. The command measures the review *process*, not the content of an arbitrary PR.

**Does a high score mean the software is safe?** No. The conclusions depend on the tasks sampled, their known answers, the quality of the evidence, and the review policy.

**Do I need a cloud account or AI API key to follow this guide?** No. The three local demos above use committed examples.

**Does IDKMesh automatically approve or merge changes?** No. The evidence tools do not grant integration authority. The project deliberately separates a worker's claim, a checker's findings, and a human or explicitly governed decision.

## When something goes wrong

| Problem | First thing to try |
| --- | --- |
| `python: command not found` | Your operating system may call it `python3`; verify Python 3.11+ is installed. |
| `idkmesh: command not found` | Activate the `.venv` environment again; run `python -m pip install .` from the repository root. |
| The example JSON file cannot be found | Run `cd idkmesh` to return to the cloned repository root. |
| The contract demo complains about a missing dependency | Run `python -m pip install -r requirements-phase0.txt` in the active environment. |
| You are using Windows | Follow [Getting Started](GETTING_STARTED.md) for PowerShell-specific environment commands. |

For deeper setup problems, see [Getting Started](GETTING_STARTED.md) or ask in [GitHub Discussions](https://github.com/MSKazemi/idkmesh/discussions). Report reproducible bugs in [GitHub Issues](https://github.com/MSKazemi/idkmesh/issues), and report security concerns privately using [SECURITY.md](https://github.com/MSKazemi/idkmesh/blob/main/SECURITY.md).

## Tiny glossary

| Word | Simple meaning |
| --- | --- |
| **Agent / worker** | A person, AI system, or tool doing a job |
| **WorkUnit** | A small task that says what is allowed, required, and forbidden |
| **Candidate** | A proposed answer, change, or artifact |
| **Verifier** | A checker that evaluates a candidate separately from its creator |
| **Evidence** | The recorded inputs, checks, outcomes, and supporting facts |
| **Provenance** | Where an artifact came from and which versions created it |
| **Review gate** | A checkpoint where proposed work is considered for acceptance |
| **Effective votes** | An estimate of how much independent checking a panel's outcomes represent |
| **Integration / merge** | Accepting a change into the project's main version |
| **Framework** | Reusable building blocks and rules that different applications can adopt |

## Who should use it today?

IDKMesh is particularly relevant to teams evaluating multiple AI/human reviewers, researchers studying agent reliability, maintainers who need auditable evidence, and contributors interested in building trustworthy human–AI collaboration tools.

If you need a simple chatbot, automatic PR reviewer, or fully managed multi-agent coding service today, **this is not yet that product**.

## What should I do first?

**Start with the panel audit above.** It provides one tangible result without requiring an AI model. Then choose the next page that matches your goal:

- [Getting Started](GETTING_STARTED.md) — detailed commands and using your own data.
- [What Is IDKMesh?](WHAT_IS_IDKMESH.md) — the larger framework/research vision.
- [Project Adoption Guide](PROJECT_ADOPTION_GUIDE.md) — use the collaboration model with another repository.
- [Capability Truth Matrix](CAPABILITY_MATRIX.md) — what is demonstrated, experimental, or planned.
- [Contributor Quickstart](community/CONTRIBUTOR_QUICKSTART.md) — contribute one small improvement.
