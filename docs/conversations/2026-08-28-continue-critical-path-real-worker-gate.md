# Project Conversation — Continue Critical Path Toward Real Worker

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Project-owner instruction

> Continue

Repository context: `https://github.com/MSKazemi/idkmesh`

## Assistant execution summary

This continuation deliberately prioritized the current executable critical path instead of opening another theory/research lane.

The main result is a much stronger, exact-head real-worker candidate in PR #91 plus a precise independent Docker acceptance protocol in issue #37.

---

## 1. Rechecked the live P0 state

At the beginning of the turn, the repository had already advanced beyond the previous snapshot:

- the executable local verifier from PR #72 was on `main`;
- issue #4 explicitly allowed the deterministic two-attempt coordinator slice;
- PR #51 still represented the repository-side fail-closed/branch-protection work, while actual GitHub `main` protection remained an admin configuration issue;
- the old canonical-node PR #34 was still open/stale at first inspection.

The key rule for this turn became:

> **Do not duplicate work that concurrent contributors/agents have already landed; converge on one implementation and spend reviewer attention on missing evidence.**

---

## 2. Began a two-attempt orchestrator, then closed it when equivalent work landed

A branch `orchestration/two-attempt-kernel-v0` and PR #87 were initially created with:

- exactly two isolated fixture attempts;
- canonical ResultManifest generation;
- independent local-verifier routing;
- deterministic replay signatures;
- worker-failure isolation;
- no automatic integration;
- unit tests and CI.

While PR #87 was opening, equivalent implementation from PR #78 appeared on `main`, including:

- `experiments/two_attempt_orchestrator.py`;
- `examples/orchestration/two-attempt-good-vs-bad.json`;
- `examples/orchestration/two-attempt-worker-failure.json`.

Issue #4 also recorded the merged deterministic coordinator baseline.

PR #87 was therefore explicitly closed as superseded rather than raced against the already-landed implementation.

### Durable collaboration lesson

A self-evolving repository must optimize not only for generation but also for convergence:

```text
parallel ideas
 -> detect semantic overlap
 -> select/reconcile one useful implementation
 -> close duplicates visibly
 -> preserve scarce review capacity
```

Raw PR count is not progress if two PRs solve the same problem.

---

## 3. Isolated the real remaining issue #4 blocker

After PR #78, the deterministic control-plane baseline existed. The missing critical-path component was the real bounded worker plus independent runtime evidence:

```text
canonical WorkUnit
 -> real bounded worker
 -> ResultManifest
 -> independent verifier
 -> VerificationResult
 -> human/governance decision
```

The remaining work therefore shifted to the canonical node worker and controlled Docker acceptance.

---

## 4. Reconciled old PR #34 without force-pushing, then accepted its supersession

PR #34 was initially on stale head:

`9ac6c09d4db06dc7c846d319e76624fbf1eaaa0f`

Its 12 changed paths were verified to be absent from then-current `main`, so the change remained cleanly additive.

A normal two-parent synchronization merge was constructed:

- previous PR head as one parent;
- current `main` as the other parent;
- current `main` tree preserved;
- exact node blobs overlaid;
- no force push.

Temporary synchronized head:

`10a1885505859abef266d66839c90c0041adcf8a`

Both checks passed on that exact head:

- IDKMesh Node CI `33182791204` — success;
- Phase 0 schema check `33182791209` — success.

Immediately afterward, concurrent repository work closed #34 without merge and opened a cleaner convergence PR #91. Because #91 started from a newer `main` and intentionally superseded #34, #34 was not reopened.

---

## 5. PR #91 became the canonical real-worker convergence path

PR #91:

`Converge canonical WorkUnit v0.2 node backend onto current main`

Branch:

`integration/canonical-node-current`

It keeps one canonical contract family:

```text
WorkUnit v0.2
 -> Node Execution Binding v0.1
 -> idkmesh-node
 -> ResultManifest v0.1
 -> independent VerificationResult v0.1
 -> human/governance integration
```

The worker never treats its own successful execution as acceptance.

### Initial important safety delta: untracked artifacts

The convergence work identified a real evidence-completeness problem:

- Git patches capture tracked changes;
- untracked outputs can exist outside that patch;
- a successful worker must not silently omit part of its candidate output.

PR #91 therefore fails closed on any untracked task artifact until a typed/size-bounded packaging protocol exists.

It records:

- `untracked_file_count`;
- `untracked_paths`;
- policy violations.

---

## 6. Independent pre-Docker source review found additional blocking evidence-integrity gaps

Before asking a community contributor to run Docker acceptance, the worker source was independently reviewed rather than assuming green unit CI proved containment.

