# IDKMesh for Absolute Beginners

If the rest of the repository feels complicated, start here.

## IDKMesh in one sentence

**IDKMesh helps humans and AI agents work together without trusting the first answer automatically.**

Think of it as a combination of:

- a **team manager** that gives small jobs to workers;
- a **quality-control system** that checks the work separately;
- a **logbook** that records what happened and what evidence exists;
- a **safety boundary** that prevents a worker from approving its own work.

The long-term goal is to make this useful for large teams of people, AI agents, software tools, and computers.

Today, IDKMesh is still an **alpha research and engineering project**. It is not yet a finished one-click AI swarm product.

## What problem is it trying to solve?

Imagine you ask one AI agent:

> "Please change my software."

The agent may produce a good answer, but it may also make a mistake.

Now imagine you ask five AI agents. That sounds safer, but the five agents may make the **same mistake**. Five answers do not automatically mean five independent opinions.

IDKMesh is trying to solve problems like these:

1. **Big work is hard to control.**  
   A large goal should be split into small, bounded jobs.

2. **AI can be confidently wrong.**  
   The system should not trust a worker just because it says "done."

3. **More reviewers do not always mean more safety.**  
   Several reviewers may repeat the same error.

4. **It is often unclear who did what.**  
   The project keeps provenance: records of workers, inputs, outputs, checks, and evidence.

5. **The same actor should not create and approve its own result.**  
   Work and verification are separated.

6. **Automation should not silently gain authority.**  
   A successful worker, verifier, or CI check does not automatically get merge authority.

The basic rule is:

```text
worker says "done"
        !=
work is accepted
```

## A simple example

Suppose you want to add a login feature to a project.

Without a verification-first process:

```text
AI writes code
   ->
AI says it works
   ->
code is accepted
```

With the IDKMesh idea:

```text
Goal: add login
   ->
Create a small, clear task
   ->
Worker writes the code
   ->
Worker records what it changed
   ->
A separate verifier checks it
   ->
Tests and evidence are recorded
   ->
A human or governance rule decides whether to integrate it
```

The important difference is that **the worker does not approve itself**.

## How does IDKMesh work?

You do not need to remember the technical names yet. The basic flow is:

### 1. Start with a goal

Example:

> "Fix this bug."

### 2. Turn the goal into a small job

IDKMesh calls a bounded task a **WorkUnit**.

A WorkUnit tries to make the job clear:

- what should be done;
- what is allowed;
- what is not allowed;
- what evidence is expected;
- what security limits apply.

### 3. Give the job to a worker

The worker could be:

- a human;
- an AI coding agent;
- a script;
- another software tool;
- eventually another machine or service.

### 4. Save the result and its history

The result should include information about what was produced and where it came from.

This helps answer:

> "What created this result, from what inputs, and under what rules?"

### 5. Check the work separately

A different verifier checks the result.

The verifier should not simply trust the worker's claim.

### 6. Save the verification evidence

The system records what was checked and what the verifier found.

### 7. Make a separate integration decision

Even a successful verification is not automatically permission to merge or publish.

The final authority remains separate.

## What can I actually use today?

There are three useful ways to use the repository right now.

### Option A — Run the demo

This is the easiest way to understand the trust model.

You need:

- Git;
- Python 3.11 or newer.

Clone the project:

```bash
git clone https://github.com/MSKazemi/idkmesh
cd idkmesh
```

Create a Python environment on Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-phase0.txt
```

Run the demo:

```bash
python scripts/demo.py
```

The demo deliberately tests both valid and invalid examples.

For example, it checks that the system rejects cases where:

- a task is missing required security limits;
- a worker tries to accept its own work;
- the same identity is used as worker and independent verifier;
- evidence does not match the supplied artifacts.

No AI API key is required for this demo.

### Option B — Use `idkmesh gate-audit`

This is the most immediately usable product in the repository today.

Install it from the repository:

```bash
pip install .
```

Run the included example:

```bash
idkmesh gate-audit examples/gate-audit/panel-votes.example.json --pretty
```

The tool helps answer a question like:

> "I have several reviewers. Are they really giving me several independent checks, or are they mostly making the same mistakes?"

It looks at reviewer/verifier results and reports things such as:

- reviewer accuracy;
- whether reviewers fail on the same items;
- false accepts and false rejects;
- an estimate of effective independent votes;
- whether known-bad test cases got through.

This can be useful if you use:

- multiple AI judges;
- multiple automated code reviewers;
- human + AI review panels;
- CI/QA verification systems;
- evaluation pipelines.

It is a **diagnostic tool**. It does not approve code or make merge decisions.

For your own review data, continue with [Getting Started](GETTING_STARTED.md).

### Option C — Help build the larger system

The complete Git-native **Verified Swarm Runner** is still being developed.

You can contribute without understanding the entire project.

Useful entry points include:

- documentation;
- Python tests;
- reproducibility checks;
- verification tools;
- security;
- agent adapters;
- experiments;
- contributor experience.

See [Contributor Quickstart](community/CONTRIBUTOR_QUICKSTART.md).

## A real-world situation where this idea helps

Imagine you use five AI models to review generated code.

All five say:

> "Looks good."

You may think you have five independent confirmations.

But if all five models learned similar patterns, use similar prompts, or fail on the same kind of bug, the five votes may contain much less independent information than you think.

IDKMesh's current `gate-audit` tool is designed to measure this kind of problem from verdict data that you already collected.

That is one concrete problem the repository can help with **today**.

## What IDKMesh does not solve yet

Do not expect the current repository to:

- automatically run thousands of AI agents for you;
- automatically distribute arbitrary jobs across the internet;
- safely control millions of computers;
- replace GitHub;
- replace your AI agent framework;
- replace your CI system;
- automatically decide what should be merged;
- prove that a result is correct just because several agents agree.

Those are either outside the project or still future work.

## Who should use it today?

IDKMesh is most useful today for:

- AI-agent researchers;
- software engineers experimenting with multiple AI reviewers;
- teams building verification or evaluation pipelines;
- open-source maintainers interested in safer human + AI collaboration;
- researchers studying collective intelligence;
- contributors who want to help build the Verified Swarm Runner.

If you only want a simple chatbot or a finished autonomous coding swarm, IDKMesh is not that product yet.

## Tiny glossary

| Word | Very simple meaning |
| --- | --- |
| **WorkUnit** | A small job with clear limits |
| **Worker** | The person, AI, or tool doing the job |
| **Result** | What the worker produced |
| **Verifier** | A separate checker |
| **Evidence** | Information showing what was tested or observed |
| **Provenance** | The history of where a result came from |
| **Gate** | A checkpoint before something is accepted |
| **Integration** | Putting an accepted change into the main project |
| **Mesh** | A network of different people, agents, tools, and computers |
| **IDK** | "I don't know" — uncertainty should be visible instead of hidden |

## The most important idea

You can understand most of IDKMesh by remembering this:

> **Do not trust an answer only because it was produced. Check it independently, keep the evidence, and keep final authority separate.**

## What should I do first?

If you are completely new, use this order:

1. Read this page.
2. Run `python scripts/demo.py`.
3. Run the example `idkmesh gate-audit`.
4. Read [Getting Started](GETTING_STARTED.md).
5. If you want to contribute, use the [Contributor Quickstart](community/CONTRIBUTOR_QUICKSTART.md).

You do **not** need to understand the whole repository before trying those steps.
