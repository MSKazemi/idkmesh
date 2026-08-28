# Target Execution Convergence Follow-up

Date: 2026-08-28

This follow-up records repository changes that landed while the targets/goals/tasks planning turn was still active.

## Landed foundations

Two previously in-review components are now on `main`:

- **PR #78** — deterministic two-attempt orchestration kernel;
- **PR #81** — EvaluatorPlan v0.1 / Evaluator Sovereignty binding.

PR #78 makes the multi-attempt control plane real: separate attempt histories, independent verifier outcomes, worker failure isolation, semantic replay, no automatic candidate selection, and no merge authority.

PR #81 makes evaluator control content-addressed and bound to the exact Work Unit/source revision and exact required-validator set before positive decision support is possible.

The canonical trust chain is now:

```text
WorkUnit
 -> ResultManifest
 -> EvaluatorPlan
 -> VerificationResult
 -> human/integration decision
```

## Safety fix discovered and implemented

A control-plane authority audit found that both verification CLI entrypoints could write `--output` to arbitrary repository-relative paths:

- `experiments/local_verifier.py`;
- `experiments/evaluator_plan_runner.py`.

This meant a component described as read-only/evidence-only could target a tracked file such as `README.md`.

PR #90 was opened to make executable authority match the intended authority:

```text
verification output -> root results/ only
```

Root `results/` is already ignored by `.gitignore`.

PR #90 adds fail-closed self-tests for canonical-path output attempts and preserves existing candidate-evaluation and EvaluatorPlan semantics. Both **Phase 0 schema check** and **Evaluator plan binding** CI pass on head `b955d7474841ca018cc4e0878f542542841239d2`.

No self-merge or self-approval was performed.

## Canonical tracker refresh

The main execution issues were updated again to avoid stale descriptions:

- **#4** now treats PR #78 Phase A0 as completed foundation and focuses on the real node adapter after #34/#37 plus later 3–5 attempt fan-out;
- **#5** now focuses on real repository patch/log bundle verification through EvaluatorPlan, followed by a 5–10 task benchmark cohort;
- **#16** now treats PR #72, PR #81, and PR #78 as completed foundations and names the remaining v0.1 gates explicitly.

## Current product bottleneck

The principal physical/runtime blocker is still:

```text
PR #34 canonical node
 -> synchronize with current main
 -> controlled Docker acceptance #37
 -> independent sandbox/path review
```

The assistant environment does not provide the controlled Docker host required by #37, so that gate was not fabricated or claimed.

## Current next technical target

After PR #90 safety review, #5 Phase B1 should extend the canonical EvaluatorPlan-bound verifier to the real node smoke bundle without executing candidate code.

Minimum independently observed checks:

- exact Work Unit / ResultManifest / EvaluatorPlan binding;
- candidate patch/log digests;
- safe unified-diff path parsing;
- `allowed_paths` / `forbidden_paths` enforcement;
- verifier-owned semantic acceptance for the harmless README smoke property;
- scope-valid but semantically wrong negative candidate;
- forbidden-path negative candidate;
- forged-digest negative candidate;
- fail-closed unsupported required validators.

Useful patch mechanics explored in closed PR #61 should be extracted into the canonical verifier path rather than resurrecting a second verifier package.

## Governance status

GitHub metadata still reports `main` as **unprotected**. Issue #35 therefore remains the highest integration-governance safety gap. Repository files and agent instructions cannot substitute for a GitHub-enforced ruleset/branch-protection boundary.

## Community/backlog state

Growth Seed #28 has completed and is closed after the IDKGraph P0 decomposition landed. The repository should continue to gate new Growth Seeds on verified descendant evidence and reviewer capacity rather than issue volume.

## Updated execution order

```text
1. Protect main (#35) when admin/settings action is available.
2. Independently review/integrate green PR #90.
3. Synchronize #34 and complete controlled Docker gate #37.
4. Build #5 real patch-bundle evaluator through canonical EvaluatorPlan path.
5. Connect real node adapter to merged PR #78 orchestrator.
6. Build minimal Evidence Report/replay UX for #16.
7. Run real-task #2/#30 only after comparable real evidence exists.
```

Synthetic R2/R3 scale/evolution research may continue as research, but it should not be promoted as proof of real Verified Swarm Runner quality before this execution chain is complete.