The review found four important issues.

### Finding A — truncated candidate patch could still report success

The earlier runner bounded `changes.patch` by truncating it, but a truncated candidate could still report `status: succeeded`.

That is an evidence-completeness failure: the canonical candidate artifact is incomplete.

**Fix:** patch truncation now creates an output-policy violation and the attempt fails closed. A truncated patch is diagnostic evidence only.

### Finding B — task-writable `.git` metadata was later trusted by the host

The earlier design mounted the checkout—including `.git`—read/write into the task container, then used that same Git metadata for host `git diff`/`git ls-files` evidence.

A task could therefore alter refs/index/config/control metadata and influence the measurement of its own output.

**Fix:**

- real Git directory stored outside task-writable `/workspace`;
- mounted read-only at `/git-meta` for task-side Git reads;
- host Git result capture uses explicit trusted `--git-dir` and `--work-tree` arguments;
- host Git HOME/XDG isolated;
- system/global Git config disabled;
- inherited `GIT_*` variables removed;
- empty init template used;
- task-visible `.git` pointer tampering detected and fails closed.

This turns Git metadata into evaluator-controlled state rather than candidate-controlled state.

### Finding C — `.gitignore` could hide untracked output

The earlier untracked scan used standard ignore behavior, which meant a task output matching `.gitignore` could disappear from evidence.

**Fix:** untracked result capture intentionally does **not** use `--exclude-standard`. Ignored files are still task outputs and are still observed/fail closed.

### Finding D — image tag and wall-time provenance were not strong enough

Two reproducibility/resource issues remained:

1. allowlisted tags such as `python:3.12-alpine` are mutable;
2. `budget.wall_seconds` constrained the container timeout but not necessarily source preparation/result capture.

These were fixed before the Docker gate was frozen.

---

## 7. Runtime image is now bound to immutable evidence

The configured allowlisted tag is treated only as a routing/configuration selector.

The controlled host must preload it. The node then requires Docker inspection to provide:

1. immutable local image ID: `sha256:<64 hex>`;
2. matching immutable repository digest for the configured repository, e.g. `python@sha256:<64 hex>`.

A locally retagged/unresolved image without matching repository-digest evidence fails closed.

Docker runs by the resolved **image ID**, not the mutable tag.

The ResultManifest/provenance retains:

- `configured_container_image`;
- `resolved_container_image_id`;
- `resolved_container_repo_digest`;
- repository digest in runtime provenance.

The worker performs no implicit pull during task execution.

---

## 8. WorkUnit wall time is now a cross-phase bound

`budget.wall_seconds` is required and carried into the parsed WorkUnit.

The worker uses a single attempt deadline spanning:

- immutable image resolution;
- source preparation/fetch/checkout;
- task-container execution;
- bounded host-side Git evidence capture.

A small bounded tail is reserved for evidence capture so the task cannot consume every remaining second and prevent the worker from recording why it stopped.

Measured whole-attempt overruns become runtime-policy violations.

Timeout cleanup (`docker rm -f`) is bounded containment cleanup, not extra task authority.

---

## 9. Tests now encode the discovered assumptions as explicit invariants

The node test suite now covers, among other cases:

- Docker network `none`, read-only root, dropped capabilities, `no-new-privileges`, resource limits;
- external `/git-meta` read-only mount;
- removal of inherited Git configuration;
- explicit trusted host Git metadata/work-tree addressing;
- `.git` pointer tampering;
- ignored untracked output detection;
- untracked-artifact fail-closed behavior;
- tracked path policy;
- candidate-patch truncation failure;
- immutable image ID + matching repository digest parsing;
- locally retagged/no-repository-digest rejection;
- preloaded-image requirement;
- WorkUnit wall-budget handling.

---

## 10. Negative CI evidence was retained and used

A hardening head `5567dd126ae4ef45a90a852c7f66361ff89703ac` produced:

- Phase 0 schema check `33183750657` — success;
- IDKMesh Node CI `33183750664` — failure.

The Node CI failure was isolated to the **test harness**, not a production-policy relaxation:

- a test passed the synthetic absolute deadline `10**12` into a real Python subprocess;
- the OS time conversion raised `OverflowError: timestamp too large to convert to C _PyTime_t`.

The test was corrected to use a realistic `time.monotonic() + 60` deadline.

This failed run remains useful evidence because it demonstrates that new safety logic was actually exercised rather than merely documented.

---

## 11. Executable hardening became green

After correcting the test fixture, executable code head:

`cb9279c86cd30a2201267319b623206e153d7239`

