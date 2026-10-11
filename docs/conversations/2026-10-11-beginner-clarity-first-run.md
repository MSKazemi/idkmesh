# Beginner comprehension and first-run documentation review (2026-10-11)

## Owner question / goal

Can a person with limited software or AI-agent experience immediately tell **what IDKMesh does, what works today, and how to try it**? Improve the public documentation and preserve the result in this repository.

## Findings from current `main`

- The existing [README](../../README.md) and [beginner guide](../BEGINNER_GUIDE.md) communicate the verification-first vision, but the public front door combines research hypotheses, reference-product ambitions, executable demos, and specialist implementation detail.
- `pyproject.toml` packages only the `idkmesh` Python module and exposes the `idkmesh` CLI.
- `idkmesh/cli.py` provides an existing `gate-audit` diagnostic for ground-truthed verdict matrices and `gate-audit-ui` for local viewing; the checked-in votes fixture explicitly identifies itself as synthetic.
- `scripts/demo.py` validates prepared work/evidence contracts and rejects intentionally invalid cases; it neither starts an AI worker nor proves live verifier independence.
- `idkmesh control-tower` is a local read-only inspection surface, not a hosted service or an automatic merge/dispatch UI.
- The [capability matrix](../CAPABILITY_MATRIX.md) explicitly rates the project as an alpha/research engineering preview and holds unfinished or unqualified capabilities outside public claims.
- Open documentation PR [#1004](https://github.com/MSKazemi/idkmesh/pull/1004) documents as-built modules, API/CLI, and troubleshooting. This change focuses on beginner comprehension and should not duplicate that specialist reference.

## Decision and work in this change

1. Lead the public README with a concrete job-to-be-done and direct beginner paths instead of requiring people to understand the research program first.
2. Rewrite the beginner guide around a verifiable **first result**: install the CLI in a local virtual environment, audit the committed vote matrix, and inspect readable output.
3. Explicitly separate the **available verdict-auditing path** from the **broader intended task/worker/verifier/decision framework cycle**; no single-step end-to-end automation is implied.
4. Include a worked mistake from the real fixture, explain `ground_truth` vs reviewer `verdicts`, and define terms in non-specialist language.
5. Adjust the published quickstart's first-screen explanation and make the link to the beginner guide visible.
6. Preserve explicit limits: synthetic evidence is not real observation; no AI key is needed for local demos; control-tower cannot dispatch, approve, or merge; external-project bootstrap remains dry-run planning.

## Scope and evidence

Base `main` reviewed: `bee77a6125dbccb58f166ec363e978cd960f43f3` (2026-10-11). Relevant sources inspected: `README.md`, `AGENTS.md`, `PROJECT_RULES.md`, `docs/BEGINNER_GUIDE.md`, `docs/GETTING_STARTED.md`, `docs/WHAT_IS_IDKMESH.md`, `docs/CAPABILITY_MATRIX.md`, `docs/PROJECT_ADOPTION_GUIDE.md`, `docs/RUN_LIFECYCLE_TUTORIAL.md`, `docs/start.html`, `pyproject.toml`, `idkmesh/cli.py`, `scripts/demo.py`, and `examples/gate-audit/panel-votes.example.json`.

This is a documentation and wording improvement, not a runtime capability or scientific evidence promotion. Tests or live user research are not claimed unless their results are reported in the PR. A useful subsequent check is a first-time-user walkthrough by someone who has never seen IDKMesh: ask them what the tool accepts, what it produces, and what it does *not* automate, before and after following the guide.

## Community impact

Makes the shortest hands-on path, evidence caveats, and onward routes obvious to new readers without requiring them to learn the architecture or join the research program first.

## AI/tool provenance

Drafted with ChatGPT GPT-6 using live GitHub-connected repository data. No independent human usability study is represented.

## Integration note (same documentation branch)

While this work was being prepared, `main` advanced from `bee77a6125dbccb58f166ec363e978cd960f43f3` to `12242ba12e4823c025c76dce2b471b830afbdf7c` with new command/API/library inventory documentation. The final documentation integrates those additions: the README is patched **onto the later main text**, and the beginner guide adds a direct link and introductory help commands for `docs/EXECUTABLE_CAPABILITIES.md`. No newer main changes are intentionally removed.
