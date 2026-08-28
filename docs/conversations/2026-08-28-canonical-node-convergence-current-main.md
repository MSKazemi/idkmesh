# Conversation record: converge canonical node onto current main

**Date:** 2026-08-28
**Repository:** `MSKazemi/idkmesh`

## User instruction

The project owner provided the repository URL again, continuing the standing instruction to keep collaborating on and improving IDKMesh and to preserve substantive project work in the public repository.

## Repository state observed

The earlier canonical-node integration PR #34 remained open but had diverged substantially from current `main`: its branch contained the node implementation, while `main` had advanced with independent verification, evaluator-sovereignty binding, a deterministic two-attempt orchestration kernel, and R2 scheduling/scale evidence.

The canonical Work Unit had also evolved to **WorkUnit v0.2**, adding explicit capability/resource requirements, security classification, independent-verification policy, and zero-project-spend fields.

The node code on the old branch had already been adapted to WorkUnit v0.2, but replaying the branch's stale history risked rolling back or conflicting with newer project work.

## Convergence decision

Apply **convergence before expansion**:

1. start a fresh branch from current `main`;
2. transplant only the isolated `node/` subtree, the Node Execution Binding schema, and the node CI workflow;
3. preserve all newer verification/orchestration/research files from `main` untouched;
4. keep the worker output as canonical ResultManifest v0.1 and require independent VerificationResult v0.1 downstream;
5. leave merge authority outside the worker and outside this collaboration turn.

This creates a much smaller review surface than merging 26 stale branch commits into a `main` that had advanced by 28 commits.

## Safety finding and fix

During convergence, one fail-open edge case was identified:

- the node recorded both tracked and untracked changed paths;
- `changes.patch` packages only tracked Git diffs;
- therefore a task that created an untracked file could otherwise be reported successful while part of its candidate output was silently absent from the artifact bundle.

Node v0.1 now fails closed on any untracked artifact until an explicit typed/size-bounded untracked-artifact packaging contract exists.

The ResultManifest records `untracked_file_count` and `untracked_paths`, and a unit test covers this invariant.

## Updated current trust pipeline

```text
WorkUnit v0.2
 -> idkmesh-node real local Docker execution
 -> ResultManifest v0.1 + bounded candidate patch
 -> independent verifier / evaluator-owned plan
 -> VerificationResult v0.1 + evidence
 -> human or governance integration decision
```

The node documentation was updated to reflect that the independent verifier and deterministic two-attempt orchestration kernel already exist on current `main`.

## Next milestone

Run one controlled real-Docker end-to-end acceptance on an immutable IDKMesh source commit and retain both worker and evaluator provenance. The worker must remain unable to certify itself, and project spend must remain zero.

After that evidence, connect `idkmesh-node` as a concrete adapter behind the existing multi-attempt orchestration kernel.

## Community impact

This turn reduces integration debt rather than creating another architecture layer. Contributors get one current worker branch based directly on `main`, a narrower diff, an explicit fail-closed artifact rule, and a concrete next acceptance experiment.