passed:

- IDKMesh Node CI `33183837389` — success;
- Phase 0 schema check `33183837441` — success.

Then `node/README.md` was updated to accurately describe the implemented immutable-image and whole-attempt evidence rules.

That documentation-only commit moved the PR head, so the previous green evidence was **not** silently carried forward. Exact-head CI was checked again.

---

## 12. Final frozen PR #91 candidate for controlled Docker acceptance

Final head at the end of this turn:

`d638a2f78e4a89353b98e91052233e365f56f90a`

The only delta from `cb927...` is `node/README.md`, but the exact final head has its own complete green checks:

- **IDKMesh Node CI** — run `33183974768` — success;
- **Phase 0 schema check** — run `33183974817` — success.

PR #91 remains **draft** intentionally. It is not considered runtime-ready merely because unit/contract CI is green.

---

## 13. Issue #37 is now the precise independent runtime gate

Issue #37 was rewritten as:

`Acceptance: run PR #91 idkmesh-node on a controlled Docker host`

It is frozen to exact head:

`d638a2f78e4a89353b98e91052233e365f56f90a`

It records the exact green CI runs and requires a controlled-host positive smoke plus five negative runtime checks:

### Positive

- preload and inspect `python:3.12-alpine`;
- record local image ID and matching repository digest;
- run canonical node smoke;
- verify ResultManifest, source/image provenance, path evidence, artifact/log hashes, sandbox flags, no untracked/policy violations, no self-acceptance.

### Negative A — out-of-scope tracked path

Must fail closed and record path violation.

### Negative B — ignored untracked output

Must still be observed despite `.gitignore` and fail closed.

### Negative C — Git metadata tampering

Must not change real `/git-meta`; host evidence remains anchored to trusted metadata; pointer tampering is recorded and fails.

### Negative D — oversized candidate patch

`patch_truncated=1` must be a failure; truncated patch is diagnostic only.

### Negative E — unresolved/locally retagged image

Missing preloaded image or missing matching repository digest must fail closed; no implicit task-time pull.

No Docker runtime acceptance was claimed in this chat because the available execution environment is not the explicitly controlled Docker host required by #37.

---

## Current critical-path state

```text
canonical contracts                   DONE
independent local verifier            DONE
2-attempt deterministic coordinator   DONE (PR #78)
real worker convergence               PR #91 DRAFT
pre-Docker source hardening            DONE
Node CI + Phase 0 CI                  GREEN on d638a2f...
controlled Docker acceptance #37      BLOCKING
real node -> verifier E2E             NEXT AFTER #37
real node orchestrator adapter        NEXT AFTER #37
3–5 bounded real attempts              LATER
```

---

## Safety / convergence decisions preserved

- No duplicate orchestrator was kept open after equivalent work landed.
- No force push was used while reconciling the old node branch.
- Closed/unmerged PR #34 was not reopened once cleaner #91 existed.
- Candidate evidence cannot omit untracked or oversized tracked output while reporting success.
- Candidate code cannot control the Git metadata used by host evidence capture.
- Host Git configuration is isolated from untrusted repository attributes/config triggers.
- Runtime image evidence is immutable and execution uses the resolved image ID.
- Whole-attempt wall budget covers source/runtime/evidence phases.
- No Docker acceptance was claimed without a controlled host.
- Acceptance evidence is bound to an exact PR head.
- Movement of base `main` alone does not invalidate a frozen candidate; changing the candidate does.
- Worker success remains candidate evidence, not acceptance.
- No autonomous merge authority was added.
- PR #91 remains draft until independent runtime evidence exists.
- Repository-admin `main` branch protection remains a separate unresolved safety requirement.

---

## Community impact

This turn turned a vague "run Docker sometime" milestone into a high-value, bounded community contribution.

A contributor with a controlled Docker host now has:

- one exact candidate SHA;
- exact green CI identifiers;
- a positive procedure;
- five falsification-oriented negative tests;
- explicit image/source/evidence provenance requirements;
- clear acceptance semantics.

That is more useful for community growth than opening additional competing worker/orchestrator designs, because the task has a concrete definition of success and produces inspectable evidence the next contributor can build on.

---

## Next action

The highest-value next action is independent controlled-host Docker evidence for #37 against:

`d638a2f78e4a89353b98e91052233e365f56f90a`

After #37 passes on the unchanged head:

```text
real node
 -> ResultManifest
 -> independent verifier
 -> VerificationResult
 -> human decision
```

Then connect `idkmesh-node` behind the already-landed two-attempt coordinator and repeat the same evidence discipline with two real attempts.
